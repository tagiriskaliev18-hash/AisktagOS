#!/usr/bin/env python3
"""Центр AIsktagOS: приветствие, драйверы видеокарты, инструменты разработчика и сведения о системе.

    aisktag-welcome [--page welcome|drivers|dev|system] [--autostart]
"""
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QProcess, QPropertyAnimation, QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (QApplication, QCheckBox, QFrame, QGraphicsOpacityEffect, QGridLayout,
                             QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox,
                             QPlainTextEdit, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout,
                             QWidget)

DONE_FLAG = Path.home() / ".config/aisktagos/welcome-done"
LIVE = "boot=casper" in Path("/proc/cmdline").read_text()
LOGO = "/usr/share/aisktagos/logo.png"

# Палитра «Cyber-Cyan / Neon-Blue» — та же, что у установщика и темы окон
CYAN = "#22e4ff"
STATUS_COLORS = {"ok": "#2fd27a", "warn": "#febc2e", "info": CYAN, "off": "#7d87ab"}

STYLE = f"""
QWidget {{ font-family: Inter; font-size: 10.5pt; color: #e6ecff; }}
QWidget#root {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0a0f1e, stop:1 #0d1430); }}
QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}

QListWidget#nav {{ background: rgba(14, 20, 38, 0.92); border: none;
    border-right: 1px solid rgba(120, 200, 255, 0.12); padding: 14px 10px; outline: none; }}
QListWidget#nav::item {{ padding: 11px 12px; border-radius: 10px; margin: 3px 0; color: #aeb8da; }}
QListWidget#nav::item:hover {{ background: rgba(34, 228, 255, 0.07); color: #ffffff; }}
QListWidget#nav::item:selected {{ color: #ffffff; border: 1px solid rgba(34, 228, 255, 0.55);
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 rgba(31, 184, 255, 0.35), stop:1 rgba(61, 107, 255, 0.30)); }}

QLabel#h1 {{ font-size: 22pt; font-weight: 600; color: #ffffff; }}
QLabel#h2 {{ font-size: 13.5pt; font-weight: 600; color: #ffffff; }}
QLabel#muted {{ color: #8b95b8; }}

QFrame#card {{ background: rgba(18, 26, 46, 0.85); border: 1px solid rgba(120, 200, 255, 0.14);
    border-radius: 16px; }}

QPushButton {{ background: #16203a; border: 1px solid rgba(120, 200, 255, 0.22); border-radius: 10px;
    padding: 8px 16px; }}
QPushButton:hover {{ border: 1px solid {CYAN}; }}
QPushButton:disabled {{ color: #5b6585; border: 1px solid rgba(120, 200, 255, 0.10); }}
QPushButton#tile {{ text-align: left; padding: 14px 16px; border-radius: 14px;
    background: rgba(18, 26, 46, 0.85); border: 1px solid rgba(120, 200, 255, 0.14); }}
QPushButton#tile:hover {{ border: 1px solid {CYAN}; background: rgba(34, 228, 255, 0.07); }}
QPushButton#tile:pressed {{ background: rgba(61, 123, 255, 0.18); }}
QPushButton#primary {{ color: #ffffff; font-weight: 600; border: 1px solid rgba(34, 228, 255, 0.5);
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1fb8ff, stop:1 #3d6bff); }}
QPushButton#primary:hover {{ border: 1px solid {CYAN};
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4fd0ff, stop:1 #5a85ff); }}
QPushButton#primary:disabled {{ background: #1c2540; color: #5b6585; border: 1px solid transparent; }}

QCheckBox#stack {{ padding: 12px 14px; border-radius: 12px; background: rgba(18, 26, 46, 0.85);
    border: 1px solid rgba(120, 200, 255, 0.14); spacing: 12px; }}
QCheckBox#stack:hover {{ border: 1px solid rgba(34, 228, 255, 0.6); }}
QCheckBox#stack:checked {{ border: 1px solid {CYAN}; background: rgba(61, 123, 255, 0.16); }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px;
    border: 1px solid rgba(120, 200, 255, 0.4); background: #121a2e; }}
QCheckBox::indicator:checked {{ border: 1px solid {CYAN};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.6, fx:0.5, fy:0.5,
                                stop:0 {CYAN}, stop:0.62 {CYAN}, stop:0.7 #121a2e); }}

QPlainTextEdit {{ font-family: 'JetBrains Mono'; font-size: 9pt; border-radius: 12px; padding: 8px;
    background: #070b16; border: 1px solid rgba(120, 200, 255, 0.14); color: #b9f3ff; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: rgba(139, 149, 184, 0.35); border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: rgba(34, 228, 255, 0.6); }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
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


def gpu_status(name: str) -> tuple[str, str]:
    """Состояние драйвера видеокарты: (ok|warn|info, пояснение)."""
    up = name.upper()
    if re.search(r"VMWARE|VIRTUALBOX|QXL|BOCHS|VIRTIO|RED HAT|CIRRUS|HYPER-V", up):
        return "info", "Виртуальная видеокарта — драйвер встроен в ядро"
    if "NVIDIA" in up:
        if Path("/proc/driver/nvidia/version").exists():
            return "ok", "Фирменный драйвер NVIDIA работает"
        return "warn", "Работает открытый драйвер; для игр и CUDA установите фирменный"
    if re.search(r"AMD|ATI|RADEON|INTEL", up):
        return "ok", "Открытый драйвер Mesa работает «из коробки»"
    return "info", "Используется стандартный драйвер ядра"


def card() -> tuple[QFrame, QVBoxLayout]:
    """Карточка со скруглением и тонкой светящейся рамкой."""
    frame = QFrame(objectName="card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(10)
    return frame, lay


def status_dot(kind: str) -> QLabel:
    """Цветной индикатор состояния (не зависит от темы значков)."""
    dot = QLabel()
    dot.setFixedSize(12, 12)
    color = STATUS_COLORS.get(kind, STATUS_COLORS["off"])
    dot.setStyleSheet(f"background: {color}; border-radius: 6px; border: 2px solid rgba(255,255,255,0.18);")
    return dot


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

        keys_card, keys_lay = card()
        keys_lay.addWidget(heading("Горячие клавиши", "h2"))
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
        keys_lay.addWidget(keys)
        lay.addWidget(keys_card)
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
        gpu_card, cl = card()
        cl.addWidget(heading("Видеокарты в этом компьютере", "h2"))
        found = gpus()
        if not found:
            cl.addWidget(muted("Не удалось определить видеокарту (нет lspci)."))
        for g in found:
            kind, note = gpu_status(g)
            row = QHBoxLayout()
            row.setSpacing(12)
            row.addWidget(status_dot(kind), 0, Qt.AlignmentFlag.AlignTop)
            text = QVBoxLayout()
            text.setSpacing(2)
            name = QLabel(g)
            name.setWordWrap(True)
            name.setStyleSheet("font-weight: 600;")
            text.addWidget(name)
            text.addWidget(muted(note))
            row.addLayout(text, 1)
            cl.addLayout(row)
        lay.addWidget(gpu_card)

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

        # Сетка карточек-флажков: название и описание в две строки
        box = QWidget()
        col = QGridLayout(box)
        col.setSpacing(10)
        col.setContentsMargins(0, 4, 6, 4)
        self.checks: list[tuple[QCheckBox, tuple]] = []
        for i, item in enumerate(DEV_STACKS):
            name, desc, _who, _cmd = item
            cb = QCheckBox(f"{name}\n{desc}", objectName="stack")
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            col.addWidget(cb, i // 2, i % 2)
            self.checks.append((cb, item))
        col.setRowStretch(len(DEV_STACKS) // 2 + 1, 1)
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
        info = QFrame(objectName="card")
        grid = QGridLayout(info)
        grid.setContentsMargins(18, 16, 18, 16)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)
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
        grid.setColumnStretch(1, 1)
        lay.addWidget(info)
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


class Center(QWidget):
    PAGES = ["welcome", "drivers", "dev", "system"]

    def __init__(self, page: str):
        super().__init__()
        self.setWindowTitle("Центр AIsktagOS")
        self.setWindowIcon(QIcon.fromTheme("aisktagos-logo", QIcon(LOGO)))
        self.resize(1020, 720)
        # Фон-градиент из STYLE (#root) рисуется только с этим атрибутом
        self.setObjectName("root")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.runner = Runner()
        nav = QListWidget(objectName="nav")
        nav.setFixedWidth(210)
        nav.setIconSize(QSize(22, 22))
        for text, icon in (("Добро пожаловать", "aisktagos-logo"), ("Драйверы", "video-display"),
                           ("Разработка", "applications-development"), ("Система", "computer")):
            nav.addItem(QListWidgetItem(QIcon.fromTheme(icon), text))
        self.stack = QStackedWidget()
        for w in (WelcomePage(), DriversPage(self.runner), DevPage(self.runner), SystemPage()):
            self.stack.addWidget(w)
        # Плавное появление страницы при переключении
        self.fade = QGraphicsOpacityEffect(self.stack)
        self.fade.setOpacity(1.0)
        self.stack.setGraphicsEffect(self.fade)
        self.anim = QPropertyAnimation(self.fade, b"opacity", self)
        self.anim.setDuration(240)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        # После анимации эффект выключаем: иначе страница всё время рисуется через буфер
        self.anim.finished.connect(lambda: self.fade.setEnabled(False))
        nav.currentRowChanged.connect(self._switch)

        right = QVBoxLayout()
        right.setContentsMargins(26, 22, 26, 18)
        right.addWidget(self.stack, 1)
        right.addWidget(self.runner)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(nav)
        root.addLayout(right, 1)
        nav.setCurrentRow(self.PAGES.index(page) if page in self.PAGES else 0)

    def _switch(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.anim.stop()
        self.fade.setEnabled(True)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()


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
