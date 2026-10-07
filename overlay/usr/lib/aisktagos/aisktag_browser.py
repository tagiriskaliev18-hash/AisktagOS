"""Управление Firefox для Джарвиса (как Claude in Chrome) через WebDriver BiDi. Только стандартная библиотека.

Джарвис открывает отдельное окно Firefox со своим профилем (~/.local/share/aisktagos/jarvis/firefox)
и порт удалённого управления только на 127.0.0.1. Основной профиль пользователя не трогается:
пароли, куки и история обычного Firefox Джарвису не видны.

    b = Browser(); b.open("https://example.com"); print(b.read()); print(b.elements()); b.click(3)
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import time
from pathlib import Path

PORT = int(os.environ.get("JARVIS_BROWSER_PORT", "9333"))
PROFILE = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "aisktagos" / "jarvis" / "firefox"
PAGE_TEXT_LIMIT = 12000
ELEMENTS_LIMIT = 150

# Настройки отдельного профиля: без мастера первого запуска и лишних вкладок
USER_JS = """\
user_pref("browser.aboutwelcome.enabled", false);
user_pref("browser.startup.homepage_override.mstone", "ignore");
user_pref("startup.homepage_welcome_url", "");
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("datareporting.policy.dataSubmissionEnabled", false);
user_pref("toolkit.telemetry.reportingpolicy.firstRun", false);
user_pref("browser.tabs.warnOnClose", false);
user_pref("browser.sessionstore.resume_from_crash", false);
user_pref("intl.accept_languages", "ru-RU, ru, en-US, en");
"""

# Клавиши WebDriver: имя → код
KEYS = {"enter": "", "return": "", "tab": "", "escape": "", "esc": "",
        "backspace": "", "delete": "", "space": " ", "up": "", "down": "",
        "left": "", "right": "", "pageup": "", "pagedown": "", "home": "",
        "end": "", "ctrl": "", "control": "", "shift": "", "alt": "",
        "meta": "", **{f"f{i}": chr(0xE031 + i - 1) for i in range(1, 13)}}

# Скрипт страницы: пронумеровать видимые элементы, с которыми можно работать
ELEMENTS_JS = r"""
(() => {
  const sel = 'a[href],button,input,select,textarea,summary,[role=button],[role=link],[role=checkbox],' +
              '[role=tab],[role=menuitem],[role=option],[role=switch],[contenteditable=""],[contenteditable=true],[onclick]';
  document.querySelectorAll('[data-jarvis-id]').forEach(e => e.removeAttribute('data-jarvis-id'));
  const out = []; let n = 0;
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect(), st = getComputedStyle(el);
    if (r.width < 2 || r.height < 2 || st.visibility === 'hidden' || st.display === 'none') continue;
    if (r.bottom < 0 || r.top > innerHeight * 3) continue;
    if (el.disabled) continue;
    el.setAttribute('data-jarvis-id', ++n);
    const tag = el.tagName.toLowerCase();
    let kind = el.getAttribute('role') || tag;
    if (tag === 'input') kind = 'input:' + (el.type || 'text');
    let label = (el.getAttribute('aria-label') || (el.labels && el.labels[0] && el.labels[0].innerText) ||
                 el.innerText || el.value || el.placeholder ||
                 el.title || el.alt || el.name || '').replace(/\s+/g, ' ').trim().slice(0, 80);
    if (tag === 'a' && !label) label = el.getAttribute('href').slice(0, 80);
    let extra = '';
    if (tag === 'input' && (el.type === 'checkbox' || el.type === 'radio')) extra = el.checked ? ' [отмечено]' : '';
    else if ((tag === 'input' || tag === 'textarea') && el.value && el.type !== 'password') extra = ' = "' + el.value.slice(0, 40) + '"';
    if (r.top > innerHeight || r.bottom < 0) extra += ' (ниже, нужна прокрутка)';
    out.push('[' + n + '] ' + kind + ' «' + label + '»' + extra);
    if (n >= LIMIT) break;
  }
  return out.join('\n');
})()
"""


class BrowserError(Exception):
    """Понятная ошибка управления браузером (текст на русском)."""


class _WebSocket:
    """Минимальный клиент WebSocket (RFC 6455): текстовые кадры, маскирование, ping/pong."""

    def __init__(self, host: str, port: int, path: str, timeout: float = 30):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise BrowserError("Firefox закрыл соединение управления")
            head += chunk
        status, _, self.buf = head.partition(b"\r\n\r\n")
        if b" 101 " not in status.split(b"\r\n")[0]:
            raise BrowserError("Firefox не принял подключение: " + status.split(b"\r\n")[0].decode(errors="replace"))

    def _recv(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise BrowserError("соединение с Firefox прервано (окно браузера закрыто?)")
            self.buf += chunk
        data, self.buf = self.buf[:n], self.buf[n:]
        return data

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        head = bytes([0x80 | opcode])
        n = len(payload)
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 65536:
            head += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            head += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def send(self, text: str) -> None:
        self._send_frame(0x1, text.encode())

    def recv(self) -> str:
        parts = []
        while True:
            b0, b1 = self._recv(2)
            opcode, n = b0 & 0x0F, b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._recv(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._recv(8))[0]
            mask = self._recv(4) if b1 & 0x80 else None
            payload = self._recv(n)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 0x9:                       # ping
                self._send_frame(0xA, payload)
                continue
            if opcode == 0x8:
                raise BrowserError("Firefox закрыл соединение управления")
            if opcode in (0x0, 0x1, 0x2):
                parts.append(payload)
                if b0 & 0x80:
                    return b"".join(parts).decode("utf-8", errors="replace")

    def close(self) -> None:
        try:
            self._send_frame(0x8, b"")
            self.sock.close()
        except OSError:
            pass


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def find_firefox() -> str | None:
    for cand in (os.environ.get("JARVIS_FIREFOX"), "firefox", "/usr/lib/firefox/firefox", "firefox-esr"):
        if cand and (shutil.which(cand) or os.path.isfile(cand)):
            return shutil.which(cand) or cand
    return None


class Browser:
    def __init__(self, headless: bool | None = None):
        self.headless = headless if headless is not None else os.environ.get("JARVIS_HEADLESS") == "1"
        self.ws: _WebSocket | None = None
        self.next_id = 0
        self.context: str | None = None

    # --- Подключение ------------------------------------------------------------
    def _launch(self) -> None:
        exe = find_firefox()
        if not exe:
            raise BrowserError("Firefox не найден. Установите его: sudo apt install firefox")
        PROFILE.mkdir(parents=True, exist_ok=True)
        (PROFILE / "user.js").write_text(USER_JS, encoding="utf-8")
        argv = [exe, "--new-instance", "--profile", str(PROFILE), "--remote-debugging-port", str(PORT),
                "--remote-allow-hosts", "localhost,127.0.0.1"]
        if self.headless:
            argv.append("--headless")
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        for _ in range(150):
            if _port_open(PORT):
                return
            time.sleep(0.2)
        raise BrowserError("Firefox не открыл порт управления за 30 секунд")

    def connect(self) -> None:
        if self.ws:
            return
        if not _port_open(PORT):
            self._launch()
        last = None
        for _ in range(20):
            try:
                self.ws = _WebSocket("127.0.0.1", PORT, "/session")
                break
            except (OSError, BrowserError) as e:
                last = e
                time.sleep(0.5)
        if not self.ws:
            raise BrowserError(f"не удалось подключиться к Firefox: {last}")
        try:
            self.cmd("session.new", {"capabilities": {"alwaysMatch": {"acceptInsecureCerts": False}}})
        except BrowserError as e:
            if "session" in str(e).lower():
                raise BrowserError("Firefox Джарвиса уже управляется другим процессом. Закройте окно "
                                   "Firefox Джарвиса или другой экземпляр jarvis и повторите.") from e
            raise
        self.context = None

    def close(self) -> None:
        if self.ws:
            try:
                self.cmd("session.end", {})
            except BrowserError:
                pass
            self.ws.close()
            self.ws = None

    def cmd(self, method: str, params: dict, timeout: float = 60) -> dict:
        if not self.ws:
            self.connect()
        self.next_id += 1
        my_id = self.next_id
        self.ws.sock.settimeout(timeout)
        self.ws.send(json.dumps({"id": my_id, "method": method, "params": params}))
        while True:
            try:
                msg = json.loads(self.ws.recv())
            except socket.timeout as e:
                raise BrowserError(f"Firefox не ответил за {int(timeout)} с ({method})") from e
            if msg.get("id") != my_id:
                continue                            # события и чужие ответы
            if msg.get("type") == "error":
                raise BrowserError(f"{msg.get('error')}: {msg.get('message', '')}".strip())
            return msg.get("result", {})

    # --- Вкладки ----------------------------------------------------------------
    def tabs(self) -> list[dict]:
        return self.cmd("browsingContext.getTree", {"maxDepth": 0}).get("contexts", [])

    def _ctx(self) -> str:
        if self.context:
            return self.context
        tabs = self.tabs()
        if not tabs:
            self.context = self.cmd("browsingContext.create", {"type": "tab"})["context"]
        else:
            self.context = tabs[-1]["context"]
        return self.context

    def tab_list(self) -> str:
        cur = self._ctx()
        return "\n".join(f"{i}{' (текущая)' if t['context'] == cur else ''}: {t.get('url', '')}"
                         for i, t in enumerate(self.tabs())) or "вкладок нет"

    def tab_switch(self, index: int) -> str:
        tabs = self.tabs()
        if not 0 <= index < len(tabs):
            raise BrowserError(f"нет вкладки {index}")
        self.context = tabs[index]["context"]
        self.cmd("browsingContext.activate", {"context": self.context})
        return f"текущая вкладка {index}: {tabs[index].get('url', '')}"

    def tab_new(self, url: str = "") -> str:
        self.context = self.cmd("browsingContext.create", {"type": "tab"})["context"]
        return self.open(url) if url else "открыта новая вкладка"

    def tab_close(self) -> str:
        self.cmd("browsingContext.close", {"context": self._ctx()})
        self.context = None
        return "вкладка закрыта"

    # --- Страница ---------------------------------------------------------------
    def eval(self, expression: str, await_promise: bool = False, own: bool = False) -> dict:
        params = {"expression": expression, "target": {"context": self._ctx()}, "awaitPromise": await_promise}
        if own:
            params["resultOwnership"] = "root"
        res = self.cmd("script.evaluate", params)
        if res.get("type") == "exception":
            text = res.get("exceptionDetails", {}).get("text", "ошибка JavaScript")
            raise BrowserError(f"ошибка скрипта на странице: {text}")
        return res.get("result", {})

    def _value(self, expression: str):
        r = self.eval(expression)
        return r.get("value")

    def open(self, url: str) -> str:
        if "://" not in url and not url.startswith(("about:", "file:")):
            url = "https://" + url
        try:
            self.cmd("browsingContext.navigate", {"context": self._ctx(), "url": url, "wait": "complete"}, timeout=90)
        except BrowserError as e:
            if "timeout" not in str(e).lower() and "не ответил" not in str(e):
                raise
        return self.summary()

    def back(self) -> str:
        self.cmd("browsingContext.traverseHistory", {"context": self._ctx(), "delta": -1})
        time.sleep(1)
        return self.summary()

    def summary(self) -> str:
        title = self._value("document.title") or ""
        url = self._value("location.href") or ""
        return f"Открыта страница: {title}\nURL: {url}"

    def read(self, limit: int = PAGE_TEXT_LIMIT) -> str:
        text = self._value("document.body ? document.body.innerText : ''") or ""
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if len(text) > limit:
            text = text[:limit] + f"\n…(обрезано, всего {len(text)} символов)"
        return self.summary() + "\n\n" + text

    def elements(self) -> str:
        out = self._value(ELEMENTS_JS.replace("LIMIT", str(ELEMENTS_LIMIT))) or ""
        return out or "на странице не найдено интерактивных элементов"

    def _element_ref(self, idx: int) -> dict:
        res = self.eval(f"document.querySelector('[data-jarvis-id=\"{int(idx)}\"]')", own=True)
        if res.get("type") != "node":
            raise BrowserError(f"элемент [{idx}] не найден — сначала вызовите browser_elements (страница могла измениться)")
        self.eval(f"document.querySelector('[data-jarvis-id=\"{int(idx)}\"]')"
                  ".scrollIntoView({block: 'center', inline: 'center'})")
        return {"sharedId": res["sharedId"]}

    def click(self, idx: int) -> str:
        ref = self._element_ref(idx)
        self.cmd("input.performActions", {"context": self._ctx(), "actions": [{
            "type": "pointer", "id": "mouse", "parameters": {"pointerType": "mouse"},
            "actions": [{"type": "pointerMove", "x": 0, "y": 0, "origin": {"type": "element", "element": ref}},
                        {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}]}]})
        time.sleep(1.0)
        return f"нажал на [{idx}]. " + self.summary()

    def type(self, idx: int | None, text: str, submit: bool = False) -> str:
        if idx is not None:
            self.click(idx)
            # Очистить поле перед вводом
            self.eval("(() => { const e = document.activeElement; if (e && 'value' in e) { e.value = '';"
                      " e.dispatchEvent(new Event('input', {bubbles: true})); } })()")
        keys = []
        for ch in text:
            keys += [{"type": "keyDown", "value": ch}, {"type": "keyUp", "value": ch}]
        if submit:
            keys += [{"type": "keyDown", "value": KEYS["enter"]}, {"type": "keyUp", "value": KEYS["enter"]}]
        self.cmd("input.performActions", {"context": self._ctx(),
                                          "actions": [{"type": "key", "id": "kbd", "actions": keys}]})
        time.sleep(1.0 if submit else 0.2)
        where = f"в [{idx}]" if idx is not None else "в активный элемент"
        return f"ввёл текст {where}" + (" и нажал Enter. " + self.summary() if submit else "")

    def key(self, combo: str) -> str:
        names = [k.strip().lower() for k in combo.replace("+", " ").split() if k.strip()]
        codes = [KEYS.get(n, n if len(n) == 1 else None) for n in names]
        if None in codes:
            raise BrowserError(f"неизвестная клавиша в «{combo}»")
        acts = [{"type": "keyDown", "value": c} for c in codes] + [{"type": "keyUp", "value": c} for c in reversed(codes)]
        self.cmd("input.performActions", {"context": self._ctx(),
                                          "actions": [{"type": "key", "id": "kbd", "actions": acts}]})
        time.sleep(0.5)
        return f"нажал {combo}"

    def scroll(self, direction: str = "down") -> str:
        dy = {"down": 0.8, "up": -0.8}.get(direction, 0.8)
        if direction in ("top", "bottom"):
            self.eval("scrollTo(0, " + ("0" if direction == "top" else "document.body.scrollHeight") + ")")
        else:
            self.eval(f"scrollBy(0, innerHeight * {dy})")
        pos = self._value("Math.round(100 * (scrollY + innerHeight) / Math.max(1, document.body.scrollHeight))")
        return f"прокрутил {direction}; видно до {pos}% страницы"

    def screenshot(self, path: str) -> str:
        data = self.cmd("browsingContext.captureScreenshot", {"context": self._ctx()})["data"]
        Path(path).write_bytes(base64.b64decode(data))
        return path

    def run_js(self, code: str) -> str:
        res = self.eval(code, await_promise=True)
        return json.dumps(res.get("value", res.get("type")), ensure_ascii=False)[:4000]
