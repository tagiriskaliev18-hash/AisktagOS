"""jarvis — ИИ-агент AIsktagOS: сам выполняет задачи на компьютере и в браузере.

  jarvis                        диалог (/new — новая задача, /yes — не спрашивать, /exit — выход)
  jarvis задача…                выполнить одну задачу и выйти
  jarvis -y задача…             не спрашивать подтверждения команд и записи файлов
  jarvis --setup                подключить быструю нейросеть (Groq — ответ за доли секунды) или свою
  jarvis --setup groq КЛЮЧ      то же без вопросов
  jarvis --status               какая модель и сервер используются
  jarvis --update               обновить Джарвиса из последнего релиза AIsktagOS на GitHub

Примеры:
  jarvis найди в ~/Загрузки все PDF больше 10 МБ и перенеси их в ~/Документы/PDF
  jarvis открой github.com/trending и перечисли 5 самых популярных репозиториев на Python
  jarvis посмотри, что у меня на экране, и объясни ошибку
"""
import hashlib
import json
import os
import py_compile
import re
import shutil
import sys
import tarfile
import tempfile
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import readline  # noqa: F401  (история и правка строки)
except ImportError:
    pass

import aisktag_ai as ai  # noqa: E402  (путь к библиотекам задаёт запускатель /usr/bin/jarvis)
import aisktag_jarvis as jv  # noqa: E402

TTY = sys.stdout.isatty()
DIM, BOLD, CYAN, YEL, RED, RESET = (("\033[2m", "\033[1m", "\033[36m", "\033[33m", "\033[31m", "\033[0m")
                                    if TTY else ("",) * 6)
auto_yes = False


def confirm(name: str, what: str) -> bool:
    if auto_yes:
        return True
    if not sys.stdin.isatty():
        print(f"{YEL}  ⚠ пропущено (нет терминала для подтверждения): {what}{RESET}")
        return False
    try:
        ans = input(f"{YEL}  ? Джарвис хочет {what}\n    Разрешить? [д/Н/в — всегда] {RESET}").strip().lower()
    except EOFError:
        return False
    if ans in ("в", "всегда", "a", "always"):
        set_yes(True)
        return True
    return ans in ("д", "да", "y", "yes")


def set_yes(value: bool) -> None:
    global auto_yes
    auto_yes = value
    print(f"{DIM}  (подтверждения {'отключены до конца сеанса' if value else 'включены'}){RESET}")


class Spinner:
    """«⠋ думаю… 12 с» в строке терминала, пока модель считает: видно, что Джарвис не завис."""

    def __init__(self):
        self.thread = None
        self.stop_flag = threading.Event()
        self.label = "думаю"

    def start(self, label: str = "думаю") -> None:
        if not TTY or self.thread:
            return
        self.label = label
        self.stop_flag.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        t0, frames, i = time.time(), "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏", 0
        while not self.stop_flag.wait(0.12):
            sec = int(time.time() - t0)
            hint = " (первый запрос будит модель)" if self.label == "просыпаюсь" and sec > 3 else ""
            sys.stdout.write(f"\r{DIM}  {frames[i % len(frames)]} {self.label}… {sec} с{hint}{RESET}\033[K")
            sys.stdout.flush()
            i += 1
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    def stop(self) -> None:
        if self.thread:
            self.stop_flag.set()
            self.thread.join()
            self.thread = None


spinner = Spinner()
streaming = False


def on_event(kind: str, text: str) -> None:
    global streaming
    spinner.stop()
    if kind == "chunk":
        if not streaming:
            streaming = True
            sys.stdout.write(f"\n{BOLD}Джарвис:{RESET} ")
        sys.stdout.write(text)
        sys.stdout.flush()
        return
    if kind == "done":
        streaming = False
        print("\n")
        return
    if kind == "tool":
        print(f"{CYAN}  ▸ {text}{RESET}")
    elif kind == "result":
        lines = text.strip().splitlines()
        short = "\n    ".join(lines[:6]) + (f"\n    … ещё {len(lines) - 6} строк" if len(lines) > 6 else "")
        print(f"{DIM}    {short}{RESET}")
        spinner.start()                      # дальше снова считает модель
    elif kind == "info":
        print(f"{DIM}  {text}{RESET}")
        spinner.start()
    elif kind == "answer":
        print(f"\n{BOLD}Джарвис:{RESET} {text}\n")


def status() -> None:
    cfg = jv.load_config()
    where = "локальная модель Mind" if ai.is_local(cfg) else cfg["base_url"]
    print(f"Сервер: {where}\nМодель: {cfg['model']}\nЗрение: {'да' if cfg.get('vision') else 'нет (экран читается через распознавание текста)'}")
    print(f"Настройки: {jv.CONF}")
    if ai.is_local(cfg):
        print(f"Состояние локального ИИ: {ai.backend_state()}")
        print("Совет: для сложных задач лучше модель standard или pro (`ai model`), а ещё лучше — сильная облачная "
              "модель (`jarvis --setup`). Модель 1.5B часто ошибается в многошаговых задачах.")


# Быстрые облачные серверы с вызовом инструментов. Модели берутся из списка сервера (/models): первая
# доступная из предпочтительных — списки у провайдеров меняются, жёстко зашитое имя быстро устаревает.
PROVIDERS = {
    "groq": ("Groq — мгновенные ответы (≈0,5 с), бесплатный ключ", "https://api.groq.com/openai/v1",
             "https://console.groq.com/keys",
             ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "moonshotai/kimi-k2-instruct", "qwen/qwen3-32b",
              "openai/gpt-oss-20b", "llama-3.1-8b-instant"]),
    "openrouter": ("OpenRouter — сотни моделей, есть бесплатные", "https://openrouter.ai/api/v1",
                   "https://openrouter.ai/keys",
                   ["openai/gpt-4.1-mini", "google/gemini-2.5-flash", "anthropic/claude-sonnet-4", "openai/gpt-4o-mini"]),
    "openai": ("OpenAI", "https://api.openai.com/v1", "https://platform.openai.com/api-keys",
               ["gpt-4.1-mini", "gpt-4o-mini", "gpt-4.1", "gpt-4o"]),
}


def _api(url: str, key: str, body: dict | None = None, timeout: float = 30) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, method="POST" if body else "GET",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                          "User-Agent": "aisktagos-jarvis"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def connect(provider: str, key: str, model: str = "") -> bool:
    """Проверить ключ, выбрать модель и сохранить в jarvis.json. True — всё работает."""
    title, base, _, preferred = PROVIDERS[provider]
    name = title.split(" —")[0]
    try:
        ids = [m["id"] for m in _api(base + "/models", key).get("data", [])]
    except urllib.error.HTTPError as e:
        print(f"{RED}{name}: ключ не подошёл (ошибка {e.code}). Проверьте, что скопировали его целиком.{RESET}")
        return False
    except (OSError, ValueError) as e:
        print(f"{RED}Нет связи с {base}: {e}{RESET}")
        return False
    model = model or next((m for m in preferred if m in ids), ids[0] if ids else "")
    if not model:
        print(f"{RED}Сервер не вернул ни одной модели.{RESET}")
        return False
    t0 = time.time()
    try:
        _api(base + "/chat/completions", key, {"model": model, "max_tokens": 8,
                                                "messages": [{"role": "user", "content": "Ответь одним словом: ок"}]})
    except (OSError, ValueError) as e:
        print(f"{RED}Модель {model} не ответила: {e}{RESET}")
        return False
    cfg = {}
    try:
        cfg = json.loads(jv.CONF.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    cfg.update(base_url=base, model=model, api_key=key, vision=False)
    jv.CONF.parent.mkdir(parents=True, exist_ok=True)
    jv.CONF.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    jv.CONF.chmod(0o600)
    print(f"{BOLD}Готово:{RESET} Джарвис работает через {name}, модель {model} "
          f"(ответ за {time.time() - t0:.1f} с). Ключ сохранён в {jv.CONF} (доступен только вам).")
    return True


def setup(args: list[str] | None = None) -> None:
    """jarvis --setup                 — выбрать сервер в диалоге
    jarvis --setup groq КЛЮЧ       — сразу подключить (также openrouter, openai, local)"""
    args = args or []
    if args and args[0] == "local":
        cfg = {}
        try:
            cfg = json.loads(jv.CONF.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        for k in ("base_url", "model", "api_key"):
            cfg.pop(k, None)
        jv.CONF.parent.mkdir(parents=True, exist_ok=True)
        jv.CONF.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Джарвис снова работает на встроенной модели (без интернета).")
        return
    if args and args[0] in PROVIDERS:
        key = args[1] if len(args) > 1 else input("Ключ API: ").strip()
        connect(args[0], key, args[2] if len(args) > 2 else "")
        return
    print(f"{BOLD}Какую нейросеть подключить Джарвису?{RESET}")
    names = list(PROVIDERS)
    for i, n in enumerate(names, 1):
        print(f"  {i}. {PROVIDERS[n][0]}")
    print(f"  {len(names) + 1}. Встроенная модель (без интернета, медленнее)")
    print(f"  {len(names) + 2}. Другой OpenAI-совместимый сервер (Ollama, LM Studio, свой)")
    ans = input("Номер [1]: ").strip() or "1"
    if ans == str(len(names) + 1):
        return setup(["local"])
    if ans == str(len(names) + 2):
        cfg = {}
        try:
            cfg = json.loads(jv.CONF.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        cfg["base_url"] = input("Адрес API (например http://localhost:11434/v1): ").strip()
        cfg["model"] = input("Модель: ").strip()
        cfg["api_key"] = input("Ключ API (если нужен): ").strip()
        cfg["vision"] = input("Модель понимает картинки? [д/Н]: ").strip().lower() in ("д", "да", "y")
        jv.CONF.parent.mkdir(parents=True, exist_ok=True)
        jv.CONF.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        jv.CONF.chmod(0o600)
        print(f"Сохранено в {jv.CONF}")
        return
    try:
        prov = names[int(ans) - 1]
    except (ValueError, IndexError):
        print("Нет такого пункта.")
        return
    title, _, keys_url, _ = PROVIDERS[prov]
    print(f"Ключ можно получить бесплатно за минуту: {keys_url}  (войдите и нажмите «Create API Key»)")
    if shutil.which("xdg-open") and input("Открыть эту страницу в браузере? [Д/н]: ").strip().lower() not in ("н", "n"):
        subprocess.Popen(["xdg-open", keys_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    key = input("Вставьте ключ (Ctrl+Shift+V): ").strip()
    if key:
        connect(prov, key)


# --- Обновление без переустановки ОС ----------------------------------------------
# Сборка на GitHub кладёт в каждый релиз AIsktagOS архив с кодом Джарвиса. `jarvis --update` (и тихая
# проверка раз в 12 часов) ставит его в ~/.local/share/aisktagos/jarvis/lib, а /usr/bin/jarvis
# запускает оттуда, если там версия новее встроенной. Так исправления доходят до ярлыка на рабочем столе.
UPDATE_REPO = os.environ.get("JARVIS_UPDATE_REPO", "tagiriskaliev18-hash/AisktagOS")
UPDATE_API = os.environ.get("JARVIS_UPDATE_API", "https://api.github.com")      # для тестов — свой сервер
ASSET = "jarvis-update.tar.gz"
USER_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "aisktagos" / "jarvis"
STAMP = USER_DIR / "last-update-check"


def _ver(text: str) -> tuple:
    m = re.search(r'^VERSION = "([\d.]+)"', text, re.M)
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def _get(url: str, timeout: float = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "aisktagos-jarvis", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def update(quiet: bool = False) -> str | None:
    """Скачать и поставить новую версию. Возвращает номер новой версии или None."""
    def say(msg):
        if not quiet:
            print(msg)
    try:
        USER_DIR.mkdir(parents=True, exist_ok=True)
        STAMP.touch()
        releases = json.loads(_get(f"{UPDATE_API}/repos/{UPDATE_REPO}/releases?per_page=15"))
    except (OSError, ValueError) as e:
        say(f"{RED}Не удалось проверить обновления (нет интернета?): {e}{RESET}")
        return None
    best = None
    for rel in releases:
        names = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
        if ASSET in names and ASSET + ".sha256" in names and (best is None or rel["created_at"] > best[0]):
            best = (rel["created_at"], rel["tag_name"], names[ASSET], names[ASSET + ".sha256"])
    if not best:
        say("Обновлений Джарвиса в релизах пока нет.")
        return None
    _, tag, url, sha_url = best
    with tempfile.TemporaryDirectory(prefix="jarvis-update-") as tmp:
        try:
            data = _get(url, timeout=120)
            expected = _get(sha_url).decode().split()[0].lower()
        except (OSError, IndexError) as e:
            say(f"{RED}Не удалось скачать обновление: {e}{RESET}")
            return None
        if hashlib.sha256(data).hexdigest() != expected:
            say(f"{RED}Обновление повреждено (контрольная сумма не совпала) — пропускаю.{RESET}")
            return None
        arc = Path(tmp) / ASSET
        arc.write_bytes(data)
        new = Path(tmp) / "new"
        with tarfile.open(arc) as t:
            for m in t.getmembers():
                # Только обычные файлы и папки внутри архива — без ссылок и путей «../»
                if not (m.isfile() or m.isdir()) or m.name.startswith(("/", "..")) or "/../" in m.name:
                    say(f"{RED}В архиве обновления недопустимый файл {m.name} — пропускаю.{RESET}")
                    return None
            try:
                t.extractall(new, filter="data")
            except TypeError:                    # Python без фильтров извлечения
                t.extractall(new)
        lib = new / "lib"
        try:
            version = _ver((lib / "aisktag_jarvis.py").read_text(encoding="utf-8"))
            for f in lib.glob("*.py"):
                py_compile.compile(str(f), doraise=True)
        except (OSError, py_compile.PyCompileError) as e:
            say(f"{RED}Обновление не прошло проверку: {e}{RESET}")
            return None
        current = _ver(Path(jv.__file__).read_text(encoding="utf-8"))
        if version <= current:
            say(f"У вас последняя версия Джарвиса ({'.'.join(map(str, current))}).")
            return None
        dest = USER_DIR / "lib"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(lib), str(dest))
        if (new / "bin" / "jarvis").exists():
            shutil.copy2(new / "bin" / "jarvis", USER_DIR / "jarvis")
    vs = ".".join(map(str, version))
    say(f"{BOLD}Джарвис обновлён до {vs}{RESET} (релиз {tag}). Изменения подхватятся при следующем запуске.")
    return vs


def auto_update() -> None:
    """Тихая проверка обновлений раз в 12 часов в фоне; сообщает, только если что-то поставила."""
    if os.environ.get("JARVIS_NO_UPDATE"):
        return
    try:
        if time.time() - STAMP.stat().st_mtime < 12 * 3600:
            return
    except OSError:
        pass

    def run():
        vs = update(quiet=True)
        if vs:
            print(f"\n{DIM}  (скачано обновление Джарвиса {vs} — оно включится при следующем запуске){RESET}")
    threading.Thread(target=run, daemon=True).start()


def run_task(agent: jv.Agent, task: str) -> None:
    global streaming
    spinner.start("просыпаюсь" if ai.is_local(agent.cfg) and ai.backend_state() != "ready" else "думаю")
    try:
        agent.ask(task)
    except ai.AIError as e:
        spinner.stop()
        print(f"\n{RED}Ошибка: {e}{RESET}")
    except KeyboardInterrupt:
        spinner.stop()
        print(f"\n{DIM}  прервано{RESET}")
    finally:
        spinner.stop()
        if streaming:
            streaming = False
            print()


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help"):
        print(__doc__.strip())
        return
    if args and args[0] == "--status":
        return status()
    if args and args[0] == "--setup":
        return setup(args[1:])
    if args and args[0] == "--update":
        update()
        return
    if args and args[0] == "--version":
        print(jv.VERSION, "—", Path(jv.__file__).parent)
        return
    if args and args[0] in ("-y", "--yes"):
        args = args[1:]
        set_yes(True)
    agent = jv.Agent(confirm, on_event)
    try:
        if args:
            run_task(agent, " ".join(args))
            return
        auto_update()
        cfg = jv.load_config()
        if ai.is_local(cfg):
            # Будим локальную модель заранее, пока человек печатает первый вопрос
            threading.Thread(target=jv.server_ctx, args=(cfg,), daemon=True).start()
            offered = USER_DIR / "cloud-offered"
            if not offered.exists() and sys.stdin.isatty():
                USER_DIR.mkdir(parents=True, exist_ok=True)
                offered.touch()
                print(f"{YEL}Встроенная модель работает без интернета, но на процессоре: ответ — секунды, а сложные задачи\n"
                      f"ей не по силам. Для мгновенных ответов и действий подключите Groq (бесплатно, ~1 минута).{RESET}")
                if input("Подключить сейчас? [Д/н]: ").strip().lower() not in ("н", "n", "нет", "no"):
                    setup()
                    agent.cfg = jv.load_config()
                    agent._ctx_checked = False
                print()
            elif ai.list_models().get("active") == "lite":
                print(f"{DIM}Совет: мгновенные ответы и сложные задачи — `jarvis --setup` (Groq, бесплатно). "
                      f"Простые команды («открой Firefox», «громче», «сколько памяти») выполняются сразу.{RESET}\n")
        print(f"{BOLD}Джарвис{RESET} — ИИ-агент AIsktagOS. Опишите задачу; /new — новая тема, /setup — сменить нейросеть, "
              f"/yes — не спрашивать, /exit — выход.\n{DIM}Команды и запись файлов выполняются только с вашего разрешения.{RESET}\n")
        while True:
            try:
                task = input(f"{BOLD}вы ›{RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not task:
                continue
            if task in ("/exit", "/quit", "выход"):
                break
            if task == "/new":
                agent.reset()
                print(f"{DIM}  новая тема{RESET}")
                continue
            if task == "/setup":
                setup()
                agent.cfg = jv.load_config()
                agent._ctx_checked = False
                continue
            if task == "/yes":
                set_yes(not auto_yes)
                continue
            run_task(agent, task)
    finally:
        agent.close()


if __name__ == "__main__":
    main()
