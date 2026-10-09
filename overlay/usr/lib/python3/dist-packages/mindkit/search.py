"""Mind Search — поиск по всему сразу (как Spotlight).

Один запрос ищет среди приложений экосистемы, программ системы, быстрых
команд, настроек, имён ключей, уведомлений, входящих Handoff и файлов
в папках проектов (``search.roots``). С ``content=True`` заглядывает
и внутрь текстовых файлов.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import config, keychain, link, notify
from .paths import IS_WINDOWS

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".cache", "dist", "build",
             ".idea", ".mypy_cache", ".pytest_cache", "target", ".next"}
MAX_FILES = 50_000
TEXT_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".md", ".txt", ".json", ".toml", ".yaml", ".yml", ".sh",
            ".ps1", ".bat", ".html", ".css", ".qml", ".c", ".h", ".cpp", ".rs", ".go", ".java", ".kt",
            ".cs", ".sql", ".ini", ".cfg", ".env.example", ".desktop", ".xml", ".csv"}


def score(query: str, text: str) -> float:
    """0 — не подходит. Точное совпадение > начало > подстрока > буквы по порядку."""
    q, t = query.lower().strip(), text.lower()
    if not q or not t:
        return 0.0
    if t == q:
        return 100.0
    if t.startswith(q):
        return 80.0 - min(len(t) - len(q), 30) * 0.3
    if any(w.startswith(q) for w in t.replace("-", " ").replace("_", " ").replace(".", " ").split()):
        return 65.0
    if q in t:
        return 50.0 - min(t.index(q), 30) * 0.5
    pos = 0
    for ch in q:
        pos = t.find(ch, pos)
        if pos < 0:
            return 0.0
        pos += 1
    return 20.0 * len(q) / max(len(t), 1) + 5.0


def _item(kind: str, title: str, subtitle: str, action: dict, s: float) -> dict:
    return {"kind": kind, "title": title, "subtitle": subtitle, "action": action, "score": round(s, 1)}


def _apps(q: str) -> list[dict]:
    from . import store
    out = []
    try:
        apps = store.apps()
    except store.StoreError:
        return out
    for a in apps:
        s = max(score(q, a["name"]), score(q, a["id"]), score(q, a["tagline"]) * 0.6)
        if s:
            state = "установлено" if a["installed"] else "в Mind Store"
            out.append(_item("app", a["name"], f"{a['tagline']} · {state}",
                             {"store": a["id"]}, s + 5))
    return out


def _desktop_apps(q: str) -> list[dict]:
    out = []
    if IS_WINDOWS:
        dirs = [Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
                Path(os.environ.get("ProgramData", "C:/ProgramData")) / "Microsoft/Windows/Start Menu/Programs"]
        for d in dirs:
            if d.is_dir():
                for lnk in d.rglob("*.lnk"):
                    s = score(q, lnk.stem)
                    if s:
                        out.append(_item("program", lnk.stem, "Программа", {"open": str(lnk)}, s))
        return out
    dirs = [Path("/usr/share/applications"), Path.home() / ".local/share/applications"]
    for d in dirs:
        if not d.is_dir():
            continue
        for f in d.glob("*.desktop"):
            name, comment, hidden = f.stem, "", False
            try:
                for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.startswith("Name=") and name == f.stem:
                        name = line[5:]
                    elif line.startswith("Name[ru]="):
                        name = line[9:]
                    elif line.startswith("Comment=") and not comment:
                        comment = line[8:]
                    elif line.strip() in ("NoDisplay=true", "Hidden=true"):
                        hidden = True
                    elif line.startswith("[") and line.strip() != "[Desktop Entry]":
                        break
            except OSError:
                continue
            if hidden:
                continue
            s = max(score(q, name), score(q, f.stem) * 0.9)
            if s:
                out.append(_item("program", name, comment or "Программа", {"launch": f.name}, s))
    return out


def _shortcuts(q: str) -> list[dict]:
    from . import shortcuts
    out = []
    for sc in shortcuts.list_all():
        s = max(score(q, sc["name"]), score(q, sc.get("description", "")) * 0.6)
        if s:
            out.append(_item("shortcut", sc["name"], sc.get("description", "Быстрая команда"),
                             {"shortcut": sc["name"]}, s + 3))
    return out


def _settings(q: str) -> list[dict]:
    out = []

    def walk(node, prefix=""):
        for k, v in node.items():
            key = f"{prefix}{k}"
            if isinstance(v, dict):
                walk(v, key + ".")
            else:
                s = score(q, key)
                if s:
                    out.append(_item("setting", key, f"Настройка = {v}", {"setting": key}, s * 0.8))

    walk(config.load())
    for name in keychain.names():
        s = score(q, name)
        if s:
            out.append(_item("key", name, "Ключ в связке Mind", {"keychain": name}, s * 0.8))
    return out


def _history(q: str) -> list[dict]:
    out = []
    for n in notify.history(100):
        s = max(score(q, n.get("title", "")), score(q, n.get("body", "")) * 0.7)
        if s:
            out.append(_item("notification", n.get("title", ""), n.get("body", ""), {}, s * 0.6))
    for i, act in enumerate(link.inbox()):
        text = act.get("title") or act.get("url") or act.get("text", "")
        s = score(q, text)
        if s:
            out.append(_item("handoff", text, f"Handoff с «{act.get('from', '?')}»", {"resume": i}, s * 0.9))
    return out


def iter_files(roots: list[str] | None = None):
    count = 0
    for root in roots if roots is not None else config.get("search.roots", []):
        base = Path(root).expanduser()
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for fn in filenames:
                yield Path(dirpath) / fn
                count += 1
                if count >= MAX_FILES:
                    return


def _files(q: str, content: bool, roots: list[str] | None) -> list[dict]:
    out = []
    max_bytes = int(float(config.get("search.max_file_mb", 2)) * 1024 * 1024)
    ql = q.lower()
    for path in iter_files(roots):
        s = score(q, path.name)
        if s:
            out.append(_item("file", path.name, str(path.parent), {"open": str(path)}, s * 0.9))
            continue
        if content and path.suffix.lower() in TEXT_EXT:
            try:
                if path.stat().st_size > max_bytes:
                    continue
                with path.open(encoding="utf-8", errors="ignore") as f:
                    for no, line in enumerate(f, 1):
                        if ql in line.lower():
                            out.append(_item("text", f"{path.name}:{no}", line.strip()[:120],
                                             {"open": str(path), "line": no}, 30))
                            break
            except OSError:
                continue
    return out


def search(query: str, limit: int = 20, content: bool = False, kinds: set[str] | None = None,
           roots: list[str] | None = None) -> list[dict]:
    sources = {
        "app": lambda: _apps(query),
        "program": lambda: _desktop_apps(query),
        "shortcut": lambda: _shortcuts(query),
        "setting": lambda: _settings(query),
        "history": lambda: _history(query),
        "file": lambda: _files(query, content, roots),
    }
    results: list[dict] = []
    for name, fn in sources.items():
        if kinds and name not in kinds:
            continue
        try:
            results.extend(fn())
        except Exception:  # noqa: BLE001 — один сломанный источник не ломает поиск
            continue
    results.sort(key=lambda r: -r["score"])
    return results[:limit]
