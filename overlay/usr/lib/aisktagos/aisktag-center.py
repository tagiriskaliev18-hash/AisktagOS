#!/usr/bin/env python3
"""Центр AIsktagOS: приветствие, драйверы видеокарты, инструменты разработчика, процессы
и сведения о системе.

    aisktag-welcome [--page welcome|drivers|dev|processes|system] [--autostart]
"""
import html
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
import zlib
from pathlib import Path

from PyQt6.QtCore import QPointF, QProcess, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import (QBrush, QColor, QConicalGradient, QFont, QFontMetrics, QIcon, QImage,
                         QLinearGradient, QPainter, QPainterPath, QPalette, QPen, QPixmap,
                         QRadialGradient)
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QDialog, QFrame, QGridLayout,
                             QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
                             QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
                             QSizePolicy, QStackedWidget, QTableWidget, QTableWidgetItem, QToolButton,
                             QVBoxLayout, QWidget)

DONE_FLAG = Path.home() / ".config/aisktagos/welcome-done"
LIVE = "boot=casper" in Path("/proc/cmdline").read_text()
LOGO = "/usr/share/aisktagos/logo.png"

STYLE = """
QWidget { font-size: 10.5pt; }
QListWidget#nav { background: palette(base); border: none; padding: 8px; }
QListWidget#nav::item { padding: 10px 12px; border-radius: 8px; margin: 2px 0; }
QListWidget#nav::item:selected { background: #6d5dfc; color: white; }
QLabel#h1 { font-size: 22pt; font-weight: 600; }
QLabel#h2 { font-size: 14pt; font-weight: 600; }
QLabel#muted { color: palette(placeholder-text); }
QFrame#card { background: palette(base); border-radius: 12px; }
QPushButton#tile { text-align: left; padding: 14px; border-radius: 10px; font-size: 11pt; }
QPushButton#primary { background: #6d5dfc; color: white; border-radius: 8px; padding: 8px 18px; font-weight: 600; }
QPushButton#primary:disabled { background: #4a4760; color: #aaa; }
QPlainTextEdit { font-family: 'JetBrains Mono'; font-size: 9pt; border-radius: 8px; }
QFrame#dlcard { background: palette(base); border-radius: 12px; border: 1px solid #6d5dfc; }
QLabel#speed { color: #8f83ff; font-weight: 600; font-size: 11pt; }
QToolButton#sectionToggle { border: none; font-size: 12.5pt; font-weight: 600; padding: 4px 2px; }
QPushButton#link { color: #8f83ff; border: none; padding: 4px 8px; }
QPushButton#link:hover { text-decoration: underline; }
QLineEdit#search { border-radius: 8px; padding: 6px 8px; background: palette(base);
                   border: 1px solid rgba(128, 128, 128, 0.35); }
QLineEdit#search:focus { border-color: #6d5dfc; }
QProgressBar { border: none; border-radius: 4px; background: rgba(128, 128, 128, 0.25); }
QProgressBar::chunk { border-radius: 4px; background: #6d5dfc; }
"""

# (название, описание, кто выполняет: root|user, команда)
DEV_STACKS = [
    ("Java", "OpenJDK 21, Maven и Gradle", "root",
     "apt-get install -y openjdk-21-jdk maven gradle"),
    ("Go", "Компилятор и инструменты Go", "root", "apt-get install -y golang-go"),
    (".NET", ".NET SDK от Microsoft (C#, F#)", "root", "apt-get install -y dotnet-sdk-10.0"),
    ("Rust", "Стабильный тулчейн, clippy, rustfmt, rust-analyzer", "user",
     "rustup default stable && rustup component add clippy rustfmt rust-analyzer"),
    ("Виртуальные машины", "virt-manager + QEMU/KVM", "root",
     "apt-get install -y virt-manager qemu-system-x86 libvirt-daemon-system && "
     "usermod -aG libvirt,kvm \"$(id -nu \"$PKEXEC_UID\")\""),
    ("Claude Code", "ИИ-ассистент для программирования в терминале", "user",
     "npm config set prefix ~/.npm-global && npm install -g @anthropic-ai/claude-code"),
    ("Ollama", "Локальные нейросети (Llama, Qwen, DeepSeek) без интернета", "root",
     "curl -fsSL https://ollama.com/install.sh | sh"),
    ("LibreOffice", "Офисный пакет (Word/Excel/PowerPoint-совместимый)", "root",
     "apt-get install -y libreoffice libreoffice-kf6 libreoffice-l10n-ru"),
    ("IntelliJ IDEA Community", "IDE для Java/Kotlin (Flathub)", "user",
     "flatpak install -y --noninteractive flathub com.jetbrains.IntelliJ-IDEA-Community"),
    ("PyCharm Community", "IDE для Python (Flathub)", "user",
     "flatpak install -y --noninteractive flathub com.jetbrains.PyCharm-Community"),
    ("Android Studio", "Разработка под Android (Flathub)", "user",
     "flatpak install -y --noninteractive flathub com.google.AndroidStudio"),
    ("Postman", "Тестирование API (Flathub)", "user",
     "flatpak install -y --noninteractive flathub com.getpostman.Postman"),
    ("DBeaver", "Универсальный клиент баз данных (Flathub)", "user",
     "flatpak install -y --noninteractive flathub io.dbeaver.DBeaverCommunity"),
    ("Telegram", "Мессенджер (Flathub)", "user",
     "flatpak install -y --noninteractive flathub org.telegram.desktop"),
]


def launch(*argv: str) -> None:
    """Запустить приложение отдельно от Центра."""
    if shutil.which(argv[0]):
        subprocess.Popen(argv, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        QMessageBox.information(None, "AIsktagOS", f"Программа «{argv[0]}» не установлена.")


def gpus() -> list[str]:
    try:
        out = subprocess.run(["lspci", "-mm"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return []
    res = []
    for line in out.splitlines():
        parts = re.findall(r'"([^"]*)"', line)
        if len(parts) >= 3 and re.search(r"VGA|3D|Display", parts[0]):
            res.append(f"{parts[1]} {parts[2]}")
    return res


def has_nvidia() -> bool:
    return any("NVIDIA" in g.upper() for g in gpus())


class Runner(QWidget):
    """Журнал выполнения команд и очередь задач."""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.log = QPlainTextEdit(readOnly=True)
        self.log.setMaximumBlockCount(4000)
        self.log.setMinimumHeight(140)
        lay.addWidget(self.status)
        lay.addWidget(self.log)
        self.proc: QProcess | None = None
        self.queue: list[tuple[str, str, str]] = []
        self.on_idle = None
        self.setVisible(False)  # журнал появляется при первой задаче

    def busy(self) -> bool:
        return self.proc is not None

    def run(self, title: str, who: str, cmd: str) -> None:
        self.setVisible(True)
        self.queue.append((title, who, cmd))
        if not self.busy():
            self._next()

    def _next(self) -> None:
        if not self.queue:
            self.status.setText("Готово.")
            if self.on_idle:
                self.on_idle()
            return
        title, who, cmd = self.queue.pop(0)
        self.status.setText(f"Выполняется: {title}…")
        self.log.appendPlainText(f"\n▶ {title}\n$ {cmd}")
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._read)
        self.proc.finished.connect(lambda code, _s, t=title: self._done(t, code))
        if who == "root":
            self.proc.start("pkexec", ["env", "DEBIAN_FRONTEND=noninteractive",
                                       f"PKEXEC_UID={os.getuid()}", "bash", "-c", cmd])
        else:
            self.proc.start("bash", ["-lc", cmd])

    def _read(self) -> None:
        data = bytes(self.proc.readAllStandardOutput()).decode(errors="replace")
        self.log.insertPlainText(data)
        self.log.ensureCursorVisible()

    def _done(self, title: str, code: int) -> None:
        mark = "✔" if code == 0 else f"✘ (код {code})"
        self.log.appendPlainText(f"{mark} {title}")
        self.proc = None
        self._next()


def heading(text: str, obj: str = "h1") -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName(obj)
    lbl.setWordWrap(True)
    return lbl


def muted(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("muted")
    lbl.setWordWrap(True)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    return lbl


def tile(title: str, subtitle: str, icon: str, action) -> QPushButton:
    b = QPushButton(f"{title}\n{subtitle}")
    b.setObjectName("tile")
    b.setIcon(QIcon.fromTheme(icon))
    b.setIconSize(QSize(32, 32))
    b.setMinimumHeight(68)
    b.clicked.connect(action)
    return b


class WelcomePage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QPixmap(LOGO).scaled(88, 88, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))
        top.addWidget(logo)
        col = QVBoxLayout()
        col.addWidget(heading("Добро пожаловать в AIsktagOS"))
        col.addWidget(muted("Удобство macOS, свобода Linux Mint и надёжность Ubuntu LTS. "
                            "Всё для разработки уже установлено — можно сразу работать."))
        top.addLayout(col, 1)
        lay.addLayout(top)
        lay.addSpacing(12)

        grid = QGridLayout()
        tiles = []
        if LIVE:
            tiles.append(("Установить AIsktagOS", "Простой мастер установки на диск",
                          "aisktagos-install", lambda: launch("aisktag-install")))
        tiles += [
            ("Центр приложений", "Программы из Ubuntu и Flathub", "plasmadiscover",
             lambda: launch("plasma-discover")),
            ("Обновить систему", "Обновления и новые версии программ", "system-software-update",
             lambda: launch("plasma-discover", "--mode", "update")),
            ("Снимки системы", "Откат к рабочему состоянию (Timeshift)", "timeshift",
             lambda: launch("timeshift-launcher")),
            ("Настройки", "Экран, звук, сеть, оформление", "preferences-system",
             lambda: launch("systemsettings")),
            ("Терминал", "kitty + zsh с подсказками", "kitty", lambda: launch("kitty")),
            ("VS Code", "Редактор кода", "vscode",
             lambda: launch("code")),
        ]
        for i, (t, s, ic, fn) in enumerate(tiles):
            grid.addWidget(tile(t, s, ic, fn), i // 2, i % 2)
        lay.addLayout(grid)
        lay.addSpacing(12)

        lay.addWidget(heading("Горячие клавиши", "h2"))
        keys = QLabel(
            "<table cellspacing=6>"
            "<tr><td><b>Meta+Space</b></td><td>Поиск приложений, файлов, калькулятор (как Spotlight)</td></tr>"
            "<tr><td><b>Meta+W</b> / угол слева снизу</td><td>Обзор всех окон (как Mission Control)</td></tr>"
            "<tr><td><b>Alt+Shift</b></td><td>Сменить раскладку клавиатуры</td></tr>"
            "<tr><td><b>Meta+←/→</b></td><td>Окно на половину экрана</td></tr>"
            "<tr><td><b>Meta+T</b></td><td>Редактор плиточной раскладки окон</td></tr>"
            "<tr><td><b>Meta+E</b></td><td>Файловый менеджер</td></tr>"
            "<tr><td><b>Print</b></td><td>Снимок экрана</td></tr>"
            "</table>")
        keys.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(keys)
        lay.addStretch(1)

        self.show_cb = QCheckBox("Показывать это окно при входе в систему")
        self.show_cb.setChecked(not DONE_FLAG.exists())
        self.show_cb.toggled.connect(self._toggle)
        lay.addWidget(self.show_cb)

    @staticmethod
    def _toggle(on: bool) -> None:
        DONE_FLAG.parent.mkdir(parents=True, exist_ok=True)
        if on:
            DONE_FLAG.unlink(missing_ok=True)
        else:
            DONE_FLAG.touch()


class DriversPage(QWidget):
    def __init__(self, runner: Runner):
        super().__init__()
        self.runner = runner
        lay = QVBoxLayout(self)
        lay.addWidget(heading("Менеджер драйверов"))
        lay.addWidget(muted(
            "AMD и Intel работают «из коробки» через открытые драйверы Mesa. "
            "Для NVIDIA рекомендуем фирменный драйвер — он даёт полную скорость в играх, "
            "CUDA и нейросетях."))
        card = QFrame(objectName="card")
        cl = QVBoxLayout(card)
        cl.addWidget(heading("Видеокарты в этом компьютере", "h2"))
        found = gpus() or ["не удалось определить"]
        for g in found:
            cl.addWidget(QLabel("• " + g))
        lay.addWidget(card)

        if LIVE:
            lay.addWidget(muted("<b>Вы в live-режиме.</b> Драйверы устанавливаются после установки "
                                "AIsktagOS на диск — они не сохранятся на USB."))
        elif has_nvidia():
            lay.addWidget(muted("<b>Найдена видеокарта NVIDIA.</b> Нажмите «Установить рекомендуемые», "
                                "затем перезагрузите компьютер."))

        row = QHBoxLayout()
        self.b_check = QPushButton("Проверить доступные драйверы")
        self.b_check.clicked.connect(lambda: runner.run(
            "Поиск драйверов", "user", "ubuntu-drivers devices 2>/dev/null || echo 'Дополнительные драйверы не требуются'"))
        self.b_install = QPushButton("Установить рекомендуемые", objectName="primary")
        self.b_install.clicked.connect(self._install)
        self.b_fw = QPushButton("Обновить прошивки устройств")
        self.b_fw.clicked.connect(lambda: runner.run(
            "Обновление прошивок", "root", "fwupdmgr refresh --force; fwupdmgr update -y --no-reboot-check"))
        for b in (self.b_check, self.b_install, self.b_fw):
            row.addWidget(b)
        row.addStretch(1)
        self.b_install.setEnabled(not LIVE)
        self.b_fw.setEnabled(not LIVE)
        lay.addLayout(row)
        lay.addStretch(1)

    def _install(self) -> None:
        self.runner.run("Установка драйверов", "root",
                        "apt-get update && ubuntu-drivers install && echo 'Перезагрузите компьютер, чтобы применить драйвер.'")


class DevPage(QWidget):
    def __init__(self, runner: Runner):
        super().__init__()
        self.runner = runner
        lay = QVBoxLayout(self)
        lay.addWidget(heading("Инструменты разработчика"))
        lay.addWidget(muted(
            "Уже установлено: <b>VS Code, Git, GitHub CLI, Docker, Podman, Distrobox, Python, "
            "Node.js, rustup, GCC/Clang, CMake, Neovim, lazygit</b>. "
            "Отметьте, что добавить, и нажмите «Установить»."))

        box = QWidget()
        col = QVBoxLayout(box)
        col.setSpacing(10)
        self.checks: list[tuple[QCheckBox, tuple]] = []
        for item in DEV_STACKS:
            name, desc, _who, _cmd = item
            cb = QCheckBox(f"{name}  ·  {desc}")
            col.addWidget(cb)
            self.checks.append((cb, item))
        col.addStretch(1)
        scroll = QScrollArea(widgetResizable=True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(box)
        lay.addWidget(scroll, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        self.b_go = QPushButton("Установить выбранное", objectName="primary")
        self.b_go.clicked.connect(self._go)
        row.addWidget(self.b_go)
        lay.addLayout(row)

    def _go(self) -> None:
        chosen = [item for cb, item in self.checks if cb.isChecked()]
        if not chosen:
            return
        if any(who == "root" for _n, _d, who, _c in chosen):
            self.runner.run("Обновление списка пакетов", "root", "apt-get update")
        for name, _desc, who, cmd in chosen:
            self.runner.run(name, who, cmd)
        for cb, _ in self.checks:
            cb.setChecked(False)


class SystemPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(heading("О системе"))
        card = QFrame(objectName="card")
        grid = QGridLayout(card)
        rows = [
            ("Система", self._os()),
            ("Ядро", platform.release()),
            ("Процессор", self._cpu()),
            ("Память", self._mem()),
            ("Видеокарта", "\n".join(gpus()) or "—"),
            ("Диск (/)", self._disk()),
            ("Графический сеанс", os.environ.get("XDG_SESSION_TYPE", "—").capitalize()),
            ("Режим", "Live-USB (без установки)" if LIVE else "Установлена на диск"),
        ]
        for i, (k, v) in enumerate(rows):
            kl = QLabel(k)
            kl.setObjectName("muted")
            vl = QLabel(v)
            vl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(kl, i, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(vl, i, 1)
        lay.addWidget(card)
        row = QHBoxLayout()
        for text, argv in (("Системный монитор", ("plasma-systemmonitor",)),
                           ("Информация о системе", ("kinfocenter",)),
                           ("Разделы дисков", ("partitionmanager",))):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, a=argv: launch(*a))
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)

    @staticmethod
    def _os() -> str:
        try:
            for line in Path("/etc/os-release").read_text().splitlines():
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip('"')
        except OSError:
            pass
        return "AIsktagOS"

    @staticmethod
    def _cpu() -> str:
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    return f"{line.split(':', 1)[1].strip()} ({os.cpu_count()} потоков)"
        except OSError:
            pass
        return platform.processor() or "—"

    @staticmethod
    def _mem() -> str:
        try:
            kb = int(Path("/proc/meminfo").read_text().split()[1])
            return f"{kb / 1024 / 1024:.1f} ГБ"
        except (OSError, ValueError, IndexError):
            return "—"

    @staticmethod
    def _disk() -> str:
        u = shutil.disk_usage("/")
        return f"свободно {u.free / 1e9:.0f} ГБ из {u.total / 1e9:.0f} ГБ"


# ───────────────────────────── Процессы ─────────────────────────────
# Страница читает только /proc (без psutil и без вызова ps), опрашивает раз в 2 секунды
# и только пока видима. Карточки рисуются одним paintEvent без дочерних виджетов,
# «3D-иконки» рендерятся один раз и берутся из кэша.

ACCENT = QColor("#6d5dfc")
MEM_COLOR = QColor("#2fb9a0")
PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")
MY_UID = os.getuid()
CARD_LIMIT = 40          # сколько карточек показывать в разделе до «Показать все»
POLL_MS = 2000

# Интерпретаторы: группируем по запущенному скрипту, а не по python/node/bash
INTERPRETERS = re.compile(r"^(python[\d.]*|perl[\d.]*|ruby[\d.]*|node|nodejs|bash|sh|dash|zsh|gjs)$")
# Слишком общие команды в Exec=, по которым нельзя узнать приложение
GENERIC_EXEC = {"sh", "bash", "env", "python", "python3", "pkexec", "kdesu", "sudo", "java", "node",
                "perl", "flatpak", "xdg-open", "kioclient", "kioclient5", "gtk-launch", "kstart",
                "kstart5", "dbus-send", "qdbus", "systemctl", "true", "display", "vim", "vi"}
# Наши процессы, у которых имя исполняемого файла не совпадает с Exec= ярлыка
KEY_ALIASES = {"aisktag-center": "aisktag-welcome"}
# Понятные названия частых служб и фоновых программ
KNOWN_NAMES = {
    "__kernel": "Ядро Linux (потоки ядра)", "systemd": "Системный менеджер systemd",
    "init": "Первый процесс системы (init)",
    "systemd-journald": "Журнал системы", "systemd-logind": "Вход в систему (logind)",
    "systemd-udevd": "Устройства (udev)", "systemd-resolved": "DNS (systemd-resolved)",
    "systemd-timesyncd": "Синхронизация времени", "systemd-oomd": "Защита от нехватки памяти",
    "Xorg": "Графический сервер X11", "Xwayland": "Совместимость с X11 (Xwayland)",
    "kwin_x11": "Диспетчер окон KWin", "kwin_wayland": "Диспетчер окон KWin",
    "plasmashell": "Рабочий стол Plasma", "krunner": "Поиск KRunner", "kded5": "Службы KDE (kded)",
    "kded6": "Службы KDE (kded)", "ksmserver": "Сеанс KDE", "baloo_file": "Индексатор файлов Baloo",
    "pipewire": "Звук и видео (PipeWire)", "pipewire-pulse": "Звук (PulseAudio через PipeWire)",
    "wireplumber": "Звук: маршрутизация (WirePlumber)", "pulseaudio": "Звук (PulseAudio)",
    "NetworkManager": "Сеть (NetworkManager)", "wpa_supplicant": "Wi-Fi (wpa_supplicant)",
    "dbus-daemon": "Шина сообщений D-Bus", "dbus-broker": "Шина сообщений D-Bus",
    "polkitd": "Права администратора (polkit)", "sddm": "Экран входа SDDM", "sshd": "Сервер SSH",
    "cron": "Планировщик cron", "cupsd": "Печать (CUPS)", "dockerd": "Docker",
    "containerd": "Контейнеры (containerd)", "udisksd": "Диски (UDisks)",
    "upowerd": "Питание (UPower)", "bluetoothd": "Bluetooth", "avahi-daemon": "Обнаружение в сети (Avahi)",
    "accounts-daemon": "Учётные записи", "rsyslogd": "Системный журнал (rsyslog)",
    "packagekitd": "Установка программ (PackageKit)", "fwupd": "Обновление прошивок (fwupd)",
    "thermald": "Контроль температуры", "irqbalance": "Распределение прерываний",
    "ModemManager": "Модемы", "colord": "Цветовые профили", "agetty": "Текстовая консоль",
    "login": "Вход в консоль", "bash": "Оболочка bash", "zsh": "Оболочка zsh",
    "sh": "Оболочка sh", "dash": "Оболочка dash", "sleep": "Ожидание (sleep)", "tmux": "Терминальный мультиплексор tmux",
    "ssh-agent": "Хранитель ключей SSH", "gpg-agent": "Хранитель ключей GnuPG",
    "unattended-upgrade-shutdown": "Автообновления: ожидание выключения",
    "aisktag-center": "Центр AIsktagOS",
}
CRITICAL = {"systemd", "init", "Xorg", "Xwayland", "kwin_x11", "kwin_wayland", "plasmashell", "sddm",
            "ksmserver", "dbus-daemon", "dbus-broker", "systemd-logind", "__kernel"}


def fmt_num(v: float, digits: int = 1) -> str:
    return f"{v:.{digits}f}".replace(".", ",")


def fmt_mem(mb: float) -> str:
    return f"{fmt_num(mb / 1024)} ГБ" if mb >= 1024 else f"{mb:.0f} МБ"


def fmt_speed(bps: float) -> str:
    if bps >= 1024 * 1024:
        return f"{fmt_num(bps / 1048576)} МБ/с"
    if bps >= 1024:
        return f"{bps / 1024:.0f} КБ/с"
    return f"{bps:.0f} Б/с"


def plural(n: int, one: str, few: str, many: str) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} {one}"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} {few}"
    return f"{n} {many}"


def nproc_text(n: int) -> str:
    return plural(n, "процесс", "процесса", "процессов")


def read_file(path: str) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return b""


def users_by_uid() -> dict[int, str]:
    res = {}
    try:
        for line in Path("/etc/passwd").read_text(errors="replace").splitlines():
            parts = line.split(":")
            if len(parts) > 2 and parts[2].isdigit():
                res[int(parts[2])] = parts[0]
    except OSError:
        pass
    return res


def process_key(argv: list[str], comm: str) -> str:
    """Ключ приложения: имя исполняемого файла, а для интерпретаторов — имя скрипта."""
    if not argv or not argv[0]:
        return comm
    first = argv[0]
    if len(argv) == 1 and " " in first:  # процесс переписал свою командную строку (setproctitle)
        first = first.split()[0]
    key = os.path.basename(first.rstrip(":")) or comm
    if key.startswith("-"):  # «-zsh» у оболочки входа
        key = key[1:]
    if INTERPRETERS.match(key):
        rest = argv[1:]
        for i, a in enumerate(rest):
            if a == "-m" and i + 1 < len(rest):  # python3 -m pip → pip
                return rest[i + 1].split(".")[0]
            if a in ("-c", "-e"):
                break
            if not a.startswith("-"):
                name = os.path.basename(a)
                for ext in (".py", ".js", ".pl", ".rb", ".sh"):
                    if name.endswith(ext):
                        name = name[: -len(ext)]
                return "npm" if name == "npm-cli" else (name or key)
    if re.match(r"^python3\.\d+$", key):
        key = "python3"
    return key


class DesktopIndex:
    """Сопоставление процессов с ярлыками .desktop (человеческое имя и иконка)."""

    DIRS = ["/usr/share/applications", "/usr/local/share/applications",
            "/var/lib/flatpak/exports/share/applications",
            str(Path.home() / ".local/share/flatpak/exports/share/applications"),
            str(Path.home() / ".local/share/applications")]

    def __init__(self):
        self.map: dict[str, tuple[str, str]] = {}
        entries = []
        for d in reversed(self.DIRS):  # пользовательские ярлыки важнее системных
            try:
                files = sorted(os.listdir(d))
            except OSError:
                continue
            for fn in files:
                if fn.endswith(".desktop"):
                    e = self._parse(os.path.join(d, fn))
                    if e:
                        entries.append(e)
        entries.sort(key=lambda e: e["nodisplay"])  # сначала видимые в меню
        for field in ("exec", "wmclass", "id", "idtail"):
            for e in entries:
                k = e.get(field)
                if k and k not in self.map and k not in GENERIC_EXEC:
                    self.map[k] = (e["name"], e["icon"])

    @staticmethod
    def _parse(path: str) -> dict | None:
        vals: dict[str, str] = {}
        in_main = False
        try:
            text = Path(path).read_text(errors="replace")
        except OSError:
            return None
        for line in text.splitlines():
            if line.startswith("["):
                in_main = line.strip() == "[Desktop Entry]"
                continue
            if in_main and "=" in line:
                k, v = line.split("=", 1)
                vals.setdefault(k.strip(), v.strip())
        if vals.get("Type", "Application") != "Application" or vals.get("Hidden") == "true":
            return None
        name = vals.get("Name[ru]") or vals.get("Name")
        if not name:
            return None
        stem = os.path.basename(path)[:-8]
        e = {"name": name, "icon": vals.get("Icon", ""), "nodisplay": vals.get("NoDisplay") == "true",
             "id": stem.lower(), "idtail": stem.split(".")[-1].lower(),
             "wmclass": vals.get("StartupWMClass", "").lower()}
        toks = vals.get("Exec", "").split()
        while toks and (toks[0] == "env" or ("=" in toks[0] and not toks[0].startswith("/"))):
            toks.pop(0)
        if toks:
            if os.path.basename(toks[0]) == "flatpak" and "run" in toks:
                rest = [t for t in toks[toks.index("run") + 1:] if not t.startswith(("-", "@", "%"))]
                if rest:
                    e["exec"] = rest[0].split(".")[-1].lower()
            else:
                e["exec"] = os.path.basename(toks[0].strip('"')).lower()
        return e

    def lookup(self, key: str):
        return self.map.get(KEY_ALIASES.get(key, key).lower())


class ProcScanner:
    """Снимок процессов из /proc; ЦП% — по разнице utime+stime между опросами и /proc/stat."""

    def __init__(self):
        self.cache: dict[int, tuple] = {}    # pid → (starttime, uid, argv, key)
        self.prev_ticks: dict[int, int] = {}
        self.prev_total = self.prev_idle = 0
        self.prev_net = None
        self.prev_net_t = 0.0
        self.net_rx = self.net_tx = 0.0
        self.cpu_total_pct = 0.0
        self.mem_total = self.mem_used = 0.0
        self.ncpu = os.cpu_count() or 1

    def scan(self) -> list[dict]:
        vals = [int(x) for x in read_file("/proc/stat").split(b"\n", 1)[0].split()[1:9]]
        total, idle = sum(vals), vals[3] + vals[4]
        d_total = total - self.prev_total if self.prev_total else 0
        if d_total > 0:
            busy = d_total - (idle - self.prev_idle)
            self.cpu_total_pct = max(0.0, min(100.0, 100.0 * busy / d_total))
        self.prev_total, self.prev_idle = total, idle

        procs = []
        new_ticks: dict[int, int] = {}
        cache, prev_ticks = self.cache, self.prev_ticks
        for name in os.listdir("/proc"):
            if not name.isdigit():
                continue
            pid = int(name)
            raw = read_file(f"/proc/{name}/stat")
            if not raw:
                continue
            r = raw.rfind(b")")
            comm = raw[raw.find(b"(") + 1:r].decode(errors="replace")
            f = raw[r + 2:].split()
            ticks = int(f[11]) + int(f[12])
            start = f[19]
            c = cache.get(pid)
            prev = None
            if c is None or c[0] != start:   # новый процесс (или PID переиспользован)
                try:
                    uid = os.stat(f"/proc/{name}").st_uid
                except OSError:
                    continue
                argv = [a.decode(errors="replace") for a in
                        read_file(f"/proc/{name}/cmdline").rstrip(b"\0").split(b"\0") if a]
                kernel = not argv and (int(f[1]) == 2 or pid == 2)
                c = cache[pid] = (start, uid, argv, "__kernel" if kernel else process_key(argv, comm))
            else:
                prev = prev_ticks.get(pid)
            new_ticks[pid] = ticks
            cpu = 100.0 * (ticks - prev) / d_total if (prev is not None and d_total > 0) else 0.0
            procs.append({"pid": pid, "comm": comm, "state": f[0].decode(), "uid": c[1],
                          "argv": c[2], "key": c[3], "cpu": max(0.0, cpu),
                          "mem": int(f[21]) * PAGE_SIZE / 1048576})
        for pid in [p for p in cache if p not in new_ticks]:
            del cache[pid]
        self.prev_ticks = new_ticks
        self._mem()
        self._net()
        return procs

    def _mem(self) -> None:
        info = {}
        for line in read_file("/proc/meminfo").split(b"\n")[:8]:
            p = line.split()
            if len(p) >= 2:
                info[p[0]] = int(p[1])
        self.mem_total = info.get(b"MemTotal:", 0) / 1024
        self.mem_used = self.mem_total - info.get(b"MemAvailable:", 0) / 1024

    def _net(self) -> None:
        rx = tx = 0
        for line in read_file("/proc/net/dev").split(b"\n")[2:]:
            if b":" not in line:
                continue
            ifc, data = line.split(b":", 1)
            if ifc.strip() == b"lo":
                continue
            p = data.split()
            rx += int(p[0])
            tx += int(p[8])
        now = time.monotonic()
        if self.prev_net is not None and now > self.prev_net_t:
            dt = now - self.prev_net_t
            self.net_rx = max(0.0, (rx - self.prev_net[0]) / dt)
            self.net_tx = max(0.0, (tx - self.prev_net[1]) / dt)
        self.prev_net, self.prev_net_t = (rx, tx), now


def download_activity(p: dict) -> tuple[str, str, str] | None:
    """Если процесс что-то скачивает или устанавливает — (подпись, иконка, ключ строки)."""
    key, argv = p["key"], p["argv"]
    args = set(argv[1:])
    if key in ("apt", "apt-get", "aptitude"):
        return "Установка пакетов (apt)", "system-software-update", "apt"
    if key == "dpkg":
        return "Распаковка и настройка пакетов (dpkg)", "package-x-generic", "dpkg"
    if key.startswith("unattended-upgr") and not any("shutdown" in a for a in argv + [key]):
        return "Автоматические обновления безопасности", "system-software-update", "unattended"
    if key == "packagekitd" and p["cpu"] > 0.5:   # служба висит постоянно — показываем, только когда работает
        return "Центр приложений устанавливает программы (PackageKit)", "plasmadiscover", "packagekit"
    if key == "flatpak" and args & {"install", "update", "upgrade"}:
        return "Загрузка из Flathub", "flatpak-discover", "flatpak"
    if key == "fwupdmgr" or (key == "fwupd" and p["cpu"] > 0.5):
        return "Обновление прошивок устройств (fwupd)", "fwupd", "fwupd"
    if key in ("pip", "pip3"):
        return "Установка пакетов Python (pip)", "text-x-python", "pip"
    if key in ("npm", "npx", "pnpm", "yarn"):
        return "Установка пакетов Node.js (npm)", "application-javascript", "npm"
    if key in ("curl", "wget"):
        return f"Загрузка файла ({key})", "download", key
    if (key == "git" and args & {"clone", "fetch", "pull"}) or key.startswith("git-remote-http"):
        return "Загрузка репозитория (git)", "git", "git"
    if key == "ollama" and "pull" in args:
        return "Загрузка нейросети (Ollama)", "download", "ollama"
    if key.startswith("aisktag-ai"):
        return "ИИ-ассистент AIsktagOS загружает данные", "aisktagos-logo", "aisktag-ai"
    if key.startswith("calamares"):
        return "Установка AIsktagOS на диск", "calamares", "calamares"
    return None


# ── «3D-иконки» ──

_ICON_CACHE: dict[tuple, QPixmap] = {}
_COLOR_CACHE: dict[str, QColor] = {}


def resolve_icon(spec: str) -> QIcon:
    if not spec:
        return QIcon()
    if spec.startswith("/"):
        return QIcon(spec) if os.path.exists(spec) else QIcon()
    return QIcon.fromTheme(spec)


def name_color(text: str) -> QColor:
    """Стабильный цвет по имени — для приложений без иконки."""
    return QColor.fromHsvF((zlib.crc32(text.encode()) % 360) / 360, 0.55, 0.78)


def dominant_color(spec: str, fallback: str) -> QColor:
    """Доминирующий цвет иконки: среднее по уменьшенной копии 16×16 с весом насыщенности."""
    ck = spec or "#" + fallback
    col = _COLOR_CACHE.get(ck)
    if col is not None:
        return col
    icon = resolve_icon(spec)
    if not icon.isNull():
        img = icon.pixmap(16, 16).toImage().convertToFormat(QImage.Format.Format_ARGB32)
        r = g = b = wsum = 0.0
        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                a = c.alphaF()
                if a < 0.3:
                    continue
                w = a * (0.15 + c.hsvSaturationF())
                r += c.redF() * w
                g += c.greenF() * w
                b += c.blueF() * w
                wsum += w
        if wsum > 0:
            avg = QColor.fromRgbF(r / wsum, g / wsum, b / wsum)
            h, s, v = avg.hsvHueF(), avg.hsvSaturationF(), avg.valueF()
            if s < 0.12 or h < 0:   # серая иконка — нейтральная графитовая подложка
                col = QColor("#59607a")
            else:
                col = QColor.fromHsvF(h, max(s, 0.5), min(max(v, 0.6), 0.82))
    if col is None:
        col = name_color(fallback)
    _COLOR_CACHE[ck] = col
    return col


def icon3d(spec: str, fallback: str, size: int, dpr: float = 1.0, glyph: str = "") -> QPixmap:
    """Объёмная иконка: подложка с градиентом, бликом, внутренней тенью и мягкой тенью снизу.
    Без иконки в теме рисуется glyph или первая буква fallback. Рисуется один раз на
    (иконку, размер) и дальше берётся из кэша."""
    ck = (spec, "" if spec else fallback, size, dpr, glyph)
    pm = _ICON_CACHE.get(ck)
    if pm is not None:
        return pm
    icon = resolve_icon(spec)
    base = dominant_color(spec, fallback)
    W, H = int(size * 1.34), int(size * 1.42)
    pm = QPixmap(int(W * dpr), int(H * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    x0, y0 = (W - size) / 2, size * 0.08
    rad = size * 0.25
    depth = size * 0.07
    face = QRectF(x0, y0, size, size)

    # мягкая тень: несколько полупрозрачных слоёв вместо размытия
    p.setPen(Qt.PenStyle.NoPen)
    for i in range(7, 0, -1):
        p.setBrush(QColor(0, 0, 0, 14))
        p.drawRoundedRect(face.adjusted(-i * 0.6, depth + i * 0.9, i * 0.6, depth + i * 1.1),
                          rad + i, rad + i)
    # «торец» подложки — ощущение толщины
    side = QLinearGradient(0, y0 + depth, 0, y0 + size + depth)
    side.setColorAt(0, base.darker(190))
    side.setColorAt(1, base.darker(260))
    p.setBrush(QBrush(side))
    p.drawRoundedRect(face.translated(0, depth), rad, rad)
    # лицевая сторона: вертикальный градиент
    grad = QLinearGradient(0, y0, 0, y0 + size)
    grad.setColorAt(0, base.lighter(138))
    grad.setColorAt(0.55, base)
    grad.setColorAt(1, base.darker(122))
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(face, rad, rad)

    path = QPainterPath()
    path.addRoundedRect(face, rad, rad)
    p.save()
    p.setClipPath(path)
    # внутренняя тень по нижнему краю
    inner = QLinearGradient(0, y0 + size * 0.55, 0, y0 + size)
    inner.setColorAt(0, QColor(0, 0, 0, 0))
    inner.setColorAt(1, QColor(0, 0, 0, 70))
    p.setBrush(QBrush(inner))
    p.drawRect(face)
    # блик сверху
    gloss = QLinearGradient(0, y0, 0, y0 + size * 0.5)
    gloss.setColorAt(0, QColor(255, 255, 255, 120))
    gloss.setColorAt(1, QColor(255, 255, 255, 0))
    p.setBrush(QBrush(gloss))
    p.drawEllipse(QRectF(x0 - size * 0.25, y0 - size * 0.62, size * 1.5, size * 1.08))
    p.restore()
    # светлая кромка сверху и тёмная снизу
    edge = QLinearGradient(0, y0, 0, y0 + size)
    edge.setColorAt(0, QColor(255, 255, 255, 140))
    edge.setColorAt(0.4, QColor(255, 255, 255, 20))
    edge.setColorAt(1, QColor(0, 0, 0, 60))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QBrush(edge), max(1.0, size / 48)))
    p.drawRoundedRect(face.adjusted(0.5, 0.5, -0.5, -0.5), rad, rad)

    # сама иконка (или первая буква названия) с маленькой собственной тенью
    isz = int(size * 0.62)
    ix, iy = x0 + (size - isz) / 2, y0 + (size - isz) / 2
    if not icon.isNull():
        ip = icon.pixmap(QSize(isz, isz), dpr)
        sh = ip.toImage()
        sp = QPainter(sh)
        sp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        sp.fillRect(sh.rect(), QColor(0, 0, 0, 90))
        sp.end()
        p.drawImage(QRectF(ix, iy + size * 0.035, isz, isz), sh)
        p.drawPixmap(QRectF(ix, iy, isz, isz), ip, QRectF(ip.rect()))
    else:
        f = QFont()
        f.setPixelSize(int(size * 0.46))
        f.setWeight(QFont.Weight.Bold)
        p.setFont(f)
        letter = glyph or (fallback.strip("_") or "?")[:1].upper()
        p.setPen(QColor(0, 0, 0, 80))
        p.drawText(face.translated(0, size * 0.03), Qt.AlignmentFlag.AlignCenter, letter)
        p.setPen(QColor(255, 255, 255, 240))
        p.drawText(face, Qt.AlignmentFlag.AlignCenter, letter)
    p.end()
    _ICON_CACHE[ck] = pm
    return pm


class RingGauge(QWidget):
    """Крупный «объёмный» кольцевой индикатор."""

    D = 112

    def __init__(self, title: str, c1: str, c2: str):
        super().__init__()
        self.title, self.c1, self.c2 = title, QColor(c1), QColor(c2)
        self.frac, self.value, self.sub = 0.0, "—", ""
        self.setMinimumWidth(140)
        self.setFixedHeight(self.D + 62)

    def set(self, frac: float, value: str, sub: str) -> None:
        frac = max(0.0, min(1.0, frac))
        if (round(frac, 3), value, sub) != (round(self.frac, 3), self.value, self.sub):
            self.frac, self.value, self.sub = frac, value, sub
            self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        d = self.D
        cx = self.width() / 2
        r = QRectF(cx - d / 2, 4, d, d)
        # тень под диском
        sh = QRadialGradient(cx, r.bottom(), d * 0.5)
        sh.setColorAt(0, QColor(0, 0, 0, 110))
        sh.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(sh))
        p.drawEllipse(QRectF(cx - d * 0.5, r.bottom() - 12, d, 22))
        # выпуклый диск
        base = pal.color(QPalette.ColorRole.Base)
        disc = QRadialGradient(cx - d * 0.2, r.top() + d * 0.18, d * 0.9)
        disc.setColorAt(0, base.lighter(175))
        disc.setColorAt(1, base.darker(115))
        p.setBrush(QBrush(disc))
        p.drawEllipse(r)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.drawEllipse(r.adjusted(0.5, 0.5, -0.5, -0.5))
        # дорожка (утопленная)
        ring = r.adjusted(14, 14, -14, -14)
        p.setPen(QPen(QColor(0, 0, 0, 80), 12))
        p.drawEllipse(ring)
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        p.drawEllipse(ring.adjusted(6, 6, -6, -6))
        # значение: дуга с градиентом и светлой полоской-бликом
        if self.frac > 0.003:
            span = -int(self.frac * 360 * 16)
            cg = QConicalGradient(ring.center(), 90)
            cg.setColorAt(0, self.c1)
            cg.setColorAt(1 - min(0.999, self.frac), self.c2)
            cg.setColorAt(1, self.c1)
            p.setPen(QPen(QBrush(cg), 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(ring, 90 * 16, span)
            p.setPen(QPen(QColor(255, 255, 255, 80), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(ring.adjusted(-3, -3, 3, 3), 90 * 16, span)
        # текст
        p.setPen(pal.color(QPalette.ColorRole.WindowText))
        f = QFont(self.font())
        f.setPixelSize(21 if len(self.value) <= 5 else 17)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, self.value)
        f.setPixelSize(14)
        p.setFont(f)
        p.drawText(QRectF(0, r.bottom() + 14, self.width(), 20), Qt.AlignmentFlag.AlignHCenter, self.title)
        f.setWeight(QFont.Weight.Normal)
        f.setPixelSize(12)
        p.setFont(f)
        p.setPen(pal.color(QPalette.ColorRole.PlaceholderText))
        p.drawText(QRectF(0, r.bottom() + 35, self.width(), 18), Qt.AlignmentFlag.AlignHCenter, self.sub)
        p.end()


class AppCard(QWidget):
    """Карточка приложения. Рисуется целиком в paintEvent — без дочерних виджетов."""

    H = 150
    MIN_W = 214
    HIST = 24

    def __init__(self, page: "ProcessesPage", gkey: tuple):
        super().__init__()
        self.page, self.gkey = page, gkey
        self.name, self.icon, self.sub = "", None, ""
        self.cpu = self.mem = self.mem_frac = 0.0
        self.accent = ACCENT
        self.hist: list[float] = []
        self.hover_menu = False
        self.setMouseTracking(True)
        self.resize(self.MIN_W, self.H)

    def set_data(self, name, icon, cpu, mem, mem_frac, sub, tick: bool) -> None:
        if tick:   # история пополняется только по опросу, а не при поиске или сворачивании
            self.hist.append(cpu)
            if len(self.hist) > self.HIST:
                del self.hist[0]
        if icon != self.icon:
            self.accent = dominant_color(icon, self.gkey[1])
        if (name, sub) != (self.name, self.sub):
            self.setToolTip(f"<b>{html.escape(name)}</b><br>{html.escape(sub)}<br>"
                            "Двойной щелчок — подробности, правая кнопка — действия")
        self.name, self.icon, self.cpu, self.mem, self.mem_frac, self.sub = \
            name, icon, cpu, mem, mem_frac, sub
        self.update()

    def _menu_rect(self) -> QRectF:
        return QRectF(self.width() - 36, 10, 26, 22)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self.palette()
        w, h = self.width(), self.height()
        text = pal.color(QPalette.ColorRole.WindowText)
        muted_c = pal.color(QPalette.ColorRole.PlaceholderText)
        accent = self.accent
        rect = QRectF(1.5, 1.5, w - 3, h - 3)
        bg = pal.color(QPalette.ColorRole.Base)
        dark = bg.lightness() < 128
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0, bg.lighter(125) if dark else bg)
        g.setColorAt(1, bg)
        p.setPen(QPen(QColor(255, 255, 255, 22) if dark else QColor(0, 0, 0, 28), 1))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(rect, 14, 14)
        if self.cpu > 5:   # активное приложение: тонкое цветное «свечение» из двух обводок
            glow = QColor(accent)
            glow.setAlpha(70)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(glow, 3.5))
            p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 13, 13)
            p.setPen(QPen(accent.lighter(130), 1.3))
            p.drawRoundedRect(rect, 14, 14)

        p.drawPixmap(6, 6, icon3d(self.icon or "", self.gkey[1], 48, self.devicePixelRatioF()))

        f = QFont(self.font())
        f.setPixelSize(14)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        p.setPen(text)
        tx = 78
        tw = w - tx - 38
        p.drawText(QRectF(tx, 12, tw, 20), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   QFontMetrics(f).elidedText(self.name, Qt.TextElideMode.ElideRight, int(tw)))
        f.setPixelSize(12)
        f.setWeight(QFont.Weight.Normal)
        p.setFont(f)
        p.setPen(muted_c)
        p.drawText(QRectF(tx, 32, w - tx - 12, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   QFontMetrics(f).elidedText(self.sub, Qt.TextElideMode.ElideRight, int(w - tx - 12)))
        # кнопка «…»
        mr = self._menu_rect()
        p.setPen(Qt.PenStyle.NoPen)
        if self.hover_menu:
            p.setBrush(QColor(128, 128, 128, 70))
            p.drawRoundedRect(mr, 6, 6)
        p.setBrush(muted_c)
        for i in (-6, 0, 6):
            p.drawEllipse(QPointF(mr.center().x() + i, mr.center().y()), 1.8, 1.8)
        # мини-полоски истории загрузки ЦП
        sx, sy, sh, sw = tx, 56, 18, w - tx - 14
        bw = sw / self.HIST
        off = self.HIST - len(self.hist)
        for i, v in enumerate(self.hist):
            k = min(1.0, v / 25)
            hh = max(2.0, k * sh)
            col = QColor(accent)
            col.setAlpha(90 + int(k * 165))
            p.setBrush(col)
            p.drawRoundedRect(QRectF(sx + (off + i) * bw, sy + sh - hh, max(1.5, bw - 1.6), hh), 1, 1)
        # полоски ЦП и памяти
        for row, (label, val, frac, c) in enumerate((
                ("ЦП", f"{fmt_num(self.cpu)} %", self.cpu / 100, ACCENT),
                ("Память", fmt_mem(self.mem), self.mem_frac, MEM_COLOR))):
            y = 84 + row * 30
            p.setPen(muted_c)
            p.drawText(QRectF(14, y, 80, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            p.setPen(text)
            p.drawText(QRectF(w / 2, y, w / 2 - 14, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, val)
            track = QRectF(14, y + 19, w - 28, 5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(128, 128, 128, 55))
            p.drawRoundedRect(track, 2.5, 2.5)
            if frac > 0.0005:
                bar = QRectF(track.x(), track.y(), max(5.0, track.width() * min(1.0, frac)), 5)
                bg_ = QLinearGradient(bar.topLeft(), bar.topRight())
                bg_.setColorAt(0, c.darker(115))
                bg_.setColorAt(1, c.lighter(130))
                p.setBrush(QBrush(bg_))
                p.drawRoundedRect(bar, 2.5, 2.5)
        p.end()

    def mouseMoveEvent(self, e) -> None:
        hv = self._menu_rect().contains(e.position())
        if hv != self.hover_menu:
            self.hover_menu = hv
            self.setCursor(Qt.CursorShape.PointingHandCursor if hv else Qt.CursorShape.ArrowCursor)
            self.update()

    def leaveEvent(self, _e) -> None:
        if self.hover_menu:
            self.hover_menu = False
            self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self._menu_rect().contains(e.position()):
            self.page.card_menu(self, self.mapToGlobal(self._menu_rect().bottomLeft().toPoint()))

    def mouseDoubleClickEvent(self, _e) -> None:
        self.page.show_details(self.gkey)

    def contextMenuEvent(self, e) -> None:
        self.page.card_menu(self, e.globalPos())


class CardGrid(QWidget):
    """Адаптивная сетка: число колонок зависит от ширины, карточки растягиваются по ширине.
    Раскладка пересчитывается только при смене ширины или порядка карточек."""

    SP = 12

    def __init__(self):
        super().__init__()
        self.cards: list[AppCard] = []
        self._geom_key = None
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(0)

    def set_cards(self, cards: list[AppCard]) -> None:
        keep = set(map(id, cards))
        for c in self.cards:
            if id(c) not in keep:
                c.hide()
        self.cards = cards
        self._relayout()

    def resizeEvent(self, _e) -> None:
        self._relayout()

    def _relayout(self) -> None:
        w = max(self.width(), AppCard.MIN_W)
        cols = max(1, (w + self.SP) // (AppCard.MIN_W + self.SP))
        cw = (w - (cols - 1) * self.SP) // cols
        key = (w, tuple(map(id, self.cards)))
        if key == self._geom_key:
            return
        self._geom_key = key
        for i, c in enumerate(self.cards):
            if c.parent() is not self:
                c.setParent(self)
            c.setGeometry((i % cols) * (cw + self.SP), (i // cols) * (AppCard.H + self.SP), cw, AppCard.H)
            c.show()
        rows = (len(self.cards) + cols - 1) // cols
        self.setFixedHeight(max(0, rows * (AppCard.H + self.SP) - self.SP))


class CardSection(QWidget):
    """Раздел карточек со сворачиваемым заголовком и кнопкой «Показать все»."""

    def __init__(self, title: str, hint: str, expanded: bool, empty: str = ""):
        super().__init__()
        self.title = title
        self.show_all = False
        self.total = 0
        self.on_change = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(6)
        head = QHBoxLayout()
        self.toggle = QToolButton(checkable=True, checked=expanded)
        self.toggle.setObjectName("sectionToggle")
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle.toggled.connect(self._toggled)
        head.addWidget(self.toggle)
        head.addStretch(1)
        self.more = QPushButton("Показать все", objectName="link")
        self.more.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more.clicked.connect(self._more)
        head.addWidget(self.more)
        lay.addLayout(head)
        self.hint = muted(hint)
        lay.addWidget(self.hint)
        self.grid = CardGrid()
        lay.addWidget(self.grid)
        self.empty_text = empty
        self.empty = muted(empty)
        lay.addWidget(self.empty)
        self._toggled(expanded)

    def expanded(self) -> bool:
        return self.toggle.isChecked()

    def _toggled(self, on: bool) -> None:
        self.toggle.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)
        self.grid.setVisible(on)
        self.hint.setVisible(on)
        self._update_more()
        if self.on_change:
            self.on_change()

    def _more(self) -> None:
        self.show_all = not self.show_all
        self._update_more()
        if self.on_change:
            self.on_change()

    def _update_more(self) -> None:
        self.more.setVisible(self.expanded() and self.total > CARD_LIMIT)
        self.more.setText(f"Только первые {CARD_LIMIT}" if self.show_all else f"Показать все ({self.total})")

    def set_header(self, total: int, nproc: int, searching: bool) -> None:
        self.total = total
        text = f"{self.title}  ·  {nproc_text(nproc)}"
        if self.toggle.text() != text:
            self.toggle.setText(text)
        empty = "Ничего не найдено." if searching else self.empty_text
        if self.empty.text() != empty:
            self.empty.setText(empty)
        self.empty.setVisible(self.expanded() and total == 0 and bool(empty))
        self.hint.setVisible(self.expanded() and total > 0)
        self._update_more()


class DetailsDialog(QDialog):
    """Подробности о группе процессов: PID, пользователь, ЦП, память и командная строка."""

    STATES = {"R": "работает", "S": "ожидает", "D": "ввод-вывод", "Z": "зомби", "T": "остановлен",
              "I": "простаивает", "t": "отладка"}

    def __init__(self, page: "ProcessesPage", title: str, procs: list[dict]):
        super().__init__(page)
        self.page = page
        self.procs = {p["pid"]: p for p in procs}
        self.setWindowTitle(f"{title} — процессы")
        self.resize(860, 440)
        lay = QVBoxLayout(self)
        lay.addWidget(heading(title, "h2"))
        lay.addWidget(muted(f"{nproc_text(len(procs))} · ЦП {fmt_num(sum(p['cpu'] for p in procs))} % · "
                            f"память {fmt_mem(sum(p['mem'] for p in procs))}"))
        self.table = QTableWidget(len(procs), 6)
        self.table.setHorizontalHeaderLabels(["PID", "Пользователь", "Состояние", "ЦП %", "Память",
                                              "Командная строка"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        for row, pr in enumerate(sorted(procs, key=lambda q: (-q["cpu"], -q["mem"]))):
            cmd = " ".join(pr["argv"]) or f"[{pr['comm']}]"
            vals = [str(pr["pid"]), page.users.get(pr["uid"], str(pr["uid"])),
                    self.STATES.get(pr["state"], pr["state"]), fmt_num(pr["cpu"]), fmt_mem(pr["mem"]), cmd]
            for col, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if col in (0, 3, 4):
                    it.setTextAlignment(right)
                if col == 5:
                    it.setToolTip(cmd)
                it.setData(Qt.ItemDataRole.UserRole, pr["pid"])
                self.table.setItem(row, col, it)
        self.table.resizeColumnsToContents()
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        kill = QPushButton(QIcon.fromTheme("process-stop"), "Завершить выбранные")
        kill.clicked.connect(self._kill)
        row.addWidget(kill)
        row.addStretch(1)
        close = QPushButton("Закрыть", objectName="primary")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)

    def _kill(self) -> None:
        rows = {i.row() for i in self.table.selectedItems()}
        pids = [self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in rows]
        if not pids:
            QMessageBox.information(self, "AIsktagOS", "Выберите процессы в таблице.")
        elif self.page.terminate([self.procs[p] for p in pids], "выбранные процессы"):
            self.accept()


class ElidedLabel(QLabel):
    """Приглушённая подпись в одну строку с «…» — длинная команда не раздвигает страницу."""

    def __init__(self):
        super().__init__(objectName="muted")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setPen(self.palette().color(self.foregroundRole()))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideMiddle, self.width()))
        p.end()


class DownloadRow(QWidget):
    """Строка блока «Сейчас скачивается»: иконка, подпись, команда и неопределённый индикатор."""

    def __init__(self, label: str, icon: str, key: str):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        ic = QLabel()
        ic.setPixmap(icon3d(icon, key, 34, glyph="↓"))
        lay.addWidget(ic)
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(QLabel(f"<b>{html.escape(label)}</b>"))
        self.detail = ElidedLabel()
        col.addWidget(self.detail)
        lay.addLayout(col, 1)
        bar = QProgressBar()
        bar.setRange(0, 0)    # неопределённый индикатор: точный прогресс знают только сами программы
        bar.setTextVisible(False)
        bar.setFixedSize(150, 8)
        lay.addWidget(bar)

    def set_detail(self, text: str) -> None:
        if self.detail.text() != text:
            self.detail.setText(text)


class ProcessesPage(QWidget):
    def __init__(self):
        super().__init__()
        self.scanner = ProcScanner()
        self.desktop: DesktopIndex | None = None   # ярлыки читаются при первом показе страницы
        self.users = users_by_uid()
        self.cards: dict[tuple, AppCard] = {}
        self.groups: dict[tuple, dict] = {}
        self.titles: dict[tuple, tuple[str, str]] = {}
        self.dl_rows: dict[str, DownloadRow] = {}
        self.ema: dict[tuple, float] = {}
        self.net_peak = 256 * 1024
        self.last_poll_ms = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(POLL_MS)
        self.timer.timeout.connect(self.poll)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        col = QVBoxLayout()
        col.addWidget(heading("Процессы"))
        col.addWidget(muted("Всё, что сейчас работает на компьютере. Обновляется каждые 2 секунды. "
                            "Правая кнопка мыши по карточке — подробности и завершение."))
        top.addLayout(col, 1)
        self.search = QLineEdit(placeholderText="Поиск: имя или PID", objectName="search")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(QIcon.fromTheme("edit-find"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setFixedWidth(240)
        self.search.textChanged.connect(lambda _t: self.refresh_view())
        top.addWidget(self.search, 0, Qt.AlignmentFlag.AlignBottom)
        lay.addLayout(top)

        body = QWidget()
        self.body = QVBoxLayout(body)
        self.body.setContentsMargins(0, 10, 8, 8)
        self.body.setSpacing(14)

        gauges = QFrame(objectName="card")
        gl = QHBoxLayout(gauges)
        gl.setContentsMargins(8, 14, 8, 8)
        self.g_cpu = RingGauge("Процессор", "#a99fff", "#6d5dfc")
        self.g_mem = RingGauge("Память", "#5ce6c8", "#1f9e88")
        self.g_proc = RingGauge("Процессы", "#ffc77a", "#f07b3f")
        self.g_net = RingGauge("Сеть", "#7fcbff", "#3a7bff")
        for g in (self.g_cpu, self.g_mem, self.g_proc, self.g_net):
            gl.addWidget(g)
        self.body.addWidget(gauges)

        self.dl_box = QFrame(objectName="dlcard")
        dl = QVBoxLayout(self.dl_box)
        dl.setContentsMargins(16, 12, 16, 10)
        dh = QHBoxLayout()
        dh.addWidget(heading("Сейчас скачивается / устанавливается", "h2"), 1)
        self.dl_speed = QLabel(objectName="speed")
        dh.addWidget(self.dl_speed)
        dl.addLayout(dh)
        self.dl_list = QVBoxLayout()
        self.dl_list.setSpacing(0)
        dl.addLayout(self.dl_list)
        self.dl_box.setVisible(False)
        self.body.addWidget(self.dl_box)

        self.sections = {
            "apps": CardSection("Приложения", "Программы из меню, которые сейчас открыты.", True,
                                "Сейчас нет открытых приложений."),
            "user": CardSection("Фоновые программы", "Ваши процессы без окна: оболочки, скрипты, агенты.",
                                True),
            "system": CardSection("Системные службы", "Службы root и других пользователей, потоки ядра. "
                                  "Для их завершения понадобится пароль администратора.", False),
        }
        for s in self.sections.values():
            s.on_change = lambda: self.refresh_view()
            self.body.addWidget(s)
        self.body.addStretch(1)

        scroll = QScrollArea(widgetResizable=True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        lay.addWidget(scroll, 1)

    # ── опрос идёт только пока страница видима ──
    def showEvent(self, e) -> None:
        super().showEvent(e)
        self.poll()
        QTimer.singleShot(400, self.poll)   # быстрый второй замер, чтобы ЦП% появились сразу
        self.timer.start()

    def hideEvent(self, e) -> None:
        super().hideEvent(e)
        self.timer.stop()

    def poll(self) -> None:
        if not self.isVisible():
            return
        t0 = time.perf_counter()
        if self.desktop is None:
            self.desktop = DesktopIndex()
        sc = self.scanner
        procs = sc.scan()
        groups: dict[tuple, dict] = {}
        downloads: dict[str, list] = {}
        lookup = self.desktop.lookup
        for p in procs:
            key = p["key"]
            if key == "__kernel" or p["uid"] != MY_UID:
                sect = "system"
            else:
                sect = "apps" if lookup(key) else "user"
            gk = (sect, key)
            g = groups.get(gk)
            if g is None:
                g = groups[gk] = {"procs": [], "cpu": 0.0, "mem": 0.0, "uids": set()}
            g["procs"].append(p)
            g["cpu"] += p["cpu"]
            g["mem"] += p["mem"]
            g["uids"].add(p["uid"])
            act = download_activity(p)
            if act:
                downloads.setdefault(act[2], [act, []])[1].append(p)
        ema = {}
        for gk, g in groups.items():   # сглаженный ЦП — чтобы карточки не прыгали
            ema[gk] = 0.5 * g["cpu"] + 0.5 * self.ema.get(gk, g["cpu"])
        self.ema, self.groups = ema, groups

        # сводка
        n = len(procs)
        mine = sum(1 for p in procs if p["uid"] == MY_UID and p["key"] != "__kernel")
        self.g_cpu.set(sc.cpu_total_pct / 100, f"{sc.cpu_total_pct:.0f}%",
                       plural(sc.ncpu, "ядро", "ядра", "ядер"))
        mfrac = sc.mem_used / sc.mem_total if sc.mem_total else 0
        self.g_mem.set(mfrac, f"{mfrac * 100:.0f}%",
                       f"{fmt_num(sc.mem_used / 1024)} из {fmt_num(sc.mem_total / 1024)} ГБ")
        self.g_proc.set(mine / n if n else 0, str(n), f"ваших: {mine}")
        self.net_peak = max(self.net_peak * 0.97, sc.net_rx, 256 * 1024)
        speed = fmt_speed(sc.net_rx)
        self.g_net.set(sc.net_rx / self.net_peak, speed, f"приём · отдача {fmt_speed(sc.net_tx)}")
        self._update_downloads(downloads)
        self.refresh_view(tick=True)
        self.last_poll_ms = (time.perf_counter() - t0) * 1000

    def _update_downloads(self, downloads: dict) -> None:
        for k in [k for k in self.dl_rows if k not in downloads]:
            self.dl_rows.pop(k).deleteLater()
        for k, ((label, icon, _k), ps) in downloads.items():
            row = self.dl_rows.get(k)
            if row is None:
                row = self.dl_rows[k] = DownloadRow(label, icon, k)
                self.dl_list.addWidget(row)
            p = max(ps, key=lambda q: len(q["argv"]))
            cmd = " ".join(p["argv"]) or p["comm"]
            row.set_detail(f"{cmd}  ·  PID {p['pid']}")
        self.dl_box.setVisible(bool(downloads))
        if downloads:
            sc = self.scanner
            self.dl_speed.setText(f"↓ {fmt_speed(sc.net_rx)}   ↑ {fmt_speed(sc.net_tx)}")

    def _group_title(self, gk: tuple) -> tuple[str, str]:
        """Название и иконка группы: из .desktop, из словаря известных служб или по имени файла."""
        t = self.titles.get(gk)
        if t is not None:
            return t
        sect, key = gk
        hit = self.desktop.lookup(key) if self.desktop else None
        if hit and (sect == "apps" or key not in KNOWN_NAMES):
            t = hit
        else:
            icon = key if QIcon.hasThemeIcon(key) else ("cpu" if key == "__kernel" else "")
            t = (KNOWN_NAMES.get(key, key), icon)
        self.titles[gk] = t
        return t

    def refresh_view(self, tick: bool = False) -> None:
        """Обновить карточки: существующие переиспользуются, меняются только значения."""
        query = self.search.text().strip().lower()
        by_sect: dict[str, list] = {"apps": [], "user": [], "system": []}
        for gk, g in self.groups.items():
            if query:
                name = self._group_title(gk)[0]
                if query not in name.lower() and query not in gk[1].lower() and \
                        not any(query == str(p["pid"]) for p in g["procs"]):
                    continue
            by_sect[gk[0]].append(gk)
        mem_total = self.scanner.mem_total or 1
        for sect, keys in by_sect.items():
            s = self.sections[sect]
            keys.sort(key=lambda k: -(self.ema.get(k, 0) * 2 + self.groups[k]["mem"] / mem_total * 100))
            s.set_header(len(keys), sum(len(self.groups[k]["procs"]) for k in keys), bool(query))
            if not s.expanded():   # свёрнутый раздел не обновляем вовсе
                continue
            cards = []
            for gk in (keys if s.show_all else keys[:CARD_LIMIT]):
                g = self.groups[gk]
                card = self.cards.get(gk)
                if card is None:
                    card = self.cards[gk] = AppCard(self, gk)
                name, icon = self._group_title(gk)
                sub = nproc_text(len(g["procs"]))
                if sect == "system":
                    owners = sorted(self.users.get(u, str(u)) for u in g["uids"])
                    sub += " · " + ", ".join(owners[:2]) + ("…" if len(owners) > 2 else "")
                card.set_data(name, icon, g["cpu"], g["mem"], g["mem"] / mem_total, sub, tick)
                cards.append(card)
            s.grid.set_cards(cards)
        for gk in [k for k in self.cards if k not in self.groups]:   # приложение закрылось
            self.cards.pop(gk).deleteLater()
            self.titles.pop(gk, None)

    # ── действия ──
    def card_menu(self, card: AppCard, pos) -> None:
        m = QMenu(self)
        m.addAction(QIcon.fromTheme("documentinfo"), "Подробнее…", lambda: self.show_details(card.gkey))
        m.addSeparator()
        m.addAction(QIcon.fromTheme("process-stop"), "Завершить…",
                    lambda: self.terminate(self.groups.get(card.gkey, {}).get("procs", []), card.name))
        m.exec(pos)

    def show_details(self, gk: tuple) -> None:
        g = self.groups.get(gk)
        if g:
            DetailsDialog(self, self._group_title(gk)[0], g["procs"]).exec()

    def terminate(self, procs: list[dict], title: str) -> bool:
        """SIGTERM своим процессам напрямую, чужим — через pkexec kill (после подтверждения)."""
        if not procs:
            return False
        if any(p["pid"] == 1 or p["key"] == "__kernel" for p in procs):
            QMessageBox.information(self, "AIsktagOS", "Потоки ядра и первый процесс системы завершить нельзя.")
            return False
        me = os.getpid()
        warn = ""
        if any(p["key"] in CRITICAL for p in procs):
            warn += "\n\nВнимание: это важная часть системы. Сеанс может закрыться, несохранённые данные пропадут."
        if any(p["pid"] == me for p in procs):
            warn += "\n\nСреди них и сам Центр AIsktagOS — он закроется."
        own = [p["pid"] for p in procs if p["uid"] == MY_UID]
        other = [p["pid"] for p in procs if p["uid"] != MY_UID]
        if other:
            warn += "\n\nЧасть процессов принадлежит другим пользователям — понадобится пароль администратора."
        if QMessageBox.question(self, "Завершить?", f"Завершить «{title}» ({nproc_text(len(procs))})?{warn}") \
                != QMessageBox.StandardButton.Yes:
            return False
        for pid in own:
            if pid == me:
                continue
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except OSError:
                other.append(pid)
        if other:
            QProcess.startDetached("pkexec", ["kill", "-TERM", *map(str, other)])
        if me in own:
            QTimer.singleShot(300, QApplication.quit)
        QTimer.singleShot(700, self.poll)
        return True


class Center(QWidget):
    PAGES = ["welcome", "drivers", "dev", "processes", "system"]

    def __init__(self, page: str):
        super().__init__()
        self.setWindowTitle("Центр AIsktagOS")
        self.setWindowIcon(QIcon.fromTheme("aisktagos-logo", QIcon(LOGO)))
        self.resize(980, 700)

        self.runner = Runner()
        nav = QListWidget(objectName="nav")
        nav.setFixedWidth(210)
        nav.setIconSize(QSize(22, 22))
        for text, icon in (("Добро пожаловать", "aisktagos-logo"), ("Драйверы", "video-display"),
                           ("Разработка", "applications-development"),
                           ("Процессы", "utilities-system-monitor"), ("Система", "computer")):
            nav.addItem(QListWidgetItem(QIcon.fromTheme(icon), text))
        self.stack = QStackedWidget()
        for w in (WelcomePage(), DriversPage(self.runner), DevPage(self.runner), ProcessesPage(),
                  SystemPage()):
            self.stack.addWidget(w)
        nav.currentRowChanged.connect(self.stack.setCurrentIndex)

        right = QVBoxLayout()
        right.setContentsMargins(20, 16, 20, 16)
        right.addWidget(self.stack, 1)
        right.addWidget(self.runner)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(nav)
        root.addLayout(right, 1)
        nav.setCurrentRow(self.PAGES.index(page) if page in self.PAGES else 0)


def main() -> int:
    args = sys.argv[1:]
    page = "welcome"
    if "--page" in args and args.index("--page") + 1 < len(args):
        page = args[args.index("--page") + 1]
    if "--autostart" in args:
        if LIVE or DONE_FLAG.exists():
            return 0
        if has_nvidia():
            page = "drivers"
    app = QApplication(sys.argv)
    app.setApplicationName("aisktag-center")
    app.setDesktopFileName("aisktag-welcome")
    app.setStyleSheet(STYLE)
    w = Center(page)
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
