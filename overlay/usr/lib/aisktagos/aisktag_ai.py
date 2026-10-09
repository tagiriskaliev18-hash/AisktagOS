"""Клиентская библиотека Mind (встроенный ИИ AIsktagOS). Только стандартная библиотека Python.

Её используют команда `ai`, окно-ассистент aisktag-mind и Центр AIsktagOS.

Поддерживаемые провайдеры (cfg['provider']):
  'local'  — локальный llama.cpp через systemd-socket (http://127.0.0.1:6573, по умолчанию)
  'nvidia' — NVIDIA NIM API (OpenAI-совместимый, https://integrate.api.nvidia.com/v1)
  'claude' — Anthropic Messages API (https://api.anthropic.com/v1/messages)

Конфигурация читается из ~/.config/aisktagos/ai.json или переменных окружения:
  AI_PROVIDER   — 'local' | 'nvidia' | 'claude'
  AI_BASE_URL   — переопределить базовый URL (необязательно)
  AI_MODEL      — имя модели
  AI_API_KEY    — ключ API (для nvidia/claude)
  NVIDIA_API_KEY, CLAUDE_API_KEY — альтернативные переменные для ключей
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Iterator

LOCAL_URL      = "http://127.0.0.1:6573/v1"
BACKEND_HEALTH = "http://127.0.0.1:6574/health"
USER_CONF      = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "aisktagos" / "ai.json"
CATALOG        = Path(os.environ.get("AISKTAG_CATALOG", "/usr/share/aisktagos/ai/models.json"))
MODEL_HELPER   = "/usr/lib/aisktagos/ai/aisktag-ai-model"
READ_TIMEOUT   = 900  # секунд; первая загрузка модели может занять несколько минут

# ---------------------------------------------------------------------------
# Провайдеры: базовые URL и топ-модели для кодинга/дизайна
# ---------------------------------------------------------------------------
PROVIDERS: dict[str, dict] = {
    "local": {
        "base_url": LOCAL_URL,
        "api_key":  "",
        "models": [
            "aisktag-mind",       # псевдоним, выбирается моделью из каталога
        ],
        "description": "Локальная модель (llama.cpp, работает без интернета)",
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key":  "",           # заполняется из NVIDIA_API_KEY
        "models": [
            "meta/llama-3.1-70b-instruct",          # универсальный топ
            "mistralai/codestral-22b-v0-1",          # лучший в кодинге
            "qwen/qwen2.5-coder-32b-instruct",       # сильный кодер
            "microsoft/phi-3.5-mini-instruct",       # быстрый, лёгкий
            "deepseek-ai/deepseek-coder-v2-lite-instruct",  # специализированный
        ],
        "description": "NVIDIA NIM (бесплатный API, 80+ моделей)",
    },
    "claude": {
        "base_url": "https://api.anthropic.com",
        "api_key":  "",           # заполняется из CLAUDE_API_KEY
        "models": [
            "claude-opus-4-5",    # самый мощный, дорогой
            "claude-sonnet-4-5",  # баланс цены и качества ← рекомендуется
            "claude-haiku-4-5",   # самый быстрый и дешёвый
        ],
        "description": "Anthropic Claude (подписка или API-ключ)",
    },
}

DEFAULTS = {
    "provider":    "local",
    "base_url":    LOCAL_URL,
    "model":       "aisktag-mind",
    "api_key":     "",
    "temperature": 0.3,
}

# Роли ассистента: (название, системный промпт)
PERSONAS = {
    "general": (
        "Универсальный",
        "Ты Mind — встроенный ассистент операционной системы AIsktagOS (Ubuntu + KDE Plasma) для программистов. "
        "Отвечай коротко, по делу и по-русски (если пользователь пишет на другом языке — на нём). "
        "Код давай в блоках с указанием языка. Если не уверен — так и скажи, не выдумывай.",
    ),
    "code": (
        "Программист",
        "Ты опытный инженер-программист. Пиши рабочий, идиоматичный и безопасный код, объясняй решение в 2–3 фразах. "
        "Отвечай на языке пользователя, код — в блоках.",
    ),
    "review": (
        "Ревьюер кода",
        "Ты строгий, но доброжелательный ревьюер кода. Найди ошибки, уязвимости, гонки, утечки и неочевидные проблемы, "
        "затем предложи улучшения. Формат: список замечаний по убыванию важности, у каждого — почему и как исправить.",
    ),
    "explain": (
        "Объясняет код",
        "Ты объясняешь код новичку: что делает, как устроено, где подводные камни. Просто, с примерами.",
    ),
    "admin": (
        "Linux-администратор",
        "Ты Linux-администратор Ubuntu 24.04 с KDE Plasma. Давай проверенные команды (apt, systemctl, journalctl), "
        "предупреждай об опасных действиях и объясняй, что команда сделает.",
    ),
    "translate": (
        "Переводчик",
        "Ты технический переводчик. Переводи между русским и английским, сохраняя код, термины и форматирование.",
    ),
    "design": (
        "UI/UX дизайнер",
        "Ты опытный UI/UX дизайнер и фронтенд-разработчик. Помогаешь с дизайном интерфейсов, цветовыми схемами, "
        "типографикой, компоновкой. Предлагаешь конкретные значения (hex, pt, px). Говоришь по-русски.",
    ),
}


class AIError(Exception):
    """Понятная пользователю ошибка (текст на русском)."""


# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Читает конфиг из файла, затем перекрывает переменными окружения."""
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(USER_CONF.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass

    # Переменные окружения имеют наивысший приоритет
    env_map = {
        "AI_PROVIDER":   "provider",
        "AI_BASE_URL":   "base_url",
        "AI_MODEL":      "model",
        "AI_API_KEY":    "api_key",
    }
    for env, key in env_map.items():
        if os.environ.get(env):
            cfg[key] = os.environ[env]

    # Отдельные ключи провайдеров (удобнее при работе с несколькими)
    if not cfg.get("api_key"):
        provider = cfg.get("provider", "local")
        if provider == "nvidia" and os.environ.get("NVIDIA_API_KEY"):
            cfg["api_key"] = os.environ["NVIDIA_API_KEY"]
        elif provider == "claude" and os.environ.get("CLAUDE_API_KEY"):
            cfg["api_key"] = os.environ["CLAUDE_API_KEY"]

    # Если провайдер известен и base_url не переопределён явно — берём из таблицы
    provider = cfg.get("provider", "local")
    if provider in PROVIDERS and cfg["base_url"] == LOCAL_URL and provider != "local":
        cfg["base_url"] = PROVIDERS[provider]["base_url"]
        if not cfg["api_key"] and PROVIDERS[provider]["api_key"]:
            cfg["api_key"] = PROVIDERS[provider]["api_key"]

    cfg["base_url"] = cfg["base_url"].rstrip("/")
    return cfg


def save_config(cfg: dict) -> None:
    """Сохраняет конфиг (без пустых полей)."""
    USER_CONF.parent.mkdir(parents=True, exist_ok=True)
    keep = {k: cfg[k] for k in ("provider", "base_url", "model", "api_key", "temperature") if k in cfg}
    USER_CONF.write_text(json.dumps(keep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        USER_CONF.chmod(0o600)   # файл может содержать ключ API
    except OSError:
        pass


def is_local(cfg: dict | None = None) -> bool:
    cfg = cfg or load_config()
    return cfg.get("provider", "local") == "local" or cfg["base_url"].startswith(
        ("http://127.0.0.1", "http://localhost")
    )


def _headers_openai(cfg: dict) -> dict:
    """HTTP-заголовки для OpenAI-совместимых провайдеров (local, nvidia)."""
    h = {"Content-Type": "application/json", "User-Agent": "aisktagos-mind/2.0"}
    if cfg.get("api_key"):
        h["Authorization"] = "Bearer " + cfg["api_key"]
    return h


def _headers_claude(cfg: dict) -> dict:
    """HTTP-заголовки для Anthropic API."""
    return {
        "Content-Type":    "application/json",
        "User-Agent":      "aisktagos-mind/2.0",
        "x-api-key":       cfg.get("api_key", ""),
        "anthropic-version": "2023-06-01",
    }


# ---------------------------------------------------------------------------
# Стриминг через OpenAI-совместимый API (local + nvidia)
# ---------------------------------------------------------------------------

def _stream_openai(messages: list[dict], cfg: dict, max_tokens: int | None,
                   temperature: float, should_stop: Callable[[], bool] | None) -> Iterator[str]:
    body = {
        "model":       cfg["model"],
        "messages":    messages,
        "stream":      True,
        "temperature": temperature,
    }
    if max_tokens:
        body["max_tokens"] = max_tokens

    req = urllib.request.Request(
        cfg["base_url"] + "/chat/completions",
        data=json.dumps(body).encode(),
        headers=_headers_openai(cfg),
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=READ_TIMEOUT)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:400]
        if e.code in (401, 403):
            raise AIError("Сервер ИИ отклонил ключ доступа. Проверьте api_key в настройках.") from e
        if e.code == 429:
            raise AIError("Превышен лимит запросов к API. Подождите немного или смените модель.") from e
        raise AIError(f"Сервер ИИ ответил ошибкой {e.code}: {detail}") from e
    except (urllib.error.URLError, ConnectionError, socket.timeout) as e:
        if is_local(cfg):
            raise AIError(
                "Локальный ИИ недоступен. Проверьте:\n"
                "  systemctl status aisktag-llm.socket\n"
                "  journalctl -u aisktag-llm-backend\n"
                "(возможно, модель не установлена: запустите ai model)"
            ) from e
        raise AIError(f"Не удалось подключиться к {cfg['base_url']}: {getattr(e, 'reason', e)}") from e

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
                delta = json.loads(data)["choices"][0].get("delta", {})
            except (ValueError, KeyError, IndexError):
                continue
            if delta.get("content"):
                yield delta["content"]


# ---------------------------------------------------------------------------
# Стриминг через Anthropic Messages API
# ---------------------------------------------------------------------------

def _stream_claude(messages: list[dict], cfg: dict, max_tokens: int | None,
                   temperature: float, should_stop: Callable[[], bool] | None) -> Iterator[str]:
    """Anthropic SSE: события content_block_delta с delta.type == text_delta."""
    # Anthropic API не принимает system-сообщение внутри messages[]
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    user_messages = [m for m in messages if m["role"] != "system"]

    body: dict = {
        "model":       cfg["model"],
        "messages":    user_messages,
        "max_tokens":  max_tokens or 4096,
        "stream":      True,
        "temperature": temperature,
    }
    if system_parts:
        body["system"] = "\n\n".join(system_parts)

    req = urllib.request.Request(
        cfg["base_url"] + "/v1/messages",
        data=json.dumps(body).encode(),
        headers=_headers_claude(cfg),
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=READ_TIMEOUT)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:400]
        if e.code in (401, 403):
            raise AIError("Anthropic отклонил ключ API. Проверьте CLAUDE_API_KEY.") from e
        if e.code == 429:
            raise AIError("Превышен лимит Claude API. Подождите или перейдите на Haiku.") from e
        raise AIError(f"Claude API ошибка {e.code}: {detail}") from e
    except (urllib.error.URLError, ConnectionError, socket.timeout) as e:
        raise AIError(f"Не удалось подключиться к Anthropic: {getattr(e, 'reason', e)}") from e

    with resp:
        for raw in resp:
            if should_stop and should_stop():
                return
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                event = json.loads(data)
            except ValueError:
                continue
            # content_block_delta → delta.type == "text_delta"
            if event.get("type") == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta" and delta.get("text"):
                    yield delta["text"]


# ---------------------------------------------------------------------------
# Единая точка входа
# ---------------------------------------------------------------------------

def stream_chat(
    messages: list[dict],
    cfg: dict | None = None,
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> Iterator[str]:
    """Потоково отдаёт куски ответа модели. Бросает AIError с понятным текстом."""
    cfg = cfg or load_config()
    temp = cfg.get("temperature", 0.3) if temperature is None else temperature

    provider = cfg.get("provider", "local")
    if provider == "claude":
        yield from _stream_claude(messages, cfg, max_tokens, temp, should_stop)
    else:
        # 'local' и 'nvidia' — оба OpenAI-совместимые
        yield from _stream_openai(messages, cfg, max_tokens, temp, should_stop)


def complete(messages: list[dict], cfg: dict | None = None, **kw) -> str:
    """Не-стриминговый вариант: возвращает весь ответ строкой."""
    return "".join(stream_chat(messages, cfg, **kw))


# ---------------------------------------------------------------------------
# Состояние локального бэкенда
# ---------------------------------------------------------------------------

def _get(url: str, timeout: float = 0.6) -> int | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, OSError):
        return None


def backend_state() -> str:
    """ready | loading | idle | missing — актуально только для локального провайдера."""
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


# ---------------------------------------------------------------------------
# Каталог моделей и железо
# ---------------------------------------------------------------------------

def ram_mb() -> int:
    """Доступная RAM в МБ (Linux /proc/meminfo)."""
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError):
        pass
    return 0


def load_catalog() -> dict:
    """Читает models.json — каталог локальных GGUF-моделей."""
    try:
        return json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"default": "lite", "models": []}


def recommend_model(total_mb: int | None = None) -> str:
    """Самая сильная модель каталога, которая комфортно помещается в RAM."""
    total_mb = ram_mb() if total_mb is None else total_mb
    best = None
    for m in load_catalog()["models"]:
        if total_mb >= m["ram_mb"] and (best is None or m["size_mb"] > best["size_mb"]):
            best = m
    return best["id"] if best else load_catalog().get("default", "lite")


def list_models() -> dict:
    """Каталог с отметками «установлена» и активной моделью."""
    try:
        out = subprocess.run(
            [MODEL_HELPER, "list"], capture_output=True, text=True, timeout=10, check=True
        ).stdout
        return json.loads(out)
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"active": "lite", "models": load_catalog()["models"]}


def list_provider_models(provider: str) -> list[str]:
    """Список моделей для выбранного провайдера (из таблицы PROVIDERS)."""
    return PROVIDERS.get(provider, {}).get("models", [])
