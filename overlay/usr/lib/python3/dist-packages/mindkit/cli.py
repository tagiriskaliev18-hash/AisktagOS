"""Командная строка MindKit: ``mindkit <команда>``."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

from . import __version__, assistant, clipboard, config, design, keychain, link, notify, search, shortcuts, store


def _piped() -> bool:
    """Данные подали через | или < (а не просто не терминал)."""
    import os
    import stat
    try:
        mode = os.fstat(sys.stdin.fileno()).st_mode
    except (OSError, ValueError, AttributeError):
        return False
    return stat.S_ISFIFO(mode) or stat.S_ISREG(mode)


def _print_json(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _report(result: dict[str, str]) -> int:
    if not result:
        print("Нет известных устройств. Найдите их: mindkit link devices --scan")
        return 1
    bad = 0
    for name, state in result.items():
        print(f"  {'✓' if state == 'ok' else '✗'} {name}" + ("" if state == "ok" else f": {state}"))
        bad += state != "ok"
    return 1 if bad == len(result) else 0


# ── status ──────────────────────────────────────────────────────────────

def cmd_status(a) -> int:
    st = link.status()
    print(f"MindKit {__version__} · устройство «{st['device']['name']}» ({st['device']['id']})")
    print(f"  Связка ключей: {'системное хранилище' if st['keychain'] == 'system' else 'файл (только владелец)'}"
          f", ключей: {len(keychain.names())}")
    print(f"  Буфер обмена:  {st['clipboard']}")
    print(f"  MindLink:      {'настроен' if st['account'] else 'не настроен (mindkit link init)'}, порт {st['port']}, "
          f"{'шифрование AES-GCM' if st['encryption'] else 'без шифрования (pip install cryptography)'}")
    print(f"  Устройства:    {', '.join(p['name'] for p in st['peers'].values()) or 'нет'}")
    print(f"  Шлюз ИИ:       {config.get('gateway.url')} → запасной {config.get('ollama.url')}")
    return 0


# ── config ──────────────────────────────────────────────────────────────

def cmd_config(a) -> int:
    if a.action == "list":
        _print_json(config.load())
    elif a.action == "get":
        _print_json(config.get(a.key))
    elif a.action == "set":
        try:
            value = json.loads(a.value)
        except ValueError:
            value = a.value
        config.set(a.key, value)
        print(f"{a.key} = {json.dumps(value, ensure_ascii=False)}")
    return 0


# ── keychain ────────────────────────────────────────────────────────────

def cmd_keychain(a) -> int:
    if a.action == "list":
        for name in keychain.names():
            print(f"  {name:<28} {keychain.mask(keychain.get(name))}")
        if not keychain.names():
            print("Связка ключей пуста. Добавьте: mindkit keychain set GROQ_API_KEY")
    elif a.action == "set":
        value = a.value
        if value is None:
            value = sys.stdin.readline().strip() if _piped() else getpass.getpass(f"{a.name}: ")
        if not value:
            print("Пустое значение — ничего не сохранено", file=sys.stderr)
            return 1
        keychain.set(a.name, value)
        print(f"✓ {a.name} сохранён ({keychain.backend()})")
    elif a.action == "get":
        value = keychain.get(a.name)
        if not value:
            return 1
        print(value if a.show else keychain.mask(value))
    elif a.action == "delete":
        print("✓ удалён" if keychain.delete(a.name) else "нет такого ключа")
    elif a.action == "env":
        # Для оболочки: eval "$(mindkit keychain env)"
        for name in keychain.names():
            value = keychain.get(name).replace("'", "'\"'\"'")
            print(f"export {name}='{value}'" if not a.powershell else f"$env:{name}='{value}'")
    elif a.action == "import":
        added = 0
        for line in Path(a.file).expanduser().read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.removeprefix("export ").split("=", 1)
            name, value = name.strip(), value.strip().strip("'\"")
            if value and keychain.NAME_RE.match(name) and ("KEY" in name or "TOKEN" in name or "SECRET" in name
                                                            or a.all):
                keychain.set(name, value)
                added += 1
                print(f"  + {name}")
        print(f"✓ импортировано ключей: {added}")
    return 0


# ── MindLink ────────────────────────────────────────────────────────────

def cmd_link(a) -> int:
    if a.action == "init":
        key = link.init_account(force=a.force)
        print("Ключ аккаунта MindLink (введите его на других своих устройствах):\n")
        print(f"  mindkit link join {key}\n")
        print("Храните его как пароль: с ним устройство получает доступ к буферу и файлам.")
    elif a.action == "join":
        link.join_account(a.key)
        print("✓ Устройство вошло в аккаунт. Запустите службу: mindkit link daemon")
    elif a.action == "key":
        key = keychain.get(link.ACCOUNT_KEY_NAME)
        print(key or "Ключа нет: mindkit link init")
    elif a.action == "devices":
        if a.scan:
            found = link.discover(timeout=a.timeout)
            print(f"Найдено в сети: {len(found)}")
        for pid, p in link.peers().items():
            print(f"  {p['name']:<20} {p['host']}:{p['port']}  ({pid})")
        if not link.peers():
            print("Устройств нет. Запустите «mindkit link daemon» на других устройствах и повторите с --scan")
    elif a.action == "add":
        host, _, port = a.address.partition(":")
        peer = {"host": host, "port": int(port or config.get("link.port")), "name": a.address}
        info = link.verify_peer(peer["host"], peer["port"])
        if not info:
            print(f"✗ {a.address}: не отвечает или это не ваше устройство", file=sys.stderr)
            return 1
        print(f"✓ добавлено «{info['name']}»")
    elif a.action == "forget":
        print("✓ забыто" if link.forget_peer(a.device) else "нет такого устройства")
    elif a.action == "ping":
        return _report(link.ping(a.to))
    elif a.action == "autostart":
        print(link.autostart(a.state == "on"))
    elif a.action == "daemon":
        if not link.account_key():
            if not a.wait:
                print("Сначала: mindkit link init (первое устройство) или mindkit link join КЛЮЧ", file=sys.stderr)
                return 1
            # Служба ОС стартует сразу, а работать начинает, когда устройство войдёт в аккаунт
            import time as _t
            while not link.account_key():
                _t.sleep(15)
        d = link.Daemon(port=a.port, clipboard_sync=False if a.no_clipboard else None)
        print(f"MindLink слушает порт {d.port}" + ("" if link.encryption_available() else
                                                    " (без шифрования: pip install cryptography)"))
        d.serve_forever()
    return 0


def cmd_copy(a) -> int:
    text = " ".join(a.text) if a.text else (sys.stdin.read() if _piped() else clipboard.get())
    clipboard.set(text)
    return _report(link.send_clipboard(text, to=a.to))


def cmd_handoff(a) -> int:
    if a.action == "list":
        for i, act in enumerate(link.inbox()):
            what = act.get("url") or act.get("local_path") or act.get("path") or act.get("text", "")[:60]
            print(f"  [{i}] {act.get('kind'):<4} {act.get('title') or ''} {what}  ← {act.get('from', '?')}")
        if not link.inbox():
            print("Входящих Handoff нет")
        return 0
    if a.action == "resume":
        act = link.resume(a.index)
        if not act:
            print("Нечего продолжать")
            return 1
        print(f"✓ открыто: {act.get('title') or act.get('url') or act.get('kind')}")
        return 0
    if a.action == "url":
        act = link.make_activity("url", a.title or a.value, url=a.value)
    elif a.action == "file":
        act = link.make_activity("file", a.title or "", path=a.value, line=a.line)
    else:
        act = link.make_activity("text", a.title or a.value[:40], text=a.value)
    return _report(link.handoff(act, to=a.to))


def cmd_drop(a) -> int:
    code = 0
    for f in a.files:
        print(f"MindDrop: {f}")
        code |= _report(link.drop(f, to=a.to))
    return code


def cmd_notify(a) -> int:
    if a.devices:
        return _report(link.send_notification(a.title, a.body or "", to=a.to))
    notify.send(a.title, a.body or "", app=a.app)
    return 0


def cmd_notifications(a) -> int:
    if a.clear:
        notify.clear()
        return 0
    import time as _t
    for n in notify.history(a.limit):
        when = _t.strftime("%d.%m %H:%M", _t.localtime(n["time"]))
        src = f" ← {n['source']}" if n.get("source") else ""
        print(f"  {when}  [{n.get('app')}] {n.get('title')}: {n.get('body', '')}{src}")
    return 0


# ── поиск, команды, ассистент, магазин, дизайн ──────────────────────────

ICONS = {"app": "◆", "program": "▣", "shortcut": "⚡", "setting": "⚙", "key": "🔑", "notification": "🔔",
         "handoff": "⇄", "file": "📄", "text": "≡"}


def cmd_search(a) -> int:
    res = search.search(" ".join(a.query), limit=a.limit, content=a.content,
                        roots=a.root or None)
    if a.json:
        _print_json(res)
        return 0
    for r in res:
        print(f"  {ICONS.get(r['kind'], '•')} {r['title']}  — {r['subtitle']}")
    if not res:
        print("Ничего не найдено")
    return 0 if res else 1


def cmd_shortcuts(a) -> int:
    if a.action == "list":
        for sc in shortcuts.list_all():
            print(f"  ⚡ {sc['name']:<24} {sc.get('description', '')}{'' if sc.get('builtin') else '  (своя)'}")
    elif a.action == "show":
        _print_json(shortcuts.get(a.name))
    elif a.action == "run":
        out = shortcuts.run(a.name, " ".join(a.input), log=lambda m: print(m, file=sys.stderr))
        print(out)
    elif a.action == "add":
        sc = json.loads(Path(a.file).read_text(encoding="utf-8"))
        print(f"✓ сохранено: {shortcuts.save(sc)}")
    elif a.action == "delete":
        print("✓ удалено" if shortcuts.delete(a.name) else "нет такой своей команды")
    return 0


def cmd_ask(a) -> int:
    context = sys.stdin.read() if _piped() else ""
    try:
        print(assistant.ask(" ".join(a.question), context=context, model=a.model))
    except assistant.AssistantError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


def cmd_store(a) -> int:
    try:
        if a.action == "list":
            for app in store.apps(refresh=a.refresh):
                mark = "✓" if app["installed"] else ("+" if app["installable"] else " ")
                print(f"  {mark} {app['id']:<26} {app['tagline']}")
            print("\n✓ установлено, + можно поставить: mindkit store install <id>")
        elif a.action == "install":
            path = store.install(a.app, dry=a.dry_run)
            print(f"✓ {a.app}: {path}")
        elif a.action == "run":
            store.run(a.app, dry=a.dry_run)
        elif a.action == "update":
            print("Обновлено:", ", ".join(store.update_all(dry=a.dry_run)) or "нечего")
    except store.StoreError as e:
        print(e, file=sys.stderr)
        return 1
    return 0


def cmd_design(a) -> int:
    print(design.css() if a.format == "css" else design.qss() if a.format == "qss"
          else json.dumps(design.tokens(), ensure_ascii=False, indent=2), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mindkit", description="Общие службы экосистемы MindTagSystem")
    p.add_argument("--version", action="version", version=f"MindKit {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="состояние MindKit на этом устройстве").set_defaults(fn=cmd_status)

    c = sub.add_parser("config", help="единые настройки экосистемы")
    cs = c.add_subparsers(dest="action", required=True)
    cs.add_parser("list")
    cs.add_parser("get").add_argument("key")
    s = cs.add_parser("set")
    s.add_argument("key")
    s.add_argument("value")
    c.set_defaults(fn=cmd_config)

    k = sub.add_parser("keychain", help="связка ключей Mind")
    ks = k.add_subparsers(dest="action", required=True)
    ks.add_parser("list")
    s = ks.add_parser("set")
    s.add_argument("name")
    s.add_argument("value", nargs="?")
    s = ks.add_parser("get")
    s.add_argument("name")
    s.add_argument("--show", action="store_true", help="показать целиком")
    ks.add_parser("delete").add_argument("name")
    s = ks.add_parser("env", help="ключи как переменные окружения")
    s.add_argument("--powershell", action="store_true")
    s = ks.add_parser("import", help="перенести ключи из .env")
    s.add_argument("file")
    s.add_argument("--all", action="store_true", help="все переменные, а не только *KEY*/*TOKEN*/*SECRET*")
    k.set_defaults(fn=cmd_keychain)

    ln = sub.add_parser("link", help="MindLink: устройства владельца")
    ls = ln.add_subparsers(dest="action", required=True)
    ls.add_parser("init").add_argument("--force", action="store_true")
    ls.add_parser("join").add_argument("key")
    ls.add_parser("key")
    s = ls.add_parser("devices")
    s.add_argument("--scan", action="store_true")
    s.add_argument("--timeout", type=float, default=2.0)
    ls.add_parser("add").add_argument("address", help="host[:port]")
    ls.add_parser("forget").add_argument("device")
    ls.add_parser("ping").add_argument("--to")
    s = ls.add_parser("daemon")
    s.add_argument("--port", type=int)
    s.add_argument("--no-clipboard", action="store_true")
    s.add_argument("--wait", action="store_true", help="ждать, пока устройство войдёт в аккаунт")
    ls.add_parser("autostart", help="запускать службу при входе").add_argument("state", choices=["on", "off"])
    ln.set_defaults(fn=cmd_link)

    s = sub.add_parser("copy", help="общий буфер: отправить текст на устройства")
    s.add_argument("text", nargs="*")
    s.add_argument("--to")
    s.set_defaults(fn=cmd_copy)

    h = sub.add_parser("handoff", help="продолжить на другом устройстве")
    hs = h.add_subparsers(dest="action", required=True)
    for kind in ("url", "file", "text"):
        s = hs.add_parser(kind)
        s.add_argument("value")
        s.add_argument("--to")
        s.add_argument("--title")
        if kind == "file":
            s.add_argument("--line", type=int)
    hs.add_parser("list")
    hs.add_parser("resume").add_argument("index", nargs="?", type=int, default=0)
    h.set_defaults(fn=cmd_handoff)

    s = sub.add_parser("drop", help="MindDrop: отправить файлы")
    s.add_argument("files", nargs="+")
    s.add_argument("--to")
    s.set_defaults(fn=cmd_drop)

    s = sub.add_parser("notify", help="показать уведомление")
    s.add_argument("title")
    s.add_argument("body", nargs="?")
    s.add_argument("--app", default="MindTagSystem")
    s.add_argument("--devices", action="store_true", help="на всех своих устройствах")
    s.add_argument("--to")
    s.set_defaults(fn=cmd_notify)

    s = sub.add_parser("notifications", help="история уведомлений")
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--clear", action="store_true")
    s.set_defaults(fn=cmd_notifications)

    s = sub.add_parser("search", help="Mind Search: поиск по всему")
    s.add_argument("query", nargs="+")
    s.add_argument("--content", action="store_true", help="искать и внутри файлов")
    s.add_argument("--root", action="append", help="папка поиска (можно несколько)")
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_search)

    sc = sub.add_parser("shortcuts", help="быстрые команды")
    scs = sc.add_subparsers(dest="action", required=True)
    scs.add_parser("list")
    scs.add_parser("show").add_argument("name")
    s = scs.add_parser("run")
    s.add_argument("name")
    s.add_argument("input", nargs="*")
    scs.add_parser("add").add_argument("file")
    scs.add_parser("delete").add_argument("name")
    sc.set_defaults(fn=cmd_shortcuts)

    s = sub.add_parser("ask", help="спросить ассистента Mind")
    s.add_argument("question", nargs="+")
    s.add_argument("--model")
    s.set_defaults(fn=cmd_ask)

    st = sub.add_parser("store", help="Mind Store: приложения экосистемы")
    sts = st.add_subparsers(dest="action", required=True)
    sts.add_parser("list").add_argument("--refresh", action="store_true")
    for act in ("install", "run"):
        s = sts.add_parser(act)
        s.add_argument("app")
        s.add_argument("--dry-run", action="store_true")
    sts.add_parser("update").add_argument("--dry-run", action="store_true")
    st.set_defaults(fn=cmd_store)

    s = sub.add_parser("design", help="дизайн Aurora для своих интерфейсов")
    s.add_argument("format", choices=["css", "qss", "json"])
    s.set_defaults(fn=cmd_design)
    return p


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        return int(args.fn(args) or 0)
    except (link.LinkError, shortcuts.ShortcutError, ValueError) as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
