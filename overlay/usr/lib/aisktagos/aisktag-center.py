#!/usr/bin/env python3
"""Центр AIsktagOS: приветствие, ИИ Mind, инструменты разработчика, драйверы и сведения о системе.

    aisktag-welcome [--page welcome|ai|dev|drivers|system] [--autostart]
"""
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/usr/lib/aisktagos")
import aisktag_ai as ai  # noqa: E402
import aisktag_theme as T  # noqa: E402
from PyQt6.QtCore import QEasingCurve, QProcess, QPropertyAnimation, QSize, Qt  # noqa: E402
from PyQt6.QtGui import QGuiApplication, QIcon, QPixmap  # noqa: E402
from PyQt6.QtWidgets import (QApplication, QCheckBox, QFrame, QGraphicsOpacityEffect, QGridLayout,  # noqa: E402
                             QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                             QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QStackedWidget,
                             QVBoxLayout, QWidget)

DONE_FLAG = Path.home() / ".config/aisktagos/welcome-done"
LIVE = os.environ.get("AISKTAG_FORCE_LIVE") == "1" or (
    Path("/proc/cmdline").exists() and "boot=casper" in Path("/proc/cmdline").read_text())
LOGO = "/usr/share/aisktagos/logo.png"

STATUS_COLORS = {"ok": T.C["ok"], "warn": T.C["warn"], "info": T.C["focus"], "off": T.C["muted"], "ai": T.C["ai"]}

STYLE = T.base_qss() + f"""
QListWidget#nav {{ background: {T.C['bg2']}; border: none; border-right: 1px solid {T.rgba('focus', 0.12)};
    padding: 14px 10px; outline: none; }}
QListWidget#nav::item {{ padding: 11px 12px; border-radius: 10px; margin: 3px 0; color: {T.C['text2']}; }}
QListWidget#nav::item:hover {{ background: {T.rgba('focus', 0.08)}; color: {T.C['text']}; }}
QListWidget#nav::item:selected {{ color: #ffffff; border: 1px solid {T.rgba('focus', 0.55)}; background: {T.C['accentStrong']}; }}

QPushButton#tile {{ text-align: left; padding: 14px 16px; border-radius: 14px; }}
QPushButton#tile:hover {{ border: 1px solid {T.C['focus']}; background: {T.C['surface2']}; }}
QPushButton#tile:pressed {{ background: {T.rgba('accent', 0.25)}; }}

QFrame#stackcard {{ background: {T.C['surface']}; border: 1px solid {T.rgba('focus', 0.14)}; border-radius: 12px; }}
QFrame#stackcard:hover {{ border: 1px solid {T.rgba('focus', 0.6)}; }}
QFrame#stackcard[on="true"] {{ border: 1px solid {T.C['focus']}; background: {T.rgba('accent', 0.2)}; }}
QFrame#stackcard[off="true"] {{ background: {T.C['bg2']}; }}
QCheckBox {{ spacing: 12px; background: transparent; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {T.rgba('focus', 0.4)}; background: {T.C['bg2']}; }}
QCheckBox::indicator:checked {{ border: 1px solid {T.C['focus']};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.6, fx:0.5, fy:0.5,
                                stop:0 {T.C['focus']}, stop:0.62 {T.C['focus']}, stop:0.7 {T.C['bg2']}); }}

QPlainTextEdit#log {{ font-family: 'JetBrains Mono'; font-size: 9pt; background: {T.C['bg0']}; color: #b9f3ff; }}
QProgressBar {{ background: {T.C['bg0']}; border: 1px solid {T.rgba('focus', 0.2)}; border-radius: 6px; height: 12px; text-align: center; color: {T.C['text']}; }}
QProgressBar::chunk {{ background: {T.C['ai']}; border-radius: 5px; }}
QFrame#liveBanner {{ background: {T.rgba('warn', 0.14)}; border: 1px solid {T.rgba('warn', 0.6)}; border-radius: 14px; }}
"""

# (название, описание, кто выполняет: root|user, команда, проверка установки: ("bin", имя) | ("flatpak", id))
DEV_STACKS = [
    ("Java", "OpenJDK 21, Maven и Gradle", "root", "apt-get install -y openjdk-21-jdk maven gradle", ("bin", "javac")),
    ("Go", "Компилятор и инструменты Go", "root", "apt-get install -y golang-go", ("bin", "go")),
    (".NET", ".NET SDK от Microsoft (C#, F#)", "root", "apt-get install -y dotnet-sdk-10.0", ("bin", "dotnet")),
    ("Rust", "Стабильный тулчейн, clippy, rustfmt, rust-analyzer", "user",
     "rustup default stable && rustup component add clippy rustfmt rust-analyzer", ("bin", "rustc")),
    ("Базы данных", "PostgreSQL и Redis (серверы и клиенты)", "root",
     "apt-get install -y postgresql postgresql-client redis-server redis-tools", ("bin", "psql")),
    ("Android (adb)", "Отладка по USB: adb и fastboot", "root", "apt-get install -y adb fastboot", ("bin", "adb")),
    ("Wireshark", "Анализ сетевого трафика", "root", "apt-get install -y wireshark", ("bin", "wireshark")),
    ("Виртуальные машины", "virt-manager + QEMU/KVM", "root",
     "apt-get install -y virt-manager qemu-system-x86 libvirt-daemon-system && "
     "usermod -aG libvirt,kvm \"$(id -nu \"$PKEXEC_UID\")\"", ("bin", "virt-manager")),
    ("Claude Code", "ИИ-ассистент для программирования в терминале", "user",
     "npm config set prefix ~/.npm-global && npm install -g @anthropic-ai/claude-code", ("bin", "claude")),
    ("Ollama", "Альтернативный менеджер локальных нейросетей (Mind работает и без него)", "root",
     "curl -fsSL https://ollama.com/install.sh | sh", ("bin", "ollama")),
    ("Расширения VS Code", "Python, Rust, Go, C++, Docker, GitLens, Prettier, ESLint, Continue (ИИ)", "user",
     "for e in ms-python.python rust-lang.rust-analyzer golang.go ms-vscode.cpptools ms-azuretools.vscode-docker "
     "eamodio.gitlens esbenp.prettier-vscode dbaeumer.vscode-eslint Continue.continue; do "
     "code --install-extension $e --force; done", ("bin", "code-never-detected")),
    ("IntelliJ IDEA Community", "IDE для Java/Kotlin (Flathub)", "user",
     "flatpak install -y --noninteractive flathub com.jetbrains.IntelliJ-IDEA-Community",
     ("flatpak", "com.jetbrains.IntelliJ-IDEA-Community")),
    ("PyCharm Community", "IDE для Python (Flathub)", "user",
     "flatpak install -y --noninteractive flathub com.jetbrains.PyCharm-Community",
     ("flatpak", "com.jetbrains.PyCharm-Community")),
    ("Android Studio", "Разработка под Android (Flathub)", "user",
     "flatpak install -y --noninteractive flathub com.google.AndroidStudio", ("flatpak", "com.google.AndroidStudio")),
    ("Podman Desktop", "Контейнеры и Kubernetes с графическим интерфейсом (Flathub)", "user",
     "flatpak install -y --noninteractive flathub io.podman_desktop.PodmanDesktop",
     ("flatpak", "io.podman_desktop.PodmanDesktop")),
    ("Postman", "Тестирование API (Flathub)", "user",
     "flatpak install -y --noninteractive flathub com.getpostman.Postman", ("flatpak", "com.getpostman.Postman")),
    ("DBeaver", "Универсальный клиент баз данных (Flathub)", "user",
     "flatpak install -y --noninteractive flathub io.dbeaver.DBeaverCommunity", ("flatpak", "io.dbeaver.DBeaverCommunity")),
    ("LibreOffice", "Офисный пакет (Word/Excel/PowerPoint-совместимый)", "root",
     "apt-get install -y libreoffice libreoffice-l10n-ru", ("bin", "soffice")),
    ("Telegram", "Мессенджер (Flathub)", "user",
     "flatpak install -y --noninteractive flathub org.telegram.desktop", ("flatpak", "org.telegram.desktop")),
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


def flatpak_apps() -> set[str]:
    if not shutil.which("flatpak"):
        return set()
    try:
        out = subprocess.run(["flatpak", "list", "--app", "--columns=application"],
                             capture_output=True, text=True, timeout=8).stdout
        return set(out.split())
    except (OSError, subprocess.SubprocessError):
        return set()


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


def scrolled(widget: QWidget) -> QScrollArea:
    area = QScrollArea(widgetResizable=True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(widget)
    return area


class Runner(QWidget):
    """Журнал выполнения команд, полоса прогресса и очередь задач."""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.hide()
        self.log = QPlainTextEdit(readOnly=True, objectName="log")
        self.log.setMaximumBlockCount(4000)
        self.log.setMinimumHeight(140)
        lay.addWidget(self.status)
        lay.addWidget(self.bar)
        lay.addWidget(self.log)
        self.proc: QProcess | None = None
        self.queue: list[tuple[str, str, str]] = []
        self.on_idle = None
        self.setVisible(False)  # журнал появляется при первой задаче

    def busy(self) -> bool:
        return self.proc is not None

    def run(self, title: str, who: str, cmd: str) -> None:
        """who: root — через pkexec bash -c; user — bash -lc; pk — pkexec с готовой командой (polkit-действие)."""
        self.setVisible(True)
        self.queue.append((title, who, cmd))
        if not self.busy():
            self._next()

    def _next(self) -> None:
        if not self.queue:
            self.status.setText("Готово.")
            self.bar.hide()
            if self.on_idle:
                self.on_idle()
            return
        title, who, cmd = self.queue.pop(0)
        self.status.setText(f"Выполняется: {title}…")
        self.bar.hide()
        self.log.appendPlainText(f"\n▶ {title}\n$ {cmd}")
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._read)
        self.proc.finished.connect(lambda code, _s, t=title: self._done(t, code))
        if who == "root":
            self.proc.start("pkexec", ["env", "DEBIAN_FRONTEND=noninteractive",
                                       f"PKEXEC_UID={os.getuid()}", "bash", "-c", cmd])
        elif who == "pk":
            self.proc.start("pkexec", shlex.split(cmd))
        else:
            self.proc.start("bash", ["-lc", cmd])

    def _read(self) -> None:
        data = bytes(self.proc.readAllStandardOutput()).decode(errors="replace")
        text = []
        for line in data.splitlines(keepends=True):
            m = re.match(r"PROGRESS (\d+)", line)
            if m:                          # строки прогресса идут в полосу, а не в журнал
                self.bar.show()
                self.bar.setValue(int(m.group(1)))
            else:
                text.append(line)
        if text:
            self.log.insertPlainText("".join(text))
            self.log.ensureCursorVisible()

    def _done(self, title: str, code: int) -> None:
        mark = "✔" if code == 0 else f"✘ (код {code})"
        self.log.appendPlainText(f"{mark} {title}")
        self.proc = None
        self._next()


class WelcomePage(QWidget):
    def __init__(self, goto):
        super().__init__()
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QPixmap(LOGO).scaled(88, 88, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))
        top.addWidget(logo)
        col = QVBoxLayout()
        col.addWidget(heading("Добро пожаловать в AIsktagOS"))
        col.addWidget(muted("Привычная панель задач Windows, свобода Linux и встроенный ИИ. "
                            "Всё для разработки уже установлено — можно сразу работать."))
        top.addLayout(col, 1)
        lay.addLayout(top)

        if LIVE:   # live-режим легко принять за установленную систему — предупреждаем явно
            banner = QFrame(objectName="liveBanner")
            bl = QHBoxLayout(banner)
            bl.setContentsMargins(16, 12, 16, 12)
            txt = QLabel("<b>Вы в live-режиме.</b> Система работает с USB/ISO, и всё, что вы делаете, "
                         "пропадёт после выключения. Чтобы AIsktagOS осталась на диске, установите её.")
            txt.setWordWrap(True)
            btn = QPushButton("Установить AIsktagOS", objectName="primary")
            btn.clicked.connect(lambda: launch("aisktag-install"))
            bl.addWidget(txt, 1)
            bl.addWidget(btn)
            lay.addWidget(banner)
        lay.addSpacing(6)

        grid = QGridLayout()
        tiles = [
            ("Mind — ИИ-ассистент", "Нейросеть на вашем компьютере (Meta+A)", "aisktagos-mind", lambda: launch("aisktag-mind")),
            ("Центр приложений", "Программы из Ubuntu и Flathub", "plasmadiscover", lambda: launch("plasma-discover")),
            ("Обновить систему", "Обновления и новые версии программ", "system-software-update",
             lambda: launch("plasma-discover", "--mode", "update")),
            ("Снимки системы", "Откат к рабочему состоянию (Timeshift)", "timeshift", lambda: launch("timeshift-launcher")),
            ("Настройки", "Экран, звук, сеть, оформление", "preferences-system", lambda: launch("systemsettings")),
            ("Терминал", "kitty + zsh, Ctrl+G — команда из описания", "kitty", lambda: launch("kitty")),
            ("Джарвис — ИИ-агент", "Сам делает задачи: файлы, команды, браузер (Meta+J)", "aisktagos-jarvis",
             lambda: launch("kitty", "--class", "aisktag-jarvis", "--title", "Джарвис", "jarvis")),
        ]
        for i, (t, s, ic, fn) in enumerate(tiles):
            grid.addWidget(tile(t, s, ic, fn), i // 2, i % 2)
        lay.addLayout(grid)
        lay.addSpacing(6)

        keys_card, keys_lay = card()
        keys_lay.addWidget(heading("Горячие клавиши", "h2"))
        keys = QLabel(
            "<table cellspacing=5>"
            "<tr><td><b>Win (Meta)</b></td><td>Меню «Пуск»</td>"
            "<td><b>Meta+Space</b> / <b>Meta+R</b></td><td>Поиск приложений и файлов, калькулятор</td></tr>"
            "<tr><td><b>Meta+A</b></td><td>ИИ-ассистент Mind</td>"
            "<td><b>Ctrl+G</b> в терминале</td><td>Описание → команда</td></tr>"
            "<tr><td><b>Meta+J</b></td><td>ИИ-агент Джарвис</td><td></td><td></td></tr>"
            "<tr><td><b>Meta+E</b></td><td>Файловый менеджер</td>"
            "<td><b>Meta+Enter</b> / <b>Ctrl+Alt+T</b></td><td>Терминал</td></tr>"
            "<tr><td><b>Meta+Tab</b></td><td>Обзор всех окон</td>"
            "<td><b>Meta+←/→</b></td><td>Окно на половину экрана</td></tr>"
            "<tr><td><b>Ctrl+Alt+←/→</b></td><td>Другой рабочий стол</td>"
            "<td><b>Meta+T</b></td><td>Плиточная раскладка окон</td></tr>"
            "<tr><td><b>Meta+1…9</b></td><td>Запуск закреплённых приложений</td>"
            "<td><b>Alt+Shift</b></td><td>Сменить раскладку</td></tr>"
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


class AIPage(QWidget):
    """Встроенный ИИ: состояние, модели из каталога, внешние серверы, подключение инструментов."""

    def __init__(self, runner: Runner):
        super().__init__()
        self.runner = runner
        self.body = QWidget()
        self.lay = QVBoxLayout(self.body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(self.body))
        self.build()

    def build(self) -> None:
        while self.lay.count():
            item = self.lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        lay = self.lay
        cfg = ai.load_config()
        info = ai.list_models()
        total_gb = ai.ram_mb() / 1024
        rec = ai.recommend_model()
        title = heading("ИИ Mind")
        title.setStyleSheet(f"color: {T.C['aiText']};")
        lay.addWidget(title)
        lay.addWidget(muted("Нейросеть работает на вашем компьютере: без интернета, без аккаунтов, без передачи кода. "
                            "Модель просыпается по первому запросу и через 15 минут простоя выгружается из памяти."))

        # --- состояние
        st_card, sl = card()
        state = ai.backend_state() if ai.is_local(cfg) else "external"
        label, kind = {"ready": ("Модель загружена и готова", "ok"), "loading": ("Модель загружается…", "warn"),
                       "idle": ("Спит — запустится по первому запросу (это нормально)", "info"),
                       "missing": ("Служба ИИ не запущена: systemctl status aisktag-llm.socket", "warn"),
                       "external": (f"Используется внешний сервер: {cfg['base_url']}", "ai")}[state]
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(status_dot(kind), 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(QLabel(label), 1)
        sl.addLayout(row)
        sl.addWidget(muted(f"Память компьютера: {total_gb:.0f} ГБ · рекомендуемая модель: <b>{rec}</b> · "
                           f"активная: <b>{info['active']}</b>"))
        btns = QHBoxLayout()
        open_btn = QPushButton("Открыть Mind", objectName="ai")
        open_btn.clicked.connect(lambda: launch("aisktag-mind"))
        web_btn = QPushButton("Веб-интерфейс модели")
        web_btn.clicked.connect(lambda: launch("xdg-open", "http://127.0.0.1:6573"))
        jarvis_btn = QPushButton("Джарвис — агент")
        jarvis_btn.setToolTip("ИИ-агент: сам работает с файлами, командами, приложениями и браузером")
        jarvis_btn.clicked.connect(lambda: launch("kitty", "--class", "aisktag-jarvis", "--title", "Джарвис", "jarvis"))
        btns.addWidget(open_btn)
        btns.addWidget(jarvis_btn)
        btns.addWidget(web_btn)
        btns.addStretch(1)
        sl.addLayout(btns)
        lay.addWidget(st_card)

        # --- модели
        lay.addWidget(heading("Модели", "h2"))
        for m in info["models"]:
            c, cl = card()
            head = QHBoxLayout()
            name = QLabel(f"<b>{m['title']}</b> — {m['name']}")
            head.addWidget(name, 1)
            if m["id"] == rec:
                badge = QLabel("рекомендуется")
                badge.setStyleSheet(f"color: {T.C['ok']}; font-weight: 600;")
                head.addWidget(badge)
            cl.addLayout(head)
            cl.addWidget(muted(f"{m['description']}<br>Размер {m['size_mb'] / 1024:.1f} ГБ · нужно памяти от "
                               f"{m['ram_mb'] / 1024:.1f} ГБ · лицензия {m['license']}"))
            row = QHBoxLayout()
            installed = m.get("installed", m.get("bundled"))
            if m["id"] == info["active"]:
                row.addWidget(QLabel(f"<span style='color:{T.C['ok']}'>● активна</span>"))
            elif installed:
                b = QPushButton("Сделать активной")
                b.clicked.connect(lambda _=False, i=m["id"]: self.act("Смена модели", f"use {i}"))
                row.addWidget(b)
            else:
                b = QPushButton(f"Скачать ({m['size_mb'] / 1024:.1f} ГБ)", objectName="primary")
                b.clicked.connect(lambda _=False, i=m["id"]: self.install(i))
                row.addWidget(b)
            if installed and not m.get("bundled") and m["id"] != info["active"]:
                rm = QPushButton("Удалить")
                rm.setObjectName("ghost")
                rm.clicked.connect(lambda _=False, i=m["id"]: self.act("Удаление модели", f"remove {i}"))
                row.addWidget(rm)
            row.addStretch(1)
            cl.addLayout(row)
            lay.addWidget(c)

        # --- подключение инструментов
        lay.addWidget(heading("Подключить инструменты", "h2"))
        tools, tl = card()
        tl.addWidget(muted("Любой инструмент, умеющий работать с OpenAI-совместимым API, видит локальную модель по адресу "
                           "<b>http://127.0.0.1:6573/v1</b>. Для VS Code уже подготовлен конфиг расширения Continue."))
        trow = QHBoxLayout()
        vs = QPushButton("Подключить к VS Code")
        vs.clicked.connect(lambda: self.runner.run("Расширение Continue для VS Code", "user",
                                                    "code --install-extension Continue.continue --force"))
        env = QPushButton("Скопировать переменные OPENAI_*")
        env.clicked.connect(self.copy_env)
        trow.addWidget(vs)
        trow.addWidget(env)
        trow.addStretch(1)
        tl.addLayout(trow)
        tl.addWidget(muted("В терминале: <b>ai вопрос</b> · <b>ai why</b> (разбор ошибки) · <b>ai commit</b> · "
                           "<b>ai review</b> · <b>Ctrl+G</b> (описание → команда) · <b>Ctrl+Shift+E</b> (объяснить вывод)."))
        lay.addWidget(tools)

        # --- внешний сервер
        lay.addWidget(heading("Другой сервер (по желанию)", "h2"))
        ext, el = card()
        el.addWidget(muted("Вместо локальной модели можно использовать Ollama, LM Studio или облачный сервис с OpenAI-совместимым API. "
                           "Оставьте адрес по умолчанию, чтобы работать локально."))
        self.f_url = QLineEdit(cfg["base_url"])
        self.f_model = QLineEdit(cfg["model"])
        self.f_key = QLineEdit(cfg.get("api_key", ""))
        self.f_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.f_key.setPlaceholderText("ключ API (необязательно)")
        for lbl, w in (("Адрес", self.f_url), ("Модель", self.f_model), ("Ключ", self.f_key)):
            r = QHBoxLayout()
            cap = QLabel(lbl)
            cap.setFixedWidth(60)
            r.addWidget(cap)
            r.addWidget(w, 1)
            el.addLayout(r)
        r = QHBoxLayout()
        save = QPushButton("Сохранить", objectName="primary")
        save.clicked.connect(self.save_cfg)
        reset = QPushButton("Вернуть локальную модель")
        reset.clicked.connect(self.reset_cfg)
        r.addWidget(save)
        r.addWidget(reset)
        r.addStretch(1)
        el.addLayout(r)
        lay.addWidget(ext)
        lay.addStretch(1)

    def act(self, title: str, args: str) -> None:
        self.runner.run(title, "pk", f"{ai.MODEL_HELPER} {args}")

    def install(self, mid: str) -> None:
        self.runner.run("Скачивание модели", "pk", f"{ai.MODEL_HELPER} install {mid}")
        self.runner.run("Активация модели", "pk", f"{ai.MODEL_HELPER} use {mid}")

    def copy_env(self) -> None:
        QGuiApplication.clipboard().setText("eval \"$(ai env)\"")
        QMessageBox.information(self, "Mind", "Скопировано: eval \"$(ai env)\"\nВставьте в терминал — переменные OPENAI_* "
                                              "появятся в текущем сеансе (или запускайте инструмент через «ai run команда»).")

    def save_cfg(self) -> None:
        cfg = ai.load_config()
        cfg.update(base_url=self.f_url.text().strip() or ai.LOCAL_URL, model=self.f_model.text().strip() or "aisktag-mind",
                   api_key=self.f_key.text().strip())
        cfg["provider"] = "local" if cfg["base_url"].startswith("http://127.0.0.1") else "external"
        ai.save_config(cfg)
        self.build()

    def reset_cfg(self) -> None:
        ai.save_config(dict(ai.DEFAULTS))
        self.build()


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


class StackCard(QFrame):
    """Карточка инструмента: флажок, название и описание с переносом строк (у QCheckBox текст не переносится)."""

    def __init__(self, name: str, desc: str, installed: bool):
        super().__init__()
        self.setObjectName("stackcard")
        self.setCursor(Qt.CursorShape.ArrowCursor if installed else Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(2)
        self.cb = QCheckBox(f"{name}{'  ✔ установлено' if installed else ''}")
        self.cb.setEnabled(not installed)
        self.cb.toggled.connect(self._repaint)
        label = muted(desc)
        label.setContentsMargins(28, 0, 0, 0)
        lay.addWidget(self.cb)
        lay.addWidget(label)
        self.setProperty("off", installed)

    def _repaint(self, on: bool) -> None:
        self.setProperty("on", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, e) -> None:
        if self.cb.isEnabled():
            self.cb.toggle()


class DevPage(QWidget):
    """Первый день разработчика (Git, SSH, GitHub) и каталог инструментов с отметкой «установлено»."""

    def __init__(self, runner: Runner):
        super().__init__()
        self.runner = runner
        body = QWidget()
        lay = QVBoxLayout(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(body))
        lay.addWidget(heading("Разработка"))
        lay.addWidget(muted(
            "Уже установлено: <b>VS Code, Git, GitHub CLI, Docker, Podman, Distrobox, Python, Node.js, rustup, "
            "GCC/Clang, CMake, Neovim, lazygit, gdb, jq, ripgrep</b>. Система настроена под разработку: большие лимиты "
            "наблюдателей файлов, zram, Btrfs-снимки. Командой <b>aisktag-new</b> создаётся проект из шаблона."))

        # --- первый день: Git и SSH
        git_card, gl = card()
        gl.addWidget(heading("Первый день: Git и SSH", "h2"))
        gl.addWidget(muted("Один раз укажите имя и почту для коммитов и создайте SSH-ключ для GitHub/GitLab."))
        self.f_name = QLineEdit(self._git("user.name"))
        self.f_name.setPlaceholderText("Имя Фамилия")
        self.f_mail = QLineEdit(self._git("user.email"))
        self.f_mail.setPlaceholderText("почта@пример.рф")
        for lbl, w in (("Имя", self.f_name), ("Почта", self.f_mail)):
            r = QHBoxLayout()
            cap = QLabel(lbl)
            cap.setFixedWidth(60)
            r.addWidget(cap)
            r.addWidget(w, 1)
            gl.addLayout(r)
        row = QHBoxLayout()
        b_git = QPushButton("Сохранить для Git")
        b_git.clicked.connect(self.save_git)
        b_ssh = QPushButton("Создать SSH-ключ", objectName="primary")
        b_ssh.clicked.connect(self.make_ssh)
        b_gh = QPushButton("Войти в GitHub (gh)")
        b_gh.clicked.connect(lambda: launch("kitty", "sh", "-c", "gh auth login; printf '\\nГотово. Enter — закрыть '; read _"))
        for b in (b_git, b_ssh, b_gh):
            row.addWidget(b)
        row.addStretch(1)
        gl.addLayout(row)
        self.pub = QPlainTextEdit(readOnly=True, objectName="log")
        self.pub.setMaximumHeight(70)
        self.pub.hide()
        gl.addWidget(self.pub)
        self.pub_btns = QWidget()
        pb = QHBoxLayout(self.pub_btns)
        pb.setContentsMargins(0, 0, 0, 0)
        cp = QPushButton("Копировать ключ")
        cp.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.pub.toPlainText().strip()))
        gh = QPushButton("Добавить на GitHub…")
        gh.clicked.connect(lambda: launch("xdg-open", "https://github.com/settings/ssh/new"))
        pb.addWidget(cp)
        pb.addWidget(gh)
        pb.addStretch(1)
        self.pub_btns.hide()
        gl.addWidget(self.pub_btns)
        lay.addWidget(git_card)
        self.show_key()

        # --- каталог инструментов
        lay.addWidget(heading("Каталог инструментов", "h2"))
        lay.addWidget(muted("Отметьте, что добавить, и нажмите «Установить»."))
        box = QWidget()
        col = QGridLayout(box)
        col.setSpacing(10)
        col.setContentsMargins(0, 4, 6, 4)
        fp = flatpak_apps()
        self.checks: list[tuple[QCheckBox, tuple]] = []
        for i, item in enumerate(DEV_STACKS):
            name, desc, _who, _cmd, probe = item
            have = (probe[0] == "bin" and shutil.which(probe[1]) is not None) or (probe[0] == "flatpak" and probe[1] in fp)
            card_w = StackCard(name, desc, have)
            col.addWidget(card_w, i // 2, i % 2)
            self.checks.append((card_w.cb, item))
        col.setColumnStretch(0, 1)
        col.setColumnStretch(1, 1)
        lay.addWidget(box)
        row = QHBoxLayout()
        row.addStretch(1)
        self.b_go = QPushButton("Установить выбранное", objectName="primary")
        self.b_go.clicked.connect(self._go)
        row.addWidget(self.b_go)
        lay.addLayout(row)

    @staticmethod
    def _git(key: str) -> str:
        try:
            return subprocess.run(["git", "config", "--global", key], capture_output=True, text=True).stdout.strip()
        except OSError:
            return ""

    def save_git(self) -> None:
        name, mail = self.f_name.text().strip(), self.f_mail.text().strip()
        if not name or "@" not in mail:
            QMessageBox.information(self, "Git", "Укажите имя и корректную почту.")
            return
        subprocess.run(["git", "config", "--global", "user.name", name])
        subprocess.run(["git", "config", "--global", "user.email", mail])
        QMessageBox.information(self, "Git", "Сохранено: теперь коммиты подписываются вашим именем.")

    def make_ssh(self) -> None:
        key = Path.home() / ".ssh/id_ed25519"
        if not key.exists():
            key.parent.mkdir(mode=0o700, exist_ok=True)
            comment = self.f_mail.text().strip() or f"{os.environ.get('USER', 'user')}@aisktagos"
            subprocess.run(["ssh-keygen", "-t", "ed25519", "-C", comment, "-f", str(key), "-N", ""],
                           capture_output=True)
        self.show_key()

    def show_key(self) -> None:
        pub = Path.home() / ".ssh/id_ed25519.pub"
        if pub.exists():
            self.pub.setPlainText(pub.read_text())
            self.pub.show()
            self.pub_btns.show()

    def _go(self) -> None:
        chosen = [item for cb, item in self.checks if cb.isChecked() and cb.isEnabled()]
        if not chosen:
            return
        if any(who == "root" for _n, _d, who, _c, _p in chosen):
            self.runner.run("Обновление списка пакетов", "root", "apt-get update")
        for name, _desc, who, cmd, _probe in chosen:
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
            ("ИИ Mind", f"модель «{ai.list_models()['active']}», рекомендуется «{ai.recommend_model()}»"),
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
        mb = ai.ram_mb()
        return f"{mb / 1024:.1f} ГБ" if mb else "—"

    @staticmethod
    def _disk() -> str:
        u = shutil.disk_usage("/")
        return f"свободно {u.free / 1e9:.0f} ГБ из {u.total / 1e9:.0f} ГБ"


class Center(QWidget):
    PAGES = ["welcome", "ai", "dev", "drivers", "system"]

    def __init__(self, page: str):
        super().__init__()
        self.setWindowTitle("Центр AIsktagOS")
        self.setWindowIcon(QIcon.fromTheme("aisktagos-logo", QIcon(LOGO)))
        self.resize(1060, 740)
        # Фон из STYLE (#root) рисуется только с этим атрибутом
        self.setObjectName("root")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.runner = Runner()
        nav = QListWidget(objectName="nav")
        nav.setFixedWidth(210)
        nav.setIconSize(QSize(22, 22))
        for text, icon in (("Добро пожаловать", "aisktagos-logo"), ("ИИ Mind", "aisktagos-mind"),
                           ("Разработка", "applications-development"), ("Драйверы", "video-display"),
                           ("Система", "computer")):
            nav.addItem(QListWidgetItem(QIcon.fromTheme(icon), text))
        self.stack = QStackedWidget()
        self.ai_page = AIPage(self.runner)
        for w in (WelcomePage(self.goto), self.ai_page, DevPage(self.runner), DriversPage(self.runner), SystemPage()):
            self.stack.addWidget(w)
        self.runner.on_idle = self.ai_page.build      # после установки модели обновляем список
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
        self.nav = nav

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

    def goto(self, name: str) -> None:
        self.nav.setCurrentRow(self.PAGES.index(name))

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
