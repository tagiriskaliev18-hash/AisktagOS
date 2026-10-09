"""Быстрые команды Mind (как «Команды» / Shortcuts у Apple).

Команда — цепочка шагов в JSON-файле ``<config_dir>/shortcuts/<имя>.json``::

    {"name": "Объяснить код",
     "description": "Объясняет код из буфера обмена",
     "steps": [
       {"action": "clipboard.get"},
       {"action": "ask", "prompt": "Объясни этот код:\\n{{prev}}"},
       {"action": "notify", "title": "Mind", "body": "{{prev}}"}
     ]}

Результат шага доступен следующему как ``{{prev}}``, входной текст — как
``{{input}}``, а шаг с ``"save": "имя"`` сохраняет результат в ``{{имя}}``.

Шаги: ``clipboard.get``, ``clipboard.set``, ``text``, ``ask`` (ассистент
Mind), ``notify``, ``notify.devices`` (на все устройства), ``shell``,
``open``, ``handoff``, ``send_clipboard``, ``app.run`` (Mind Store),
``shortcut`` (вложенная команда).
"""

from __future__ import annotations

import json
import re
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable

from . import assistant, clipboard, config, link, notify
from .paths import config_dir

BUILTIN: list[dict] = [
    {"name": "Объяснить код", "description": "Mind объясняет код из буфера обмена",
     "steps": [{"action": "clipboard.get"},
               {"action": "ask", "prompt": "Объясни, что делает этот код, и найди ошибки:\n\n{{prev}}"},
               {"action": "clipboard.set"},
               {"action": "notify", "title": "Mind объяснил код", "body": "Ответ в буфере обмена"}]},
    {"name": "Перевести буфер", "description": "Переводит текст из буфера на русский или английский",
     "steps": [{"action": "clipboard.get"},
               {"action": "ask", "prompt": "Переведи на русский (если текст русский — на английский). "
                                           "Выведи только перевод:\n\n{{prev}}"},
               {"action": "clipboard.set"},
               {"action": "notify", "title": "Перевод готов", "body": "{{prev}}"}]},
    {"name": "Буфер на устройства", "description": "Отправляет буфер обмена на все свои устройства",
     "steps": [{"action": "clipboard.get"}, {"action": "send_clipboard"},
               {"action": "notify", "title": "MindLink", "body": "Буфер отправлен"}]},
    {"name": "Запустить ИИ-ядро", "description": "Запускает шлюз AI Duo из Mind Store",
     "steps": [{"action": "app.run", "app": "multimodel-agent"},
               {"action": "notify", "title": "ИИ-ядро", "body": "AI Duo запускается на :8000"}]},
    {"name": "Commit-сообщение", "description": "Mind пишет сообщение коммита по git diff в текущей папке",
     "steps": [{"action": "shell", "command": "git diff --staged"},
               {"action": "ask", "prompt": "Напиши короткое сообщение коммита на русском по этому diff. "
                                           "Только текст сообщения:\n\n{{prev}}"},
               {"action": "clipboard.set"},
               {"action": "notify", "title": "Сообщение коммита в буфере", "body": "{{prev}}"}]},
]

VAR_RE = re.compile(r"\{\{\s*([\w.-]+)\s*\}\}")


class ShortcutError(RuntimeError):
    pass


def user_dir() -> Path:
    return config_dir() / "shortcuts"


def _slug(name: str) -> str:
    return re.sub(r"[^\w.-]+", "-", name.strip()).strip("-").lower() or "shortcut"


def list_all() -> list[dict]:
    items = {sc["name"]: dict(sc, builtin=True) for sc in BUILTIN}
    d = user_dir()
    if d.is_dir():
        for f in sorted(d.glob("*.json")):
            try:
                sc = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(sc, dict) and sc.get("name") and isinstance(sc.get("steps"), list):
                items[sc["name"]] = dict(sc, builtin=False, file=str(f))
    return list(items.values())


def get(name: str) -> dict:
    for sc in list_all():
        if sc["name"].lower() == name.lower() or _slug(sc["name"]) == _slug(name):
            return sc
    raise ShortcutError(f"Нет быстрой команды «{name}». Список: mindkit shortcuts list")


def save(sc: dict) -> Path:
    if not sc.get("name") or not isinstance(sc.get("steps"), list):
        raise ShortcutError("У команды должны быть name и steps")
    for step in sc["steps"]:
        if step.get("action") not in ACTIONS:
            raise ShortcutError(f"Неизвестный шаг: {step.get('action')}")
    path = user_dir() / f"{_slug(sc['name'])}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: v for k, v in sc.items() if k not in ("builtin", "file")}
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def delete(name: str) -> bool:
    path = user_dir() / f"{_slug(name)}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def _fill(value: Any, env: dict) -> Any:
    if isinstance(value, str):
        return VAR_RE.sub(lambda m: str(env.get(m.group(1), "")), value)
    if isinstance(value, list):
        return [_fill(v, env) for v in value]
    if isinstance(value, dict):
        return {k: _fill(v, env) for k, v in value.items()}
    return value


def _shell(step, prev):
    res = subprocess.run(step["command"], shell=True, capture_output=True, text=True,
                         cwd=Path(step.get("cwd", ".")).expanduser(), timeout=step.get("timeout", 300))
    if res.returncode != 0 and not step.get("ignore_errors"):
        raise ShortcutError(f"shell: код {res.returncode}: {res.stderr.strip()[:300]}")
    return res.stdout.rstrip("\n")


def _open(step, prev):
    target = step.get("target") or prev
    if re.match(r"^[a-z]+://", target):
        link._open_url(target)
    else:
        link._open_file(target)
    return target


def _app_run(step, prev):
    from . import store
    store.run(step["app"], log=lambda *_: None)
    return step["app"]


ACTIONS: dict[str, Callable[[dict, str], Any]] = {
    "clipboard.get": lambda step, prev: clipboard.get(),
    "clipboard.set": lambda step, prev: (clipboard.set(step.get("text", prev)), step.get("text", prev))[1],
    "text": lambda step, prev: step.get("text", ""),
    "ask": lambda step, prev: assistant.ask(step.get("prompt") or prev, model=step.get("model")),
    "notify": lambda step, prev: (notify.send(step.get("title", "Быстрая команда"), step.get("body", prev)[:500],
                                              app="Быстрые команды"), prev)[1],
    "notify.devices": lambda step, prev: (link.send_notification(step.get("title", "Mind"),
                                                                 step.get("body", prev)[:500],
                                                                 to=step.get("to")), prev)[1],
    "shell": _shell,
    "open": _open,
    "handoff": lambda step, prev: (link.handoff(link.make_activity(
        step.get("kind", "text"), step.get("title", ""), url=step.get("url", ""), text=step.get("text", prev),
        path=step.get("path", "")), to=step.get("to")), prev)[1],
    "send_clipboard": lambda step, prev: (link.send_clipboard(step.get("text", prev), to=step.get("to")), prev)[1],
    "app.run": _app_run,
    "shortcut": lambda step, prev: run(step["name"], step.get("input", prev), depth=_depth.n + 1),
}

_depth = threading.local()


def run(name_or_sc: str | dict, input_text: str = "", log: Callable[[str], Any] | None = None,
        depth: int = 0) -> str:
    if depth > 5:
        raise ShortcutError("Слишком глубокая вложенность команд")
    sc = get(name_or_sc) if isinstance(name_or_sc, str) else name_or_sc
    outer = getattr(_depth, "n", 0)
    _depth.n = depth
    try:
        return _run_steps(sc, input_text, log)
    finally:
        _depth.n = outer


def _run_steps(sc: dict, input_text: str, log) -> str:
    env: dict[str, Any] = {"input": input_text, "prev": input_text, "device": config.device()["name"]}
    for i, raw in enumerate(sc["steps"], 1):
        action = raw.get("action")
        fn = ACTIONS.get(action)
        if not fn:
            raise ShortcutError(f"Шаг {i}: неизвестное действие {action}")
        step = _fill(raw, env)
        if log:
            log(f"[{i}/{len(sc['steps'])}] {action}")
        result = fn(step, str(env["prev"]))
        env["prev"] = "" if result is None else result
        if raw.get("save"):
            env[raw["save"]] = env["prev"]
    return str(env["prev"])
