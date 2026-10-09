"""Связка ключей Mind — одно место для ключей API всех проектов экосистемы.

Ключ кладётся один раз (``mindkit keychain set GROQ_API_KEY``), а дальше
его видят Mind IDE, шлюз AI Duo, ITIS Browser и остальные проекты:
они вызывают ``keychain.load_env()`` при старте, и ключи из связки
становятся переменными окружения (уже заданные переменные не трогаются).

Где лежат ключи:

* если установлен пакет ``keyring`` — в системном хранилище
  (Secret Service / KWallet на Linux, Диспетчер учётных данных Windows,
  Связка ключей macOS); рядом хранится только список имён;
* иначе — в файле ``<config_dir>/keychain.json`` с доступом только
  для владельца, как ``~/.netrc`` или ``gh/hosts.yml``.

Переменная ``MINDKIT_KEYCHAIN=file`` принудительно включает файл.
"""

from __future__ import annotations

import builtins
import json
import os
import re

from .paths import config_dir, private_write

SERVICE = "MindTagSystem"
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,127}$")


def _keyring():
    if os.environ.get("MINDKIT_KEYCHAIN", "").lower() == "file":
        return None
    try:
        import keyring  # type: ignore
        from keyring.backends import fail  # type: ignore
    except ImportError:
        return None
    try:
        if isinstance(keyring.get_keyring(), fail.Keyring):
            return None
    except Exception:  # noqa: BLE001 — сломанный бэкенд = нет бэкенда
        return None
    return keyring


def backend() -> str:
    return "system" if _keyring() else "file"


def _vault_path():
    return config_dir() / "keychain.json"


def _read_vault() -> dict:
    path = _vault_path()
    if not path.exists():
        return {"names": [], "secrets": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"names": [], "secrets": {}}
    data.setdefault("names", [])
    data.setdefault("secrets", {})
    return data


def _write_vault(data: dict) -> None:
    data["names"] = sorted(builtins.set(data["names"]))
    private_write(_vault_path(), json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def _check(name: str) -> str:
    if not NAME_RE.match(name or ""):
        raise ValueError(f"Недопустимое имя ключа: {name!r}")
    return name


def set(name: str, value: str) -> None:  # noqa: A001
    _check(name)
    data = _read_vault()
    kr = _keyring()
    if kr:
        kr.set_password(SERVICE, name, value)
        data["secrets"].pop(name, None)
    else:
        data["secrets"][name] = value
    data["names"].append(name)
    _write_vault(data)


def get(name: str, default: str = "") -> str:
    _check(name)
    kr = _keyring()
    if kr:
        try:
            value = kr.get_password(SERVICE, name)
        except Exception:  # noqa: BLE001
            value = None
        if value:
            return value
    return _read_vault()["secrets"].get(name, default)


def delete(name: str) -> bool:
    _check(name)
    data = _read_vault()
    found = name in data["names"] or name in data["secrets"]
    kr = _keyring()
    if kr:
        try:
            kr.delete_password(SERVICE, name)
            found = True
        except Exception:  # noqa: BLE001
            pass
    data["secrets"].pop(name, None)
    data["names"] = [n for n in data["names"] if n != name]
    _write_vault(data)
    return found


def names() -> list[str]:
    data = _read_vault()
    return sorted(builtins.set(data["names"]) | builtins.set(data["secrets"]))


def load_env(only: list[str] | None = None, override: bool = False) -> list[str]:
    """Переносит ключи из связки в os.environ. Возвращает имена, которые выставил."""
    done = []
    for name in only or names():
        if not override and os.environ.get(name):
            continue
        value = get(name)
        if value:
            os.environ[name] = value
            done.append(name)
    return done


def mask(value: str) -> str:
    if len(value) <= 8:
        return "•" * len(value)
    return value[:4] + "…" + value[-4:]
