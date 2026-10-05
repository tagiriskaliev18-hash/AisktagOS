"""Клиентская библиотека Mind (встроенный ИИ AIsktagOS). Только стандартная библиотека Python.

Её используют команда `ai`, окно-ассистент aisktag-mind и Центр AIsktagOS.
По умолчанию запросы идут на локальный сервер http://127.0.0.1:6573 (llama.cpp, запускается
по первому запросу). Любой OpenAI-совместимый сервер подключается в ~/.config/aisktagos/ai.json
или переменными AI_BASE_URL / AI_MODEL / AI_API_KEY (OpenAI, Ollama, LM Studio, vLLM, прокси к Claude…).
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

LOCAL_URL = "http://127.0.0.1:6573/v1"
BACKEND_HEALTH = "http://127.0.0.1:6574/health"
USER_CONF = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "aisktagos" / "ai.json"
CATALOG = Path(os.environ.get("AISKTAG_CATALOG", "/usr/share/aisktagos/ai/models.json"))   # переопределение — для тестов
MODEL_HELPER = "/usr/lib/aisktagos/ai/aisktag-ai-model"
# Первая загрузка модели может занять несколько минут на медленном диске
READ_TIMEOUT = 900

DEFAULTS = {"provider": "local", "base_url": LOCAL_URL, "model": "aisktag-mind",
            "api_key": "", "temperature": 0.3}

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
    return h


def stream_chat(messages: list[dict], cfg: dict | None = None, *, max_tokens: int | None = None,
                temperature: float | None = None, should_stop: Callable[[], bool] | None = None) -> Iterator[str]:
    """Потоково отдаёт куски ответа. Бросает AIError с понятным текстом."""
    cfg = cfg or load_config()
    body = {"model": cfg["model"], "messages": messages, "stream": True,
            "temperature": cfg["temperature"] if temperature is None else temperature}
    if max_tokens:
        body["max_tokens"] = max_tokens
    req = urllib.request.Request(cfg["base_url"] + "/chat/completions", data=json.dumps(body).encode(),
                                 headers=_headers(cfg), method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=READ_TIMEOUT)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        if e.code in (401, 403):
            raise AIError("Сервер ИИ отклонил ключ доступа (проверьте api_key в настройках).") from e
        raise AIError(f"Сервер ИИ ответил ошибкой {e.code}: {detail}") from e
    except (urllib.error.URLError, ConnectionError, socket.timeout) as e:
        if is_local(cfg):
            raise AIError("Локальный ИИ недоступен. Проверьте: systemctl status aisktag-llm.socket "
                          "и journalctl -u aisktag-llm-backend (возможно, модель не установлена: ai model).") from e
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
