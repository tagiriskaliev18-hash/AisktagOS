"""Ассистент Mind (как Siri): один вызов — ответ модели из любого проекта.

Порядок: шлюз AI Duo (``gateway.url``) → локальная Ollama (``ollama.url``).
Ключ шлюза берётся из связки ключей (``gateway.key_name``). Если не
отвечает ни один, ``AssistantError`` объясняет, что запустить.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from . import config, keychain, net

SYSTEM_PROMPT = ("Ты Mind — ассистент экосистемы MindTagSystem. Отвечай кратко, по-русски, "
                 "по делу; код оформляй блоками.")


class AssistantError(RuntimeError):
    pass


def _endpoints() -> list[dict]:
    cfg = config.load()
    key_name = config.get("gateway.key_name", "AIDUO_API_KEY", cfg)
    return [
        {"name": "AI Duo", "url": config.get("gateway.url", cfg=cfg), "model": config.get("gateway.model", cfg=cfg),
         "key": keychain.get(key_name) if key_name else ""},
        {"name": "Ollama", "url": config.get("ollama.url", cfg=cfg), "model": config.get("ollama.model", cfg=cfg),
         "key": ""},
    ]


def chat(messages: list[dict], model: str | None = None, timeout: float = 120.0) -> dict:
    """OpenAI-совместимый запрос. Возвращает {"text", "via", "model"}."""
    errors = []
    for ep in _endpoints():
        if not ep["url"]:
            continue
        body = json.dumps({"model": model or ep["model"], "messages": messages, "stream": False}).encode()
        headers = {"Content-Type": "application/json"}
        if ep["key"]:
            headers["Authorization"] = "Bearer " + ep["key"]
        req = urllib.request.Request(ep["url"].rstrip("/") + "/chat/completions", data=body, headers=headers)
        try:
            with net.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read())
            text = data["choices"][0]["message"]["content"]
            return {"text": text, "via": ep["name"], "model": data.get("model", model or ep["model"])}
        except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError) as e:
            errors.append(f"{ep['name']} ({ep['url']}): {e}")
    raise AssistantError("Mind не достучался до моделей:\n  " + "\n  ".join(errors) +
                         "\nЗапустите шлюз AI Duo (docker compose up -d в multimodel-agent) или Ollama.")


def ask(question: str, context: str = "", model: str | None = None) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.append({"role": "user", "content": "Контекст:\n" + context})
    messages.append({"role": "user", "content": question})
    return chat(messages, model=model)["text"]
