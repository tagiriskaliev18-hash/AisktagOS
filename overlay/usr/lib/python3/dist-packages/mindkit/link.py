"""MindLink — связь между устройствами одного владельца (как Continuity у Apple).

Возможности:

* **Общий буфер обмена** (Universal Clipboard): скопировали на ноутбуке —
  вставили на компьютере.
* **Handoff**: открытая ссылка, файл или текст «переезжает» на другое
  устройство и открывается там одной командой.
* **MindDrop** (AirDrop): отправка файлов на устройство рядом.
* **Уведомления** на всех устройствах сразу.

Доверие устроено как Apple ID: у владельца один «ключ аккаунта».
Устройства с одинаковым ключом видят друг друга в локальной сети
(UDP-широковещание) и принимают запросы только с подписью этим ключом
(HMAC-SHA256, защита от повтора). Если установлен ``cryptography``,
содержимое ещё и шифруется AES-GCM; без него оно подписано, но
передаётся открыто — ``mindkit link status`` честно об этом пишет.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from . import clipboard, config, keychain, net, notify
from .paths import data_dir, downloads_dir

ACCOUNT_KEY_NAME = "MINDLINK_ACCOUNT_KEY"
MAX_SKEW = 120            # секунд: допустимое расхождение часов
MAX_BODY = 512 * 1024 * 1024
INLINE_FILE_LIMIT = 4 * 1024 * 1024   # файлы до 4 МБ Handoff везёт с собой


# ── ключ аккаунта ────────────────────────────────────────────────────────

def _format_key(raw: bytes) -> str:
    text = base64.b32encode(raw).decode().rstrip("=")
    return "-".join(text[i:i + 4] for i in range(0, len(text), 4))


def _parse_key(text: str) -> bytes:
    clean = "".join(ch for ch in text.upper() if ch.isalnum())
    clean += "=" * (-len(clean) % 8)
    raw = base64.b32decode(clean)
    if len(raw) != 32:
        raise ValueError("ключ аккаунта MindLink должен быть 32 байта")
    return raw


def init_account(force: bool = False) -> str:
    """Создаёт ключ аккаунта на первом устройстве. Возвращает его для других устройств."""
    current = keychain.get(ACCOUNT_KEY_NAME)
    if current and not force:
        return current
    key = _format_key(secrets.token_bytes(32))
    keychain.set(ACCOUNT_KEY_NAME, key)
    return key


def join_account(key_text: str) -> None:
    _parse_key(key_text)  # проверка формата
    keychain.set(ACCOUNT_KEY_NAME, key_text.strip().upper())


def account_key() -> bytes | None:
    text = keychain.get(ACCOUNT_KEY_NAME)
    if not text:
        return None
    try:
        return _parse_key(text)
    except ValueError:
        return None


def _derive(key: bytes, label: str) -> bytes:
    return hmac.new(key, b"mindlink/" + label.encode(), hashlib.sha256).digest()


def discovery_tag(key: bytes) -> str:
    return _derive(key, "discover").hex()[:20]


# ── шифрование и подпись ────────────────────────────────────────────────

def encryption_available() -> bool:
    if os.environ.get("MINDKIT_ENCRYPTION") == "off":
        return False
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
    except ImportError:
        return False
    return True


def _seal(key: bytes, body: bytes, aad: bytes) -> tuple[bytes, str]:
    if not body or not encryption_available():
        return body, ""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = secrets.token_bytes(12)
    return nonce + AESGCM(_derive(key, "enc")).encrypt(nonce, body, aad), "aesgcm"


def _open(key: bytes, body: bytes, aad: bytes, mode: str) -> bytes:
    if mode != "aesgcm":
        return body
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(_derive(key, "enc")).decrypt(body[:12], body[12:], aad)


def _signature(key: bytes, ts: str, nonce: str, method: str, path: str, body: bytes) -> str:
    msg = "\n".join([ts, nonce, method, path, hashlib.sha256(body).hexdigest()]).encode()
    return hmac.new(_derive(key, "auth"), msg, hashlib.sha256).hexdigest()


def _response_signature(key: bytes, nonce: str, body: bytes) -> str:
    """Ответ тоже подписан: клиент убеждается, что говорит со своим устройством."""
    return hmac.new(_derive(key, "resp"), nonce.encode() + b"\n" + body, hashlib.sha256).hexdigest()


# ── известные устройства ────────────────────────────────────────────────

def _peers_path() -> Path:
    return data_dir() / "peers.json"


def peers() -> dict[str, dict]:
    path = _peers_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


_peers_lock = threading.Lock()


def remember_peer(peer_id: str, name: str, host: str, port: int) -> None:
    if not peer_id or peer_id == config.device()["id"]:
        return
    with _peers_lock:
        all_peers = peers()
        all_peers[peer_id] = {"name": name, "host": host, "port": int(port), "seen": time.time()}
        path = _peers_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(all_peers, ensure_ascii=False, indent=2), encoding="utf-8")


def forget_peer(peer_id_or_name: str) -> bool:
    with _peers_lock:
        all_peers = peers()
        hit = [pid for pid, p in all_peers.items() if peer_id_or_name in (pid, p.get("name"))]
        for pid in hit:
            del all_peers[pid]
        _peers_path().write_text(json.dumps(all_peers, ensure_ascii=False, indent=2), encoding="utf-8")
    return bool(hit)


def find_peer(name_or_id: str) -> tuple[str, dict] | None:
    for pid, p in peers().items():
        if name_or_id in (pid, p.get("name")):
            return pid, p
    low = name_or_id.lower()
    for pid, p in peers().items():
        if str(p.get("name", "")).lower().startswith(low):
            return pid, p
    return None


# ── обнаружение в локальной сети ───────────────────────────────────────

def discover(timeout: float = 1.5, port: int | None = None) -> list[dict]:
    """Ищет устройства своего аккаунта широковещательным UDP-запросом."""
    key = account_key()
    if not key:
        return []
    port = port or int(config.get("link.discovery_port"))
    tag = discovery_tag(key)
    dev = config.device()
    me = dev["id"]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.3)
    # Имя и порт в запросе: устройство, чей ответ не дойдёт (брандмауэр), само постучится к нам
    query = json.dumps({"mindlink": 1, "q": tag, "from": me, "name": dev["name"],
                        "port": int(config.get("link.port"))}).encode()
    found: dict[str, dict] = {}
    deadline = time.time() + timeout
    for target in ("255.255.255.255", "127.0.0.1"):
        try:
            sock.sendto(query, (target, port))
        except OSError:
            pass
    while time.time() < deadline:
        try:
            data, addr = sock.recvfrom(4096)
        except socket.timeout:
            continue
        except OSError:
            break
        try:
            msg = json.loads(data)
        except ValueError:
            continue
        if msg.get("tag") != tag or msg.get("id") == me:
            continue
        host = "127.0.0.1" if addr[0].startswith("127.") else addr[0]
        found[msg["id"]] = {"id": msg["id"], "name": msg.get("name", "?"), "host": host, "port": int(msg["port"])}
    sock.close()
    # Тег виден в сети и его можно подделать, поэтому устройство попадает в список
    # только после ping с подписанным ответом
    return [p for p in (verify_peer(c["host"], c["port"]) for c in found.values()) if p]


def verify_peer(host: str, port: int) -> dict | None:
    try:
        info = request({"host": host, "port": int(port), "name": host}, "/v1/ping", {}, timeout=3)
    except LinkError:
        return None
    if not info.get("id") or info["id"] == config.device()["id"]:
        return None
    remember_peer(info["id"], info.get("name", "?"), host, int(port))
    return {"id": info["id"], "name": info.get("name", "?"), "host": host, "port": int(port)}


class _Responder(threading.Thread):
    """Отвечает на поиск устройств — только своему аккаунту."""

    def __init__(self, port: int, http_port: int):
        super().__init__(daemon=True, name="mindlink-discovery")
        self.port = port
        self.http_port = http_port
        self.stop = threading.Event()

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        sock.bind(("", self.port))
        sock.settimeout(0.5)
        while not self.stop.is_set():
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            key = account_key()
            if not key:
                continue
            try:
                msg = json.loads(data)
            except ValueError:
                continue
            dev = config.device()
            if msg.get("q") != discovery_tag(key) or msg.get("from") == dev["id"]:
                continue
            reply = {"mindlink": 1, "tag": discovery_tag(key), "id": dev["id"], "name": dev["name"],
                     "port": self.http_port}
            known = peers().get(str(msg.get("from")), {})
            if msg.get("port") and (known.get("host"), known.get("port")) != (addr[0], msg.get("port")):
                # Новое устройство: проверяем его подписанным ping, и оно узнаёт о нас
                threading.Thread(target=verify_peer, args=(addr[0], int(msg["port"])), daemon=True).start()
            try:
                sock.sendto(json.dumps(reply).encode(), addr)
            except OSError:
                pass
        sock.close()


# ── клиент ──────────────────────────────────────────────────────────────

class LinkError(RuntimeError):
    pass


def request(peer: dict, path: str, payload: bytes | dict, headers: dict | None = None,
            timeout: float = 10.0) -> dict:
    key = account_key()
    if not key:
        raise LinkError("MindLink не настроен: выполните «mindkit link init» или «mindkit link join КЛЮЧ»")
    body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
    body, mode = _seal(key, body, path.encode())
    ts, nonce = str(int(time.time())), secrets.token_hex(8)
    dev = config.device()
    hdrs = {
        "Content-Type": "application/octet-stream",
        "X-Mind-Auth": f"{ts}.{nonce}.{_signature(key, ts, nonce, 'POST', path, body)}",
        "X-Mind-From": json.dumps({"id": dev["id"], "name": dev["name"],
                                   "port": int(config.get("link.port"))}, ensure_ascii=True),
        "X-Mind-Enc": mode,
    }
    hdrs.update(headers or {})
    url = f"http://{peer['host']}:{peer['port']}{path}"
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with net.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            sig = resp.headers.get("X-Mind-Sig", "")
    except urllib.error.HTTPError as e:
        raise LinkError(f"{peer.get('name', url)}: HTTP {e.code} {e.read()[:200].decode(errors='replace')}") from e
    except (urllib.error.URLError, OSError) as e:
        raise LinkError(f"{peer.get('name', url)} недоступно: {e}") from e
    if not hmac.compare_digest(sig, _response_signature(key, nonce, raw)):
        raise LinkError(f"{peer.get('name', url)}: ответ без верной подписи — это не ваше устройство")
    try:
        return json.loads(raw or b"{}")
    except ValueError as e:
        raise LinkError(f"{peer.get('name', url)}: непонятный ответ") from e


def _targets(to: str | None) -> list[dict]:
    if to:
        hit = find_peer(to)
        if not hit:
            discover()
            hit = find_peer(to)
        if not hit:
            raise LinkError(f"Устройство «{to}» не найдено. Список: mindkit link devices")
        return [dict(hit[1], id=hit[0])]
    return [dict(p, id=pid) for pid, p in peers().items()]


def _fanout(path: str, payload: Any, to: str | None, headers: dict | None = None) -> dict[str, str]:
    """Отправляет всем (или одному) устройствам. Результат: имя → «ok» или ошибка."""
    result = {}
    for peer in _targets(to):
        try:
            request(peer, path, payload, headers)
            result[peer.get("name", peer["id"])] = "ok"
        except LinkError as e:
            result[peer.get("name", peer["id"])] = str(e)
    return result


def send_clipboard(text: str, to: str | None = None) -> dict[str, str]:
    return _fanout("/v1/clipboard", {"text": text}, to)


def send_notification(title: str, body: str = "", app: str = "MindTagSystem", to: str | None = None) -> dict[str, str]:
    return _fanout("/v1/notify", {"title": title, "body": body, "app": app}, to)


def make_activity(kind: str, title: str = "", **fields: Any) -> dict:
    """Активность Handoff: kind = url | file | text | chat (разговор Mind Studio)."""
    act = {"kind": kind, "title": title, "time": time.time(), **fields}
    if kind == "file" and fields.get("path"):
        path = Path(fields["path"]).expanduser()
        act["path"] = str(path)
        act["name"] = path.name
        act.setdefault("title", path.name)
        if path.is_file() and path.stat().st_size <= INLINE_FILE_LIMIT:
            act["content_b64"] = base64.b64encode(path.read_bytes()).decode()
    return act


def handoff(activity: dict, to: str | None = None) -> dict[str, str]:
    return _fanout("/v1/handoff", {"activity": activity}, to)


def drop(file_path: str | Path, to: str | None = None) -> dict[str, str]:
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise LinkError(f"Нет файла {path}")
    data = path.read_bytes()
    if len(data) > MAX_BODY:
        raise LinkError("Файл больше 512 МБ — MindDrop его не повезёт")
    return _fanout("/v1/drop", data, to, {"X-Mind-Filename": base64.urlsafe_b64encode(path.name.encode()).decode()})


def ping(to: str | None = None) -> dict[str, str]:
    return _fanout("/v1/ping", {}, to)


# ── входящие Handoff ────────────────────────────────────────────────────

def _inbox_path() -> Path:
    return data_dir() / "handoff.json"


def inbox() -> list[dict]:
    path = _inbox_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _store_activity(act: dict) -> dict:
    if act.get("kind") == "file" and act.get("content_b64"):
        target = _unique(downloads_dir() / Path(act.get("name") or "file").name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(base64.b64decode(act.pop("content_b64")))
        act["local_path"] = str(target)
    items = [act] + inbox()
    path = _inbox_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items[:30], ensure_ascii=False, indent=2), encoding="utf-8")
    return act


def resume(index: int = 0, opener: Callable[[str], Any] | None = None) -> dict | None:
    """Открывает активность из входящих (0 — последняя)."""
    items = inbox()
    if index >= len(items):
        return None
    act = items[index]
    kind = act.get("kind")
    if kind == "url" and act.get("url"):
        (opener or _open_url)(act["url"])
    elif kind == "file":
        local = act.get("local_path") or act.get("path")
        if local and Path(local).exists():
            (opener or _open_file)(local if not act.get("line") else f"{local}:{act['line']}")
        elif act.get("path"):
            raise LinkError(f"Файл {act['path']} есть только на устройстве «{act.get('from', '?')}»: "
                            "он больше 4 МБ, пришлите его через «mindkit drop»")
    elif kind == "text":
        clipboard.set(act.get("text", ""))
    elif kind == "chat":
        # Разговор Mind Studio: Studio сама забирает его из входящих при открытии
        import shutil
        import subprocess
        studio = shutil.which("aisktag-studio")
        if studio:
            subprocess.Popen([studio])
        else:
            msgs = (act.get("chat") or {}).get("messages", [])
            clipboard.set("\n\n".join(f"{m.get('role', '?')}: {m.get('content', '')}" for m in msgs))
    return act


def _open_url(url: str) -> None:
    browser = config.get("handoff.browser", "")
    if browser:
        import shlex
        import subprocess
        subprocess.Popen(shlex.split(browser) + [url])
        return
    import webbrowser
    webbrowser.open(url)


def _open_file(target: str) -> None:
    import shutil
    import subprocess
    editor = config.get("handoff.editor", "")
    if editor:
        import shlex
        subprocess.Popen(shlex.split(editor) + [target])
        return
    if shutil.which("code"):
        subprocess.Popen(["code", "-g", target])
        return
    path = target.rsplit(":", 1)[0] if not Path(target).exists() else target
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open" if shutil.which("xdg-open") else "open", path])


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    for i in range(1, 1000):
        cand = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not cand.exists():
            return cand
    return path.with_name(f"{path.stem}-{secrets.token_hex(3)}{path.suffix}")


# ── сервер ──────────────────────────────────────────────────────────────

class Daemon:
    """Служба MindLink: принимает запросы и синхронизирует буфер обмена."""

    def __init__(self, port: int | None = None, discovery_port: int | None = None,
                 clipboard_sync: bool | None = None, host: str = "0.0.0.0", poll: float = 1.0):
        self.port = int(port if port is not None else config.get("link.port"))
        self.discovery_port = int(discovery_port if discovery_port is not None else config.get("link.discovery_port"))
        self.clipboard_sync = bool(config.get("link.clipboard_sync") if clipboard_sync is None else clipboard_sync)
        self.host = host
        self.poll = poll
        self._seen_nonces: dict[str, float] = {}
        self._last_clip = ""
        self._stop = threading.Event()
        self.httpd: ThreadingHTTPServer | None = None
        self.responder: _Responder | None = None
        self.events: list[dict] = []   # для тестов и журнала

    # проверка подписи и замена nonce
    def _verify(self, path: str, headers, body: bytes) -> bytes:
        key = account_key()
        if not key:
            raise PermissionError("на этом устройстве нет ключа аккаунта")
        try:
            ts, nonce, sig = headers.get("X-Mind-Auth", "").split(".")
        except ValueError:
            raise PermissionError("нет подписи") from None
        if abs(time.time() - int(ts)) > MAX_SKEW:
            raise PermissionError("часы устройств расходятся больше чем на 2 минуты")
        if not hmac.compare_digest(sig, _signature(key, ts, nonce, "POST", path, body)):
            raise PermissionError("неверная подпись: другой аккаунт")
        now = time.time()
        self._seen_nonces = {n: t for n, t in self._seen_nonces.items() if now - t < MAX_SKEW * 2}
        if nonce in self._seen_nonces:
            raise PermissionError("повтор запроса")
        self._seen_nonces[nonce] = now
        return _open(key, body, path.encode(), headers.get("X-Mind-Enc", ""))

    def handle(self, path: str, data: bytes, sender: dict, headers) -> dict:
        name = sender.get("name", "?")
        if path == "/v1/ping":
            dev = config.device()
            return {"ok": True, "id": dev["id"], "name": dev["name"]}
        if path == "/v1/clipboard":
            text = json.loads(data).get("text", "")
            self._last_clip = text
            clipboard.set(text)
            self.events.append({"type": "clipboard", "from": name, "text": text})
            return {"ok": True}
        if path == "/v1/notify":
            msg = json.loads(data)
            notify.send(msg.get("title", ""), msg.get("body", ""), app=msg.get("app", "MindTagSystem"), source=name)
            self.events.append({"type": "notify", "from": name, **msg})
            return {"ok": True}
        if path == "/v1/handoff":
            act = json.loads(data).get("activity") or {}
            act["from"] = name
            act = _store_activity(act)
            notify.send(f"Handoff с «{name}»", act.get("title") or act.get("url") or act.get("kind", ""),
                        app="MindLink", source=name)
            self.events.append({"type": "handoff", "from": name, "activity": act})
            return {"ok": True}
        if path == "/v1/drop":
            if not config.get("link.accept_files", True):
                raise PermissionError("приём файлов выключен")
            raw_name = headers.get("X-Mind-Filename", "")
            try:
                fname = Path(base64.urlsafe_b64decode(raw_name.encode()).decode()).name
            except (ValueError, UnicodeDecodeError):
                fname = ""
            target = _unique(downloads_dir() / (fname or "file"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            notify.send(f"MindDrop: файл от «{name}»", str(target), app="MindLink", source=name)
            self.events.append({"type": "drop", "from": name, "path": str(target)})
            return {"ok": True, "saved": target.name}
        raise FileNotFoundError(path)

    def _make_handler(self):
        daemon = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "MindLink/1"

            def log_message(self, *args):  # тихо
                pass

            def _reply(self, code: int, obj: dict, nonce: str = "") -> None:
                raw = json.dumps(obj, ensure_ascii=False).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                key = account_key()
                if nonce and key:
                    self.send_header("X-Mind-Sig", _response_signature(key, nonce, raw))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                if self.path == "/":
                    return self._reply(200, {"service": "MindLink", "version": 1})
                return self._reply(404, {"error": "not found"})

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_BODY + 64:
                    return self._reply(413, {"error": "слишком большой запрос"})
                body = self.rfile.read(length)
                try:
                    data = daemon._verify(self.path, self.headers, body)
                except PermissionError as e:
                    return self._reply(403, {"error": str(e)})
                except Exception:  # noqa: BLE001 — не расшифровалось
                    return self._reply(403, {"error": "не удалось расшифровать"})
                try:
                    sender = json.loads(self.headers.get("X-Mind-From") or "{}")
                except ValueError:
                    sender = {}
                if sender.get("id"):
                    remember_peer(sender["id"], sender.get("name", "?"), self.client_address[0],
                                  int(sender.get("port") or daemon.port))
                nonce = self.headers.get("X-Mind-Auth", "").split(".")[1]
                try:
                    return self._reply(200, daemon.handle(self.path, data, sender, self.headers), nonce)
                except FileNotFoundError:
                    return self._reply(404, {"error": "нет такого метода"}, nonce)
                except PermissionError as e:
                    return self._reply(403, {"error": str(e)}, nonce)
                except (ValueError, KeyError) as e:
                    return self._reply(400, {"error": str(e)}, nonce)

        return Handler

    def start(self) -> "Daemon":
        self.httpd = ThreadingHTTPServer((self.host, self.port), self._make_handler())
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="mindlink-http").start()
        if self.discovery_port:
            self.responder = _Responder(self.discovery_port, self.port)
            self.responder.start()
        if self.clipboard_sync:
            self._last_clip = clipboard.get()
            threading.Thread(target=self._watch_clipboard, daemon=True, name="mindlink-clipboard").start()
        return self

    def _watch_clipboard(self) -> None:
        while not self._stop.wait(self.poll):
            text = clipboard.get()
            if text and text != self._last_clip:
                self._last_clip = text
                if len(text) <= 1024 * 1024:
                    send_clipboard(text)

    def serve_forever(self) -> None:
        self.start()
        if peers() == {}:
            discover()
        try:
            while not self._stop.wait(60):
                discover()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        self._stop.set()
        if self.responder:
            self.responder.stop.set()
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()


def autostart(enable: bool) -> str:
    """Автозапуск службы MindLink при входе в систему (Windows, Linux без systemd-службы ОС)."""
    import sys
    if os.name == "nt":
        startup = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup"
        target = startup / "MindLink.cmd"
        if not enable:
            target.unlink(missing_ok=True)
            return "Автозапуск MindLink выключен"
        pyw = Path(sys.executable).with_name("pythonw.exe")
        exe = pyw if pyw.exists() else Path(sys.executable)
        startup.mkdir(parents=True, exist_ok=True)
        target.write_text(f'@start "" "{exe}" -m mindkit link daemon --wait\r\n', encoding="utf-8")
        return f"Автозапуск MindLink включён: {target}"
    if Path("/usr/lib/systemd/user/mindlink.service").exists():
        import subprocess
        subprocess.run(["systemctl", "--user", "enable" if enable else "disable", "--now", "mindlink.service"],
                       check=False)
        return "Служба mindlink.service " + ("включена" if enable else "выключена")
    target = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "autostart/mindlink.desktop"
    if not enable:
        target.unlink(missing_ok=True)
        return "Автозапуск MindLink выключен"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("[Desktop Entry]\nType=Application\nName=MindLink\n"
                      f"Exec={sys.executable} -m mindkit link daemon --wait\nX-GNOME-Autostart-enabled=true\n"
                      "NoDisplay=true\n", encoding="utf-8")
    return f"Автозапуск MindLink включён: {target}"


def status() -> dict:
    return {
        "device": config.device(),
        "account": bool(account_key()),
        "encryption": encryption_available(),
        "keychain": keychain.backend(),
        "clipboard": clipboard.backend(),
        "port": config.get("link.port"),
        "peers": peers(),
    }
