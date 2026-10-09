"""Mind Store — каталог приложений экосистемы (как App Store).

Каталог — это ``ecosystem.json`` из MindTagSystem: у каждого проекта есть
раздел ``app`` с тем, как его поставить (``install``) и запустить (``run``).
Приложения ставятся из GitHub в ``store.apps_dir`` (по умолчанию
``~/MindTagSystem``) и обновляются через ``git pull``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from . import config
from .paths import IS_WINDOWS, data_dir

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_TTL = 24 * 3600


class StoreError(RuntimeError):
    pass


def _cache_path() -> Path:
    return data_dir() / "catalog.json"


def catalog(refresh: bool = False) -> dict:
    """Реестр экосистемы: локальная копия репозитория → кэш → GitHub."""
    local = REPO_ROOT / "ecosystem.json"
    if local.exists() and not refresh:
        return json.loads(local.read_text(encoding="utf-8"))
    cache = _cache_path()
    if cache.exists() and not refresh and time.time() - cache.stat().st_mtime < CACHE_TTL:
        return json.loads(cache.read_text(encoding="utf-8"))
    try:
        with urllib.request.urlopen(config.get("store.catalog_url"), timeout=15) as resp:
            raw = resp.read()
        data = json.loads(raw)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(raw)
        return data
    except (OSError, ValueError) as e:
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))
        if local.exists():
            return json.loads(local.read_text(encoding="utf-8"))
        raise StoreError(f"Каталог недоступен: {e}") from e


def apps_dir() -> Path:
    return Path(config.get("store.apps_dir")).expanduser()


def platform() -> str:
    return "windows" if IS_WINDOWS else ("macos" if sys.platform == "darwin" else "linux")


def app_path(project: dict) -> Path:
    return apps_dir() / project["repo"].split("/")[-1]


def is_installed(project: dict) -> bool:
    return (app_path(project) / ".git").exists()


def apps(refresh: bool = False) -> list[dict]:
    out = []
    for p in catalog(refresh)["projects"]:
        app = p.get("app") or {}
        out.append({
            "id": p["id"], "name": p["name"], "tagline": p.get("tagline", ""), "layer": p.get("layer", ""),
            "kind": app.get("kind", "app"), "repo": p["repo"], "installed": is_installed(p),
            "installable": bool(app.get("install") or app.get("run")) and
                           platform() in app.get("platforms", [platform()]),
            "note": app.get("note", ""),
        })
    return out


def find(app_id: str) -> dict:
    for p in catalog()["projects"]:
        if app_id.lower() in (p["id"], p["name"].lower()):
            return p
    raise StoreError(f"В каталоге нет «{app_id}». Список: mindkit store list")


def _expand(cmd: str, path: Path) -> str:
    venv = path / ".venv"
    py = venv / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")
    pip = venv / ("Scripts/pip.exe" if IS_WINDOWS else "bin/pip")
    return cmd.replace("{python}", sys.executable).replace("{venv_python}", str(py)).replace("{venv_pip}", str(pip))


def _run(cmd: str, cwd: Path, dry: bool, log) -> None:
    log(f"$ {cmd}")
    if dry:
        return
    res = subprocess.run(cmd, shell=True, cwd=cwd, check=False)
    if res.returncode != 0:
        raise StoreError(f"Команда завершилась с кодом {res.returncode}: {cmd}")


def install(app_id: str, dry: bool = False, log=print) -> Path:
    p = find(app_id)
    app = p.get("app") or {}
    if app.get("kind") in ("os", "web") or not (app.get("install") or app.get("run")):
        raise StoreError(f"{p['name']} не ставится как приложение. {app.get('note', '')} {app.get('get', '')}".strip())
    plats = app.get("platforms") or [platform()]
    if platform() not in plats:
        raise StoreError(f"{p['name']} пока работает только на: {', '.join(plats)}")
    missing = [r for r in app.get("requires", []) if not shutil.which(r)]
    if missing:
        raise StoreError(f"Для {p['name']} сначала поставьте: {', '.join(missing)}")
    path = app_path(p)
    if not is_installed(p):
        path.parent.mkdir(parents=True, exist_ok=True)
        _run(f'git clone https://github.com/{p["repo"]}.git "{path}"', path.parent, dry, log)
    else:
        _run("git pull --ff-only", path, dry, log)
    for step in app.get("install", []):
        _run(_expand(step, path), path, dry, log)
    return path


def run(app_id: str, dry: bool = False, log=print) -> None:
    p = find(app_id)
    app = p.get("app") or {}
    if not app.get("run"):
        raise StoreError(f"У {p['name']} нет команды запуска")
    path = app_path(p)
    if not is_installed(p) and not dry:
        raise StoreError(f"{p['name']} не установлен: mindkit store install {p['id']}")
    cmd = _expand(app["run"], path)
    log(f"$ {cmd}")
    if not dry:
        subprocess.Popen(cmd, shell=True, cwd=path)


def update_all(dry: bool = False, log=print) -> list[str]:
    done = []
    for p in catalog()["projects"]:
        if is_installed(p):
            _run("git pull --ff-only", app_path(p), dry, log)
            done.append(p["id"])
    return done
