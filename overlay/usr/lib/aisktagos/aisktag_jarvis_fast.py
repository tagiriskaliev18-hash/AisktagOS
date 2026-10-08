"""Мгновенные команды Джарвиса — без нейросети, за доли секунды.

Частые действия («открой Firefox», «громче», «скриншот», «сколько памяти», «найди в интернете …»,
«напомни через 5 минут …») распознаются по словам и выполняются сразу. Всё, что не подошло, уходит модели.

    handle(text, tools, confirm) -> str | None     # ответ пользователю или None (пусть решает модель)
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import urllib.parse
from pathlib import Path

# Вежливые слова и обращение не мешают распознаванию
_PREFIX = re.compile(r"^(?:(?:эй|слушай|окей|ок)[, ]+)?(?:джарвис|jarvis)?[,!. ]*(?:пожалуйста[, ]+)?", re.I)
_TAIL = re.compile(r"[,.!?]*\s*(?:пожалуйста|плиз|please)?[.!?]*$", re.I)

SITES = {
    "ютуб": "https://www.youtube.com", "youtube": "https://www.youtube.com", "гугл": "https://www.google.com",
    "google": "https://www.google.com", "гитхаб": "https://github.com", "github": "https://github.com",
    "почту": "https://mail.google.com", "почта": "https://mail.google.com", "gmail": "https://mail.google.com",
    "вк": "https://vk.com", "вконтакте": "https://vk.com", "телеграм": "https://web.telegram.org",
    "telegram": "https://web.telegram.org", "переводчик": "https://translate.google.com",
    "карты": "https://www.google.com/maps", "chatgpt": "https://chatgpt.com", "википедию": "https://ru.wikipedia.org",
    "яндекс": "https://ya.ru", "кинопоиск": "https://www.kinopoisk.ru", "погоду": "https://yandex.ru/pogoda",
}
FOLDERS = {"загрузки": "DOWNLOAD", "документы": "DOCUMENTS", "рабочий стол": "DESKTOP", "изображения": "PICTURES",
           "картинки": "PICTURES", "фото": "PICTURES", "музыку": "MUSIC", "музыка": "MUSIC", "видео": "VIDEOS"}
APP_ALIASES = {"браузер": "firefox", "фаерфокс": "firefox", "файрфокс": "firefox", "терминал": "kitty",
               "консоль": "kitty", "файлы": "dolphin", "проводник": "dolphin", "файловый менеджер": "dolphin",
               "вс код": "code", "vs code": "code", "вскод": "code", "редактор кода": "code", "блокнот": "kate",
               "калькулятор": "kcalc", "настройки": "systemsettings", "параметры": "systemsettings",
               "центр приложений": "plasma-discover", "магазин": "plasma-discover", "телеграм": "telegram",
               "майнд": "aisktag-mind", "mind": "aisktag-mind", "центр": "aisktag-welcome"}
UNITS = {"секунд": 1, "сек": 1, "с": 1, "минут": 60, "мин": 60, "м": 60, "час": 3600, "ч": 3600}
WORD_NUM = {"одну": 1, "один": 1, "две": 2, "два": 2, "три": 3, "пять": 5, "десять": 10, "пятнадцать": 15,
            "двадцать": 20, "тридцать": 30, "полчаса": 30}


def _env() -> dict:
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return env


def _run(argv: list[str], timeout: float = 10) -> str:
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=_env()).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _spawn(argv: list[str]) -> bool:
    if not shutil.which(argv[0]):
        return False
    subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                     start_new_session=True, env=_env())
    return True


def _open_url(url: str) -> str:
    _spawn(["xdg-open", url])
    return f"Открываю {url}"


def _gb(kib: int) -> str:
    return f"{kib / 1024 / 1024:.1f} ГБ"


def _memory() -> str:
    info = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        k, v = line.split(":", 1)
        info[k] = int(v.split()[0])
    total, avail = info["MemTotal"], info.get("MemAvailable", info["MemFree"])
    return f"Оперативная память: свободно {_gb(avail)} из {_gb(total)} (занято {100 - avail * 100 // total}%)."


def _disk() -> str:
    du = shutil.disk_usage(str(Path.home()))
    return f"Диск: свободно {du.free / 1e9:.0f} ГБ из {du.total / 1e9:.0f} ГБ ({du.used * 100 // du.total}% занято)."


def _cpu() -> str:
    model = ""
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            model = line.split(":", 1)[1].strip()
            break
    load = os.getloadavg()[0]
    return f"Процессор: {model or 'неизвестен'}, ядер: {os.cpu_count()}, загрузка за минуту: {load:.1f}."


def _battery() -> str:
    for b in sorted(Path("/sys/class/power_supply").glob("BAT*")):
        try:
            cap = (b / "capacity").read_text().strip()
            st = (b / "status").read_text().strip()
            st = {"Charging": "заряжается", "Discharging": "разряжается", "Full": "полностью заряжена"}.get(st, st)
            return f"Батарея: {cap}%, {st}."
        except OSError:
            continue
    return "Батареи нет — это настольный компьютер или виртуальная машина."


def _ip() -> str:
    addrs = _run(["hostname", "-I"]).split()
    return f"IP-адрес: {', '.join(addrs)}." if addrs else "Сеть не подключена."


def _uptime() -> str:
    sec = int(float(Path("/proc/uptime").read_text().split()[0]))
    h, m = sec // 3600, sec % 3600 // 60
    return f"Компьютер работает {h} ч {m} мин."


def _volume(cmd: str) -> str:
    if shutil.which("wpctl"):
        sink = "@DEFAULT_AUDIO_SINK@"
        argv = {"up": ["wpctl", "set-volume", "-l", "1.0", sink, "10%+"], "down": ["wpctl", "set-volume", sink, "10%-"],
                "mute": ["wpctl", "set-mute", sink, "1"], "unmute": ["wpctl", "set-mute", sink, "0"]}.get(cmd)
        if cmd.isdigit():
            argv = ["wpctl", "set-volume", "-l", "1.0", sink, f"{min(int(cmd), 100)}%"]
        _run(argv)
        now = _run(["wpctl", "get-volume", sink])
        m = re.search(r"([\d.]+)", now)
        level = f" Громкость: {round(float(m.group(1)) * 100)}%." if m else ""
        return ("Звук выключен." if "MUTED" in now else "Готово.") + level
    if shutil.which("pactl"):
        sink = "@DEFAULT_SINK@"
        argv = {"up": ["pactl", "set-sink-volume", sink, "+10%"], "down": ["pactl", "set-sink-volume", sink, "-10%"],
                "mute": ["pactl", "set-sink-mute", sink, "1"], "unmute": ["pactl", "set-sink-mute", sink, "0"]}.get(cmd)
        if cmd.isdigit():
            argv = ["pactl", "set-sink-volume", sink, f"{min(int(cmd), 100)}%"]
        _run(argv)
        return "Готово."
    return "Не нашёл, чем управлять звуком (wpctl или pactl)."


def _screenshot() -> str:
    pics = _run(["xdg-user-dir", "PICTURES"]) or str(Path.home() / "Pictures")
    out = Path(pics) / f"Снимок экрана {time.strftime('%Y-%m-%d %H-%M-%S')}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    for argv in (["spectacle", "-b", "-n", "-f", "-o", str(out)], ["grim", str(out)]):
        if shutil.which(argv[0]):
            _run(argv, timeout=20)
            if out.exists():
                return f"Снимок экрана сохранён: {out}"
    return "Не получилось сделать снимок экрана."


def _remind(seconds: int, text: str) -> str:
    text = text.strip(" ,.:—-") or "Время вышло!"
    script = f"sleep {seconds}; notify-send -u critical -a Джарвис -i aisktagos-jarvis 'Джарвис' \"$0\"; " \
             "command -v paplay >/dev/null && paplay /usr/share/sounds/freedesktop/stereo/complete.oga"
    _spawn(["sh", "-c", script, text])
    when = time.strftime("%H:%M", time.localtime(time.time() + seconds))
    return f"Напомню в {when}: {text}"


def _duration(num: str, unit: str) -> int | None:
    n = WORD_NUM.get(num, None) if not num.isdigit() else int(num)
    if num == "полчаса":
        return 1800
    if n is None:
        return None
    for prefix, mult in sorted(UNITS.items(), key=lambda kv: -len(kv[0])):
        if unit.startswith(prefix):
            return n * mult
    return None


def handle(text: str, tools, confirm) -> str | None:
    """Распознать и выполнить мгновенную команду. None — команда не узнана, пусть думает модель."""
    t = _TAIL.sub("", _PREFIX.sub("", text.strip())).strip()
    low = t.lower().replace("ё", "е")
    if not low or len(low) > 120:
        return None

    # --- Время и дата ---
    if re.fullmatch(r"(?:сколько|который)\s+(?:сейчас\s+)?(?:время|час)|время|какое сейчас время", low):
        return f"Сейчас {time.strftime('%H:%M')}."
    if re.fullmatch(r"(?:какое|какая)\s+сегодня\s+(?:число|дата)|какой сегодня день|сегодняшняя дата|дата", low):
        days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
        return f"Сегодня {time.strftime('%d.%m.%Y')}, {days[time.localtime().tm_wday]}."

    # --- Сведения о компьютере ---
    if re.search(r"(?:сколько|свободн|занят).*(?:памят|озу|оперативк)|(?:памят|озу|оперативк)\w*\s+свободн", low):
        return _memory()
    if re.search(r"(?:сколько|свободн|занят|осталось).*(?:мест|диск)", low):
        return _disk()
    if re.search(r"(?:какой|что за|загрузка)\s+(?:у меня\s+)?процессор|процессор загружен|загрузка процессора", low):
        return _cpu()
    if re.search(r"(?:заряд|батаре|аккумулятор)", low) and len(low) < 40:
        return _battery()
    if re.search(r"(?:какой|мой)\s+(?:у меня\s+)?(?:ip|айпи)|ip[- ]адрес", low):
        return _ip()
    if re.search(r"(?:сколько|как долго)\s+работает\s+(?:компьютер|система)|аптайм|uptime", low):
        return _uptime()

    # --- Звук ---
    if len(low) < 40 and re.search(r"(?:погромче|громче|прибавь\s+(?:звук|громкость))", low):
        return _volume("up")
    if len(low) < 40 and re.search(r"(?:потише|тише|убавь\s+(?:звук|громкость))", low):
        return _volume("down")
    m = re.search(r"громкость\s+(?:на\s+)?(\d{1,3})\s*%?", low)
    if m:
        return _volume(m.group(1))
    if re.search(r"(?:выключи|отключи|убери)\s+звук|без звука|mute", low):
        return _volume("mute")
    if re.search(r"(?:включи|верни)\s+звук", low):
        return _volume("unmute")

    # --- Экран ---
    if re.fullmatch(r"(?:сделай\s+)?(?:скриншот|снимок экрана)(?:\s+экрана)?", low):
        return _screenshot()
    if re.search(r"(?:заблокируй|блокируй|заблокировать)\s+(?:экран|компьютер)", low):
        _spawn(["loginctl", "lock-session"])
        return "Блокирую экран."

    # --- Напоминание и таймер ---
    m = re.search(r"(?:напомни|таймер|поставь таймер|разбуди)\s*(?:мне\s+)?(?:через|на)\s+(\d+|\w+)\s*(\w+)?(.*)", low)
    if m:
        num, unit, rest = m.group(1), m.group(2) or "минут", m.group(3)
        if num == "полчаса":
            unit, rest = "минут", (m.group(2) or "") + rest
        sec = _duration(num, unit)
        if sec:
            # Текст напоминания берём из исходной фразы, чтобы сохранить регистр
            idx = low.find(rest.strip()) if rest.strip() else -1
            what = t[idx:] if idx >= 0 else rest
            return _remind(sec, re.sub(r"^(?:что|о том,? что|про)\s+", "", what.strip(), flags=re.I))

    # --- Поиск в интернете ---
    # Ищем по исходной фразе (без lower), чтобы запрос сохранил регистр: «погода в Алматы»
    m = re.search(r"(?:найди|поищи|загугли|погугли)\s+(?:в\s+)?(?:ютубе|youtube)\s+(.+)|"
                  r"(?:включи|найди|поищи)\s+на\s+(?:ютубе|youtube)\s+(.+)", t, re.I)
    if m:
        q = m.group(1) or m.group(2)
        _open_url("https://www.youtube.com/results?search_query=" + urllib.parse.quote(q))
        return f"Ищу на YouTube: {q}"
    m = re.search(r"(?:найди|поищи|загугли|погугли)\s+(?:в\s+(?:интернете|гугле|google|сети|яндексе)\s+)(.+)|"
                  r"^(?:загугли|погугли)\s+(.+)", t, re.I)
    if m:
        q = m.group(1) or m.group(2)
        _open_url("https://www.google.com/search?q=" + urllib.parse.quote(q))
        return f"Ищу в Google: {q}"

    # --- Открыть сайт, папку, приложение ---
    m = re.fullmatch(r"(?:открой|запусти|включи|покажи)\s+(?:мне\s+)?(?:сайт\s+|папку\s+|приложение\s+|программу\s+)?(.+)", low)
    if m:
        what = m.group(1).strip()
        if re.search(r"\s(?:и|а потом|затем|потом)\s|,", what):
            return None                                # составная задача — это работа для модели
        if what in SITES:
            return _open_url(SITES[what])
        if re.fullmatch(r"(?:https?://)?[\w.-]+\.[a-zа-я]{2,}(?:/\S*)?", what):
            return _open_url(what if "://" in what else "https://" + what)
        if what in FOLDERS or what in ("домашнюю папку", "домашняя папка", "дом"):
            path = str(Path.home()) if what not in FOLDERS else (
                _run(["xdg-user-dir", FOLDERS[what]]) or str(Path.home() / FOLDERS[what].title().replace("Download", "Downloads")))
            tools.t_open_path(path)
            return f"Открываю {path}"
        app = APP_ALIASES.get(what, what)
        res = tools.t_open_app(app)
        if res.startswith("запущено"):
            return f"Запускаю {what}."
        return None                                    # не нашли — пусть разбирается модель

    # --- Создать папку ---
    m = re.fullmatch(r"создай\s+(?:новую\s+)?папку\s+[«\"']?(.+?)[»\"']?(\s+на рабочем столе)?", t, re.I)
    if m:
        base = Path(_run(["xdg-user-dir", "DESKTOP"]) or Path.home() / "Desktop") if m.group(2) else Path.home()
        path = base / m.group(1).strip()
        path.mkdir(parents=True, exist_ok=True)
        return f"Папка создана: {path}"

    # --- Питание (только с подтверждения) ---
    if re.search(r"(?:выключи|выключить)\s+(?:компьютер|пк|систему)|заверши работу", low):
        if confirm("power", "выключить компьютер"):
            _spawn(["systemctl", "poweroff"])
            return "Выключаю компьютер."
        return "Хорошо, не выключаю."
    if re.search(r"(?:перезагрузи|перезагрузить)\s+(?:компьютер|пк|систему)", low):
        if confirm("power", "перезагрузить компьютер"):
            _spawn(["systemctl", "reboot"])
            return "Перезагружаю."
        return "Хорошо, не перезагружаю."
    return None
