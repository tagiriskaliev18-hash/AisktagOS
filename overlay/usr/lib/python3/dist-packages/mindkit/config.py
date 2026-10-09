"""Единые настройки экосистемы — один файл вместо .env в каждом проекте.

Файл: ``<config_dir>/settings.json``. Любую настройку можно перекрыть
переменной окружения: ``gateway.url`` → ``MINDTAG_GATEWAY_URL``.
Секреты сюда не пишутся, для них есть ``mindkit.keychain``.
"""

from __future__ import annotations

import copy
import json
import os
import socket
import uuid
from typing import Any

from .paths import config_dir, private_write

DEFAULTS: dict[str, Any] = {
    "device": {"id": "", "name": ""},
    # Шлюз AI Duo из multimodel-agent: OpenAI-совместимый /v1
    "gateway": {"url": "http://127.0.0.1:8000/v1", "model": "gpt-4o-mini", "key_name": "AIDUO_API_KEY"},
    # Локальная модель как запасной вариант без интернета
    "ollama": {"url": "http://127.0.0.1:11434/v1", "model": "qwen14b"},
    "link": {"port": 47800, "discovery_port": 47801, "clipboard_sync": True, "accept_files": True},
    "search": {"roots": ["~/projects", "~/Projects", "~/Desktop", "~/Documents", "~/MindTagSystem"],
               "max_file_mb": 2},
    "store": {"apps_dir": "~/MindTagSystem",
              "catalog_url": "https://raw.githubusercontent.com/tagiriskaliev18-hash/MindTagSystem/main/ecosystem.json"},
}


def settings_path():
    return config_dir() / "settings.json"


def _merge(base: dict, extra: dict) -> dict:
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load() -> dict:
    """Настройки: значения по умолчанию, поверх них файл."""
    cfg = copy.deepcopy(DEFAULTS)
    path = settings_path()
    if path.exists():
        try:
            _merge(cfg, json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    dev = cfg["device"]
    if not dev.get("id") or not dev.get("name"):
        # Первый запуск: устройство получает постоянный id и имя
        dev["id"] = dev.get("id") or uuid.uuid4().hex[:12]
        dev["name"] = dev.get("name") or socket.gethostname()
        save(cfg)
    return cfg


def save(cfg: dict) -> None:
    private_write(settings_path(), json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")


def _env_name(key: str) -> str:
    return "MINDTAG_" + key.replace(".", "_").upper()


def _parse(raw: str) -> Any:
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def get(key: str, default: Any = None, cfg: dict | None = None) -> Any:
    """Значение по пути «раздел.ключ»; переменная окружения важнее файла."""
    env = os.environ.get(_env_name(key))
    if env is not None:
        return _parse(env)
    node: Any = cfg if cfg is not None else load()
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def set(key: str, value: Any) -> dict:  # noqa: A001 — как в git config
    cfg = load()
    node = cfg
    parts = key.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise ValueError(f"{key}: «{part}» не раздел")
    node[parts[-1]] = value
    save(cfg)
    return cfg


def device() -> dict:
    cfg = load()
    return {"id": cfg["device"]["id"], "name": cfg["device"]["name"]}
