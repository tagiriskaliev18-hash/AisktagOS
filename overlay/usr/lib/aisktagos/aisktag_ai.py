"""Клиентская библиотека Mind (встроенный ИИ AIsktagOS). Только стандартная библиотека Python.

Её используют команда `ai`, окно-ассистент aisktag-mind и Центр AIsktagOS.
По умолчанию запросы идут на локальный сервер http://127.0.0.1:6573 (llama.cpp, запускается
по первому запросу). Любой OpenAI-совместимый сервер подключается в ~/.config/aisktagos/ai.json
или переменными AI_BASE_URL / AI_MODEL / AI_API_KEY (OpenAI, Ollama, LM Studio, vLLM, прокси к Claude…).

Запасные поставщики: ~/.config/aisktagos/providers.json — список облачных серверов с ключами пользователя.
Если основной сервер не может ответить (кончились токены или деньги, лимит запросов, ключ отозван, нет
связи), запрос сам уходит к следующему по списку, а последней всегда остаётся встроенная модель — она
работает без интернета. Серверы с форматом Anthropic (/v1/messages, например Kimi через tokenwave.ru)
поддерживаются наравне с OpenAI-совместимыми.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Iterator

LOCAL_URL = "http://127.0.0.1:6573/v1"
BACKEND_HEALTH = "http://127.0.0.1:6574/health"
USER_CONF = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "aisktagos" / "ai.json"
PROVIDERS_CONF = USER_CONF.parent / "providers.json"
# Когда какой поставщик отказал: такой пропускаем, пока не истечёт пауза (чтобы не ждать его каждый раз)
STATE_FILE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "aisktagos" / "providers-state.json"
CATALOG = Path(os.environ.get("AISKTAG_CATALOG", "/usr/share/aisktagos/ai/models.json"))   # переопределение — для тестов
MODEL_HELPER = "/usr/lib/aisktagos/ai/aisktag-ai-model"
# Первая загрузка модели может занять несколько минут на медленном диске
READ_TIMEOUT = 900

DEFAULTS = {"provider": "local", "base_url": LOCAL_URL, "model": "aisktag-mind",
            "api_key": "", "temperature": 0.3, "api": "openai"}

# Роли ассистента: (название, системный промпт)
PERSONAS = {
    "general": ("Универсальный",
                "Ты Mind — встроенный ассистент операционной системы AIsktagOS (Ubuntu + KDE Plasma) для программистов. "
                "Отвечай коротко, по делу и по-русски (если пользователь пишет на другом языке — на нём). "
                "Код давай в блоках с указанием языка. Если не уверен — так и скажи, не выдумывай."),
    "code": ("Программист",
             "Ты опытный инженер-программист. Пиши рабочий, идиоматичный и безопасный код, объясняй решение в 2–3 фразах. "
             "Отвечай на языке пользователя, код — в блоках."),
    "review": ("Ревьюер кода",
               "Ты строгий, но доброжелательный ревьюер кода. Найди ошибки, уязвимости, гонки, утечки и неочевидные проблемы, "
               "затем предложи улучшения. Формат: список замечаний по убыванию важности, у каждого — почему и как исправить."),
    "explain": ("Объясняет код",
                "Ты объясняешь код новичку: что делает, как устроено, где подводные камни. Просто, с примерами."),
    "admin": ("Linux-администратор",
              "Ты Linux-администратор Ubuntu 24.04 с KDE Plasma. Давай проверенные команды (apt, systemctl, journalctl), "
              "предупреждай об опасных действиях и объясняй, что команда сделает."),
    "translate": ("Переводчик",
                  "Ты технический переводчик. Переводи между русским и английским, сохраняя код, термины и форматирование."),
}


class AIError(Exception):
    """Понятная пользователю ошибка (текст на русском)."""


class ProviderDown(AIError):
    """Поставщик сейчас не может ответить (токены, лимит, ключ, сеть) — можно идти к следующему."""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


# Ответы сервера, после которых есть смысл спросить другого поставщика. 400 сюда не входит: это ошибка
# самого запроса (например, не поместился контекст), и другой сервер её не исправит.
SWITCH_CODES = {401, 402, 403, 404, 408, 409, 425, 429, 500, 502, 503, 504, 529}
# Признаки «кончились деньги/токены» в теле ответа: часть серверов отвечает на это кодом 400
QUOTA_WORDS = ("quota", "insufficient", "balance", "credit", "billing", "exceeded", "limit", "баланс", "лимит")
# Пауза после отказа, секунды: лимит запросов обычно отпускает через минуты, деньги и ключ — нет
COOLDOWN = {429: 300, 402: 3600, 401: 3600, 403: 3600, 404: 3600}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(USER_CONF.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    for env, key in (("AI_BASE_URL", "base_url"), ("AI_MODEL", "model"), ("AI_API_KEY", "api_key")):
        if os.environ.get(env):
            cfg[key] = os.environ[env]
    cfg["base_url"] = cfg["base_url"].rstrip("/")
    return cfg


def save_config(cfg: dict) -> None:
    USER_CONF.parent.mkdir(parents=True, exist_ok=True)
    keep = {k: cfg[k] for k in DEFAULTS if k in cfg}
    USER_CONF.write_text(json.dumps(keep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        USER_CONF.chmod(0o600)          # внутри может лежать ключ API
    except OSError:
        pass


def is_local(cfg: dict | None = None) -> bool:
    cfg = cfg or load_config()
    return cfg["base_url"].startswith(("http://127.0.0.1", "http://localhost"))


def _headers(cfg: dict) -> dict:
    h = {"Content-Type": "application/json", "User-Agent": "aisktagos-mind/1.0"}
    if cfg.get("api_key"):
        h["Authorization"] = "Bearer " + cfg["api_key"]
    if cfg.get("api") == "anthropic":
        h["anthropic-version"] = "2023-06-01"
        if cfg.get("api_key"):
            h["x-api-key"] = cfg["api_key"]     # у Anthropic ключ здесь, у прокси — в Authorization
    return h


# --- Формат Anthropic (/v1/messages) ----------------------------------------------
# Внутри AIsktagOS всё говорит в формате OpenAI; для серверов Anthropic запрос и ответ переводятся.

def _to_anthropic(messages: list[dict], cfg: dict, *, tools: list | None = None, max_tokens: int | None = None,
                  temperature: float | None = None, stream: bool = False) -> dict:
    system, out = [], []

    def put(role: str, blocks: list) -> None:
        if not blocks:
            return
        if out and out[-1]["role"] == role:           # Anthropic требует чередования user/assistant
            out[-1]["content"] += blocks
        else:
            out.append({"role": role, "content": blocks})

    for m in messages:
        role, content = m["role"], m.get("content")
        if role == "system":
            if isinstance(content, str) and content:
                system.append(content)
        elif role == "tool":
            put("user", [{"type": "tool_result", "tool_use_id": m.get("tool_call_id") or "call",
                          "content": content or ""}])
        elif role == "assistant":
            blocks = [{"type": "text", "text": content}] if isinstance(content, str) and content.strip() else []
            for c in m.get("tool_calls") or []:
                try:
                    args = json.loads(c["function"].get("arguments") or "{}")
                except ValueError:
                    args = {}
                blocks.append({"type": "tool_use", "id": c.get("id") or c["function"]["name"],
                               "name": c["function"]["name"], "input": args if isinstance(args, dict) else {}})
            put("assistant", blocks)
        else:
            if isinstance(content, str):
                put("user", [{"type": "text", "text": content}] if content else [])
                continue
            blocks = []
            for part in content or []:
                if part.get("type") == "text":
                    blocks.append({"type": "text", "text": part["text"]})
                elif part.get("type") == "image_url":
                    url = part["image_url"]["url"]
                    if url.startswith("data:") and ";base64," in url:
                        media, data = url[5:].split(";base64,", 1)
                        blocks.append({"type": "image", "source": {"type": "base64", "media_type": media, "data": data}})
            put("user", blocks)
    if out and out[0]["role"] != "user":
        out.insert(0, {"role": "user", "content": [{"type": "text", "text": "…"}]})
    body = {"model": cfg["model"], "messages": out, "max_tokens": int(max_tokens or cfg.get("max_tokens") or 4096)}
    if system:
        body["system"] = "\n\n".join(system)
    if temperature is not None:
        body["temperature"] = temperature
    if tools:
        body["tools"] = [{"name": t["function"]["name"], "description": t["function"].get("description", ""),
                          "input_schema": t["function"].get("parameters") or {"type": "object", "properties": {}}}
                         for t in tools]
    if stream:
        body["stream"] = True
    return body


def anthropic_message(cfg: dict, body: dict, timeout: float = READ_TIMEOUT) -> dict:
    """Один ответ сервера Anthropic по запросу в формате OpenAI (body как у /chat/completions).
    Возвращает сообщение в формате OpenAI (content + tool_calls). Ошибки HTTP — как у urllib."""
    payload = _to_anthropic(body["messages"], cfg, tools=body.get("tools"), max_tokens=body.get("max_tokens"),
                            temperature=body.get("temperature"))
    req = urllib.request.Request(cfg["base_url"] + "/messages", data=json.dumps(payload).encode(),
                                 headers=_headers(cfg), method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    text, calls = [], []
    for b in data.get("content", []):
        if b.get("type") == "text":
            text.append(b.get("text", ""))
        elif b.get("type") == "tool_use":
            calls.append({"id": b.get("id"), "type": "function",
                          "function": {"name": b.get("name"), "arguments": json.dumps(b.get("input") or {},
                                                                                      ensure_ascii=False)}})
    msg = {"role": "assistant", "content": "".join(text) or None}
    if calls:
        msg["tool_calls"] = calls
    return msg


# --- Поставщики и запасная цепочка --------------------------------------------------

def _key(cfg: dict) -> str:
    return f"{cfg['base_url'].rstrip('/')}|{cfg.get('model', '')}"


def label(cfg: dict) -> str:
    """Как назвать поставщика человеку: «Groq (llama-3.3-70b)», «встроенная модель»."""
    if is_local(cfg) and cfg["base_url"].rstrip("/") == LOCAL_URL:
        return "встроенная модель (без интернета)"
    from urllib.parse import urlparse
    name = cfg.get("name") or urlparse(cfg["base_url"]).netloc or cfg["base_url"]
    return f"{name} ({cfg.get('model', '?')})"


def load_providers() -> list[dict]:
    try:
        data = json.loads(PROVIDERS_CONF.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = data.get("providers", []) if isinstance(data, dict) else data
    return [p for p in items if isinstance(p, dict) and p.get("base_url")]


def save_providers(items: list[dict]) -> None:
    PROVIDERS_CONF.parent.mkdir(parents=True, exist_ok=True)
    PROVIDERS_CONF.write_text(json.dumps({"providers": items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        PROVIDERS_CONF.chmod(0o600)          # внутри ключи API
    except OSError:
        pass


def add_provider(entry: dict, first: bool = False) -> None:
    """Добавить поставщика или обновить его (по id); first=True — поставить в начало списка."""
    items = [p for p in load_providers() if p.get("id") != entry.get("id")]
    items.insert(0, entry) if first else items.append(entry)
    save_providers(items)


def _load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass


def mark_down(cfg: dict, code: int | None) -> None:
    if is_local(cfg):
        return
    state = _load_state()
    state[_key(cfg)] = {"until": time.time() + COOLDOWN.get(code or 0, 60), "code": code}
    _save_state(state)


def mark_ok(cfg: dict) -> None:
    state = _load_state()
    if state.pop(_key(cfg), None) is not None:
        _save_state(state)


def cooling(cfg: dict) -> int:
    """Сколько секунд ещё отдыхает поставщик после отказа (0 — готов)."""
    left = _load_state().get(_key(cfg), {}).get("until", 0) - time.time()
    return max(0, int(left))


def chain(cfg: dict | None = None) -> list[dict]:
    """Порядок, в котором спрашивать поставщиков: основной, запасные из providers.json, встроенная модель.
    Отдыхающие после отказа уходят в конец (если отдыхают все — спросим их всё равно)."""
    cfg = cfg or load_config()
    out, seen = [cfg], {_key(cfg)}
    for p in load_providers():
        if p.get("enabled") is False:
            continue
        c = dict(cfg)
        c.pop("name", None)
        c.update({k: p[k] for k in ("name", "base_url", "model", "api_key", "api") if k in p})
        c["base_url"] = c["base_url"].rstrip("/")
        c.setdefault("api", "openai")
        if _key(c) not in seen:
            seen.add(_key(c))
            out.append(c)
    if not cfg.get("no_local_fallback"):
        local = dict(cfg, base_url=LOCAL_URL, model=DEFAULTS["model"], api_key="", api="openai")
        local.pop("name", None)
        if _key(local) not in seen:
            out.append(local)
    ready = [c for c in out if not cooling(c)]
    return ready + [c for c in out if cooling(c)]


def reason(code: int | None) -> str:
    """Почему поставщик не ответил — словами."""
    if code == 402:
        return "закончились деньги или токены"
    if code == 429:
        return "исчерпан лимит запросов"
    if code in (401, 403):
        return "ключ не принят (истёк или отозван)"
    if code == 404:
        return "модель больше недоступна"
    if code and code >= 500:
        return f"сервер не отвечает (ошибка {code})"
    if code:
        return f"ошибка {code}"
    return "нет связи"


def switch_text(prev: dict, new: dict, err: AIError) -> str:
    return f"{label(prev)}: {reason(getattr(err, 'code', None))} — дальше отвечает {label(new)}"


def http_failure(cfg: dict, e: urllib.error.HTTPError, detail: str) -> AIError:
    """Ошибка HTTP → ProviderDown (можно к следующему поставщику) или обычная AIError."""
    low = detail.lower()
    if e.code in SWITCH_CODES or (e.code == 400 and any(w in low for w in QUOTA_WORDS) and "context" not in low):
        code = 402 if e.code == 400 else e.code
        if e.code in (401, 403):
            return ProviderDown("Сервер ИИ отклонил ключ доступа (проверьте api_key в настройках).", code)
        return ProviderDown(f"{label(cfg)}: {reason(code)}. {detail[:200]}".strip(), code)
    return AIError(f"Сервер ИИ ответил ошибкой {e.code}: {detail}")


def _print_switch(prev: dict, new: dict, err: AIError) -> None:
    import sys
    print(f"\n↪ {switch_text(prev, new, err)}", file=sys.stderr, flush=True)


def _stream_one(messages: list[dict], cfg: dict, max_tokens: int | None, temperature: float,
                should_stop: Callable[[], bool] | None) -> Iterator[str]:
    anthropic = cfg.get("api") == "anthropic"
    if anthropic:
        body = _to_anthropic(messages, cfg, max_tokens=max_tokens, temperature=temperature, stream=True)
        url = cfg["base_url"] + "/messages"
    else:
        body = {"model": cfg["model"], "messages": messages, "stream": True, "temperature": temperature}
        if max_tokens:
            body["max_tokens"] = max_tokens
        url = cfg["base_url"] + "/chat/completions"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=_headers(cfg), method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=READ_TIMEOUT)
    except urllib.error.HTTPError as e:
        raise http_failure(cfg, e, e.read().decode(errors="replace")[:300]) from e
    except (urllib.error.URLError, ConnectionError, socket.timeout) as e:
        if is_local(cfg):
            raise ProviderDown("Локальный ИИ недоступен. Проверьте: systemctl status aisktag-llm.socket "
                               "и journalctl -u aisktag-llm-backend (возможно, модель не установлена: ai model).") from e
        raise ProviderDown(f"Не удалось подключиться к {cfg['base_url']}: {getattr(e, 'reason', e)}") from e
    with resp:
        for raw in resp:
            if should_stop and should_stop():
                return
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                return
            try:
                event = json.loads(data)
            except ValueError:
                continue
            if anthropic:
                if event.get("type") == "error":
                    err = event.get("error") or {}
                    raise ProviderDown(f"{label(cfg)}: {err.get('message', 'ошибка сервера')}",
                                       529 if err.get("type") == "overloaded_error" else 500)
                if event.get("type") == "message_stop":
                    return
                delta = event.get("delta") or {}
                if event.get("type") == "content_block_delta" and delta.get("type") == "text_delta" and delta.get("text"):
                    yield delta["text"]
                continue
            try:
                delta = event["choices"][0].get("delta", {})
            except (KeyError, IndexError, TypeError):
                continue
            if delta.get("content"):
                yield delta["content"]


last_used: dict | None = None      # кто ответил на последний запрос (для подписи «отвечал …»)


def stream_chat(messages: list[dict], cfg: dict | None = None, *, max_tokens: int | None = None,
                temperature: float | None = None, should_stop: Callable[[], bool] | None = None,
                on_switch: Callable[[dict, dict, AIError], None] | None = None,
                fallback: bool = True) -> Iterator[str]:
    """Потоково отдаёт куски ответа. Бросает AIError с понятным текстом.
    Если поставщик не может ответить ещё до первого куска (токены, лимит, ключ, сеть), вопрос сам уходит
    к следующему из chain(); on_switch(прежний, новый, ошибка) сообщает об этом (по умолчанию — в stderr)."""
    global last_used
    cfg = cfg or load_config()
    temp = cfg["temperature"] if temperature is None else temperature
    cands = chain(cfg) if fallback else [cfg]
    prev, err = None, None
    for c in cands:
        if prev is not None:
            (on_switch or _print_switch)(prev, c, err)
        started = False
        try:
            for piece in _stream_one(messages, c, max_tokens, temp, should_stop):
                started = True
                yield piece
            mark_ok(c)
            last_used = c
            return
        except ProviderDown as e:
            if started:                      # половину ответа уже показали — повторять у другого нельзя
                raise
            mark_down(c, e.code)
            prev, err = c, e
    raise err if err else AIError("Нет ни одного доступного сервера ИИ")


def complete(messages: list[dict], cfg: dict | None = None, **kw) -> str:
    return "".join(stream_chat(messages, cfg, **kw))


def _get(url: str, timeout: float = 0.6) -> int | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, OSError):
        return None


def backend_state() -> str:
    """ready — модель загружена; loading — загружается; idle — спит (проснётся по запросу); missing — служба не слушает порт."""
    code = _get(BACKEND_HEALTH)
    if code == 200:
        return "ready"
    if code == 503:
        return "loading"
    try:
        with socket.create_connection(("127.0.0.1", 6573), timeout=0.4):
            return "idle"
    except OSError:
        return "missing"


# --- Железо и каталог моделей ---------------------------------------------------

def ram_mb() -> int:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError):
        pass
    return 0


def load_catalog() -> dict:
    try:
        return json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"default": "lite", "models": []}


def recommend_model(total_mb: int | None = None) -> str:
    """Самая сильная модель каталога, которая комфортно помещается в память (ram_mb — запас на систему)."""
    total_mb = ram_mb() if total_mb is None else total_mb
    best = None
    for m in load_catalog()["models"]:
        if total_mb >= m["ram_mb"] and (best is None or m["size_mb"] > best["size_mb"]):
            best = m
    return best["id"] if best else load_catalog().get("default", "lite")


def list_models() -> dict:
    """Каталог с отметками «установлена» и активной моделью (через помощника, он не требует root для list)."""
    try:
        out = subprocess.run([MODEL_HELPER, "list"], capture_output=True, text=True, timeout=10, check=True).stdout
        return json.loads(out)
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"active": "lite", "models": load_catalog()["models"]}
