#!/usr/bin/env python3
"""Центр AIsktagOS: приветствие, драйверы видеокарты, инструменты разработчика и сведения о системе.

    aisktag-welcome [--page welcome|drivers|dev|ecosystem|system] [--autostart]
"""
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import (QByteArray, QEasingCurve, QPoint, QProcess, QPropertyAnimation, QSize, Qt,
                          QVariantAnimation)
from PyQt6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (QApplication, QCheckBox, QFileDialog, QFrame, QGraphicsDropShadowEffect,
                             QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
                             QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

try:
    # MindKit — общие службы экосистемы MindTagSystem (/usr/lib/python3/dist-packages/mindkit)
    from mindkit import keychain as mk_keychain
    from mindkit import link as mk_link
    from mindkit import store as mk_store
except ImportError:
    mk_keychain = mk_link = mk_store = None
try:
    # Единый стиль Mind: иконки с градиентом, пружина и перелив (mindkit/qtfx.py)
    from mindkit import qtfx
except ImportError:
    qtfx = None

DONE_FLAG = Path.home() / ".config/aisktagos/welcome-done"
LIVE = "boot=casper" in Path("/proc/cmdline").read_text()
LOGO = "/usr/share/aisktagos/logo.png"

# Свои иконки в стиле Mind, которых нет в MindKit (история снимков, видеокарта)
# /usr/lib/aisktagos/… → /usr/share/aisktagos/mind-icons (так же работает и из overlay при отладке)
MIND_ICONS = Path(__file__).resolve().parents[2] / "share/aisktagos/mind-icons"

# Единый стиль Mind: фиолетово-синий градиент (как в MindKit tokens.json)
GRADIENT = ("#a46cf0", "#7c66df", "#5b8dee", "#49b3f7")
GRAD_CSS = ", ".join(f"stop:{i / 3:.2f} {c}" for i, c in enumerate(GRADIENT))
CYAN = "#5b8dee"   # акцент (имя оставлено ради совместимости)
VIOLET = "#a46cf0"
STATUS_COLORS = {"ok": "#2fd27a", "warn": "#febc2e", "info": CYAN, "off": "#7d87ab"}


def _reduced_motion() -> bool:
    """Аналог prefers-reduced-motion: в KDE анимации выключаются AnimationDurationFactor=0."""
    try:
        for line in (Path.home() / ".config/kdeglobals").read_text().splitlines():
            if line.startswith("AnimationDurationFactor="):
                return float(line.split("=", 1)[1]) == 0
    except (OSError, ValueError):
        pass
    return os.environ.get("AISKTAG_REDUCED_MOTION") == "1"


REDUCED_MOTION = _reduced_motion()

STYLE = f"""
QWidget {{ font-family: Inter; font-size: 10.5pt; color: #e6ecff; }}
QWidget#root {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0b0a1c, stop:1 #0d1232); }}
QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}

QListWidget#nav {{ background: rgba(16, 15, 38, 0.92); border: none;
    border-right: 1px solid rgba(164, 108, 240, 0.16); padding: 14px 10px; outline: none; }}
QListWidget#nav::item {{ padding: 11px 12px; border-radius: 10px; margin: 3px 0; color: #b4b2da; }}
QListWidget#nav::item:hover {{ background: rgba(164, 108, 240, 0.10); color: #ffffff; }}
QListWidget#nav::item:selected {{ color: #ffffff; border: 1px solid rgba(164, 108, 240, 0.55);
    border-top: 1px solid rgba(255, 255, 255, 0.22);
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 rgba(164, 108, 240, 0.42), stop:1 rgba(73, 179, 247, 0.26)); }}

QLabel#h1 {{ font-size: 22pt; font-weight: 700;
    color: #a46cf0; }}
QLabel#h2 {{ font-size: 13.5pt; font-weight: 600; color: #ffffff; }}
QLabel#muted {{ color: #9693bd; }}

QFrame#card {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(30, 28, 64, 0.92),
                                         stop:1 rgba(18, 18, 44, 0.92));
    border: 1px solid rgba(164, 108, 240, 0.18); border-top: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 16px; }}

QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #24224a, stop:1 #191838);
    border: 1px solid rgba(164, 108, 240, 0.28); border-top: 1px solid rgba(255, 255, 255, 0.16);
    border-bottom: 2px solid rgba(8, 6, 30, 0.7); border-radius: 10px; padding: 8px 16px; }}
QPushButton:hover {{ border: 1px solid {VIOLET}; border-bottom: 2px solid rgba(8, 6, 30, 0.7); }}
QPushButton:pressed {{ border-top: 2px solid rgba(8, 6, 30, 0.7); border-bottom: 1px solid rgba(255, 255, 255, 0.12); }}
QPushButton:disabled {{ color: #5f5c85; border: 1px solid rgba(164, 108, 240, 0.10); }}
QPushButton#tile {{ text-align: left; padding: 14px 16px; border-radius: 14px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(32, 30, 68, 0.92), stop:1 rgba(20, 19, 46, 0.92));
    border: 1px solid rgba(164, 108, 240, 0.18); border-top: 1px solid rgba(255, 255, 255, 0.14);
    border-bottom: 2px solid rgba(8, 6, 30, 0.75); }}
QPushButton#tile:hover {{ border: 1px solid {VIOLET}; border-bottom: 2px solid rgba(8, 6, 30, 0.75);
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(164, 108, 240, 0.20), stop:1 rgba(73, 179, 247, 0.12)); }}
QPushButton#tile:pressed {{ background: rgba(124, 102, 223, 0.26); }}
QPushButton#primary {{ color: #ffffff; font-weight: 600; border: 0; border-radius: 10px;
    border-top: 1px solid rgba(255, 255, 255, 0.38); border-bottom: 2px solid rgba(20, 10, 60, 0.55);
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, {GRAD_CSS}); }}
QPushButton#primary:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #b483f5, stop:0.5 #6f9cf3, stop:1 #5cc4ff); }}
QPushButton#primary:disabled {{ background: #1e1c3a; color: #5f5c85; border: 0; }}

QCheckBox#stack {{ padding: 12px 14px; border-radius: 12px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(30, 28, 64, 0.92), stop:1 rgba(18, 18, 44, 0.92));
    border: 1px solid rgba(164, 108, 240, 0.18); border-top: 1px solid rgba(255, 255, 255, 0.12); spacing: 12px; }}
QCheckBox#stack:hover {{ border: 1px solid rgba(164, 108, 240, 0.7); }}
QCheckBox#stack:checked {{ border: 1px solid {VIOLET};
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(164, 108, 240, 0.24), stop:1 rgba(73, 179, 247, 0.14)); }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px;
    border: 1px solid rgba(164, 108, 240, 0.45); background: #141330; }}
QCheckBox::indicator:checked {{ border: 1px solid rgba(255, 255, 255, 0.35);
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, {GRAD_CSS}); }}

QPlainTextEdit {{ font-family: 'JetBrains Mono'; font-size: 9pt; border-radius: 12px; padding: 8px;
    background: #08071a; border: 1px solid rgba(164, 108, 240, 0.18); color: #cfc4ff; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: rgba(150, 147, 189, 0.35); border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, {GRAD_CSS}); }}
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


def mind_icon(name: str, theme_fallback: str = "", size: int = 48, white: bool = False) -> QIcon:
    """Иконка Mind с фиолетово-синим градиентом (без эмодзи и чужих значков).

    white=True — белый вариант для кнопок, у которых фон уже градиентный."""
    own = MIND_ICONS / f"{name}.svg"
    svg = None
    if white and qtfx is not None:
        try:
            svg = qtfx.design.icon_svg(name, size, gradient=False, color="#ffffff").encode()
        except KeyError:
            svg = None
    elif own.exists():
        svg = own.read_bytes()
    if svg is not None:
        renderer = QSvgRenderer(QByteArray(svg))
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        renderer.render(p)
        p.end()
        return QIcon(pm)
    if qtfx is not None:
        try:
            return qtfx.icon(name, size)
        except (KeyError, ImportError):
            pass
    return QIcon.fromTheme(theme_fallback or name)


def depth(widget: QWidget, blur: int = 28, dy: int = 8, alpha: int = 110) -> None:
    """3D-глубина: мягкая фиолетовая тень под карточкой/кнопкой."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, dy)
    shadow.setColor(QColor(40, 20, 110, alpha))
    widget.setGraphicsEffect(shadow)


def springy(widget: QWidget) -> QWidget:
    """Пружина при наведении и нажатии (bounce из MindKit)."""
    if qtfx is not None and not REDUCED_MOTION:
        qtfx.bounce_on_hover(widget)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def primary(text: str) -> QPushButton:
    """Главная кнопка: объёмная, с переливающимся градиентом Mind и пружиной."""
    b = QPushButton(text, objectName="primary")
    springy(b)
    # Без QGraphicsDropShadowEffect: кнопка часто лежит в карточке с тенью, а вложенные эффекты Qt
    # рисует с ошибками. Объём дают светлая кромка сверху и тёмная снизу.
    if qtfx is not None and not REDUCED_MOTION:
        # qtfx.shimmer задаёт фон самого виджета: выключенная кнопка остаётся серой
        extra = ("color: #ffffff; font-weight: 600; border: 0; border-radius: 10px; padding: 8px 18px;"
                 "border-top: 1px solid rgba(255,255,255,0.38); border-bottom: 2px solid rgba(20,10,60,0.55);")

        def sync(b=b):
            anim = getattr(b, "_mt_shimmer", None)
            if b.isEnabled() and anim is None:
                qtfx.shimmer(b, extra=extra)
            elif not b.isEnabled() and anim is not None:
                anim.stop()
                b._mt_shimmer = None
                b.setStyleSheet("")
        b._mt_sync = sync
        orig = b.setEnabled

        def set_enabled(on: bool, b=b, orig=orig):
            orig(on)
            b._mt_sync()
        b.setEnabled = set_enabled
        sync()
    return b


def card() -> tuple[QFrame, QVBoxLayout]:
    """Карточка с глубиной: светлая кромка сверху и мягкая тень."""
    frame = QFrame(objectName="card")
    depth(frame)
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
        self.log.appendPlainText(f"\n» {title}\n$ {cmd}")
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
        mark = "[готово]" if code == 0 else f"[ошибка, код {code}]"
        self.log.appendPlainText(f"{mark} {title}")
        self.proc = None
        self._next()


class GradientHeading(QLabel):
    """Заголовок с переливающимся фиолетово-синим градиентом (как .mt-gradient-text в вебе).

    QSS-градиент в color Qt растягивает на каждый глиф, поэтому текст рисуем сами."""

    def __init__(self, text: str):
        super().__init__(text)
        self._shift = 0.0
        self._anim = None
        if not REDUCED_MOTION:
            self._anim = QVariantAnimation(self)
            self._anim.setStartValue(0.0)
            self._anim.setKeyValueAt(0.5, 1.0)
            self._anim.setEndValue(0.0)
            self._anim.setDuration(6000)   # тот же период 6 с, что и в mind-ui.css
            self._anim.setLoopCount(-1)
            self._anim.valueChanged.connect(self._tick)

    def _tick(self, v) -> None:
        self._shift = float(v)
        self.update()

    def showEvent(self, e):  # noqa: N802 — имя из Qt
        if self._anim is not None:
            self._anim.start()
        super().showEvent(e)

    def hideEvent(self, e):  # noqa: N802
        if self._anim is not None:
            self._anim.stop()
        super().hideEvent(e)

    def paintEvent(self, _e):  # noqa: N802
        r = self.contentsRect()
        span = max(1, min(self.fontMetrics().horizontalAdvance(self.text()), r.width()))
        off = self._shift * span * 0.6
        g = QLinearGradient(r.left() - off, 0, r.left() - off + span * 1.2, 0)
        g.setSpread(QLinearGradient.Spread.ReflectSpread)
        for pos, col in ((0.0, "#c9a4ff"), (0.3, GRADIENT[0]), (0.55, GRADIENT[1]),
                         (0.8, GRADIENT[2]), (1.0, GRADIENT[3])):
            g.setColorAt(pos, QColor(col))
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setPen(QPen(QBrush(g), 1))
        p.setFont(self.font())
        p.drawText(r, int(self.alignment() | Qt.TextFlag.TextWordWrap), self.text())
        p.end()


def heading(text: str, obj: str = "h1") -> QLabel:
    lbl = GradientHeading(text) if obj == "h1" else QLabel(text)
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
    name, _, fallback = icon.partition(":")
    b.setIcon(mind_icon(name, fallback))
    b.setIconSize(QSize(30, 30))
    b.setMinimumHeight(68)
    b.clicked.connect(action)
    springy(b)
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
                          "download:aisktagos-install", lambda: launch("aisktag-install")))
        tiles += [
            ("Центр приложений", "Программы из Ubuntu и Flathub", "store:plasmadiscover",
             lambda: launch("plasma-discover")),
            ("Обновить систему", "Обновления и новые версии программ", "refresh:system-software-update",
             lambda: launch("plasma-discover", "--mode", "update")),
            ("Снимки системы", "Откат к рабочему состоянию (Timeshift)", "history:timeshift",
             lambda: launch("timeshift-launcher")),
            ("Настройки", "Экран, звук, сеть, оформление", "settings:preferences-system",
             lambda: launch("systemsettings")),
            ("Терминал", "kitty + zsh с подсказками", "terminal:kitty", lambda: launch("kitty")),
            ("VS Code", "Редактор кода", "code:vscode",
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
            "<tr><td><b>Meta+Space</b></td><td>Поиск приложений, файлов, калькулятор и Mind Search (как Spotlight)</td></tr>"
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
        self.b_install = primary("Установить рекомендуемые")
        self.b_install.setIcon(mind_icon("download", white=True))
        self.b_install.clicked.connect(self._install)
        self.b_fw = QPushButton("Обновить прошивки устройств")
        self.b_fw.clicked.connect(lambda: runner.run(
            "Обновление прошивок", "root", "fwupdmgr refresh --force; fwupdmgr update -y --no-reboot-check"))
        self.b_check.setIcon(mind_icon("search"))
        self.b_fw.setIcon(mind_icon("refresh"))
        for b in (self.b_check, self.b_install, self.b_fw):
            row.addWidget(springy(b))
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
            # Длинное описание не должно выталкивать правую колонку за край окна
            cb.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            cb.setToolTip(f"{name}: {desc}")
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
        self.b_go = primary("Установить выбранное")
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


class EcosystemPage(QWidget):
    """MindTagSystem: устройства (MindLink), связка ключей и Mind Store в одном месте."""

    def __init__(self, runner: Runner):
        super().__init__()
        self.runner = runner
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.addWidget(heading("Экосистема MindTagSystem"))
        lay.addWidget(muted(
            "Ваши устройства работают вместе, как у Apple: общий буфер обмена, Handoff, MindDrop, "
            "одна связка ключей для всех программ и каталог приложений экосистемы."))
        if mk_link is None:
            lay.addWidget(muted("MindKit не установлен. Поставьте его: "
                                "<b>pip install git+https://github.com/tagiriskaliev18-hash/MindTagSystem</b>"))
            lay.addStretch(1)
            outer.addWidget(box)
            return

        # MindLink
        c, cl = card()
        cl.addWidget(heading("Мои устройства (MindLink)", "h2"))
        self.link_state = muted("")
        cl.addWidget(self.link_state)
        row = QHBoxLayout()
        self.b_init = primary("Создать аккаунт")
        self.b_init.clicked.connect(self._init)
        self.b_join = QPushButton("Войти по ключу")
        self.b_join.clicked.connect(self._join)
        b_scan = QPushButton("Найти устройства")
        b_scan.clicked.connect(self._scan)
        b_drop = QPushButton("MindDrop: отправить файл…")
        b_drop.clicked.connect(self._drop)
        self.b_join.setIcon(mind_icon("key"))
        b_scan.setIcon(mind_icon("devices"))
        b_drop.setIcon(mind_icon("upload"))
        for b in (self.b_init, self.b_join, b_scan, b_drop):
            row.addWidget(springy(b))
        row.addStretch(1)
        cl.addLayout(row)
        lay.addWidget(c)

        # Связка ключей
        c, cl = card()
        cl.addWidget(heading("Связка ключей Mind", "h2"))
        cl.addWidget(muted("Ключи API хранятся в KWallet и доступны Mind IDE, шлюзу AI Duo, ITIS Browser "
                           "и остальным программам экосистемы. Ввести ключ нужно один раз."))
        self.keys = QVBoxLayout()
        self.keys.setSpacing(6)
        cl.addLayout(self.keys)
        row = QHBoxLayout()
        b_add = QPushButton("Добавить ключ")
        b_add.clicked.connect(self._add_key)
        b_imp = QPushButton("Импорт из .env…")
        b_imp.clicked.connect(self._import_env)
        b_add.setIcon(mind_icon("plus"))
        b_imp.setIcon(mind_icon("file"))
        row.addWidget(springy(b_add))
        row.addWidget(springy(b_imp))
        row.addStretch(1)
        cl.addLayout(row)
        lay.addWidget(c)

        # Mind Store
        c, cl = card()
        cl.addWidget(heading("Mind Store", "h2"))
        cl.addWidget(muted("Приложения экосистемы ставятся из GitHub в папку ~/MindTagSystem."))
        grid = QGridLayout()
        try:
            apps = mk_store.apps()
        except mk_store.StoreError as e:
            apps = []
            cl.addWidget(muted(str(e)))
        for i, app in enumerate(a for a in apps if a["installable"]):
            text = app["name"] + (" · установлено" if app["installed"] else "")
            tagline = app["tagline"] if len(app["tagline"]) <= 40 else app["tagline"][:39].rstrip() + "…"
            b = tile(text, tagline, "play:media-playback-start" if app["installed"] else "download:system-software-install",
                     lambda _=False, a=app: self._store(a))
            # Длинный текст плитки не должен раздвигать страницу шире окна
            b.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            grid.addWidget(b, i // 2, i % 2)
        cl.addLayout(grid)
        lay.addWidget(c)
        lay.addStretch(1)

        scroll = QScrollArea(widgetResizable=True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(box)
        outer.addWidget(scroll)
        self._refresh()

    def _refresh(self) -> None:
        st = mk_link.status()
        has = st["account"]
        names = ", ".join(p["name"] for p in st["peers"].values()) or "пока нет"
        enc = "шифрование AES-GCM" if st["encryption"] else "без шифрования"
        self.link_state.setText(
            f"Это устройство: <b>{st['device']['name']}</b>. " +
            (f"Аккаунт настроен, {enc}. Устройства рядом: <b>{names}</b>." if has else
             "Аккаунт не настроен: создайте его на первом устройстве и войдите по ключу на остальных."))
        self.b_init.setText("Показать ключ" if has else "Создать аккаунт")
        self.b_join.setVisible(not has)
        names = [n for n in mk_keychain.names() if n != mk_link.ACCOUNT_KEY_NAME]
        while self.keys.count():
            w = self.keys.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        key_pm = mind_icon("key").pixmap(18, 18)
        for n in names or [None]:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(8)
            if n is not None:
                ic = QLabel()
                ic.setPixmap(key_pm)
                rl.addWidget(ic)
            rl.addWidget(QLabel(n if n is not None else "Ключей пока нет."), 1)
            self.keys.addWidget(row)

    def _init(self) -> None:
        key = mk_link.init_account()
        subprocess.run(["systemctl", "--user", "restart", "mindlink.service"], check=False)
        QApplication.clipboard().setText(key)
        QMessageBox.information(self, "MindLink", "Ключ аккаунта скопирован в буфер обмена. "
                                "Введите его на других своих устройствах («Войти по ключу» или "
                                f"mindkit link join):\n\n{key}\n\nХраните его как пароль.")
        self._refresh()

    def _join(self) -> None:
        key, ok = QInputDialog.getText(self, "MindLink", "Ключ аккаунта с другого устройства:")
        if not ok or not key.strip():
            return
        try:
            mk_link.join_account(key)
        except ValueError as e:
            QMessageBox.warning(self, "MindLink", f"Ключ не подходит: {e}")
            return
        subprocess.run(["systemctl", "--user", "restart", "mindlink.service"], check=False)
        self._scan()

    def _scan(self) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            mk_link.discover(timeout=2.0)
        finally:
            QApplication.restoreOverrideCursor()
        self._refresh()

    def _drop(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "MindDrop: файл для своих устройств")
        if not path:
            return
        try:
            res = mk_link.drop(path)
        except mk_link.LinkError as e:
            QMessageBox.warning(self, "MindDrop", str(e))
            return
        lines = [f"{k}: " + ("доставлено" if v == "ok" else f"не доставлено ({v})") for k, v in res.items()]
        QMessageBox.information(self, "MindDrop", "\n".join(lines) or "Нет известных устройств")

    def _add_key(self) -> None:
        name, ok = QInputDialog.getText(self, "Связка ключей", "Имя ключа, например GROQ_API_KEY:")
        if not ok or not name.strip():
            return
        value, ok = QInputDialog.getText(self, "Связка ключей", f"Значение {name.strip()}:",
                                         QLineEdit.EchoMode.Password)
        if ok and value:
            try:
                mk_keychain.set(name.strip(), value)
            except ValueError as e:
                QMessageBox.warning(self, "Связка ключей", str(e))
            self._refresh()

    def _import_env(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Файл .env с ключами", str(Path.home()))
        if path:
            self.runner.run("Импорт ключей", "user", f"mindkit keychain import '{path}'")
            self.runner.on_idle = self._refresh

    def _store(self, app: dict) -> None:
        act = "run" if app["installed"] else "install"
        self.runner.run(f"Mind Store: {app['name']}", "user", f"mindkit store {act} {app['id']}")


class SystemPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(heading("О системе"))
        info = QFrame(objectName="card")
        depth(info)
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
        for text, icon, argv in (("Системный монитор", "chart", ("plasma-systemmonitor",)),
                                 ("Информация о системе", "info", ("kinfocenter",)),
                                 ("Разделы дисков", "layers", ("partitionmanager",))):
            b = QPushButton(text)
            b.setIcon(mind_icon(icon))
            b.clicked.connect(lambda _=False, a=argv: launch(*a))
            row.addWidget(springy(b))
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
    PAGES = ["welcome", "drivers", "dev", "ecosystem", "system"]

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
        nav.setFixedWidth(224)
        nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav.setIconSize(QSize(22, 22))
        for text, icon in (("Добро пожаловать", "home"), ("Драйверы", "gpu"),
                           ("Разработка", "code"), ("Экосистема", "devices"),
                           ("Система", "cpu")):
            nav.addItem(QListWidgetItem(mind_icon(icon), text))
        self.stack = QStackedWidget()
        for w in (WelcomePage(), DriversPage(self.runner), DevPage(self.runner), EcosystemPage(self.runner),
                  SystemPage()):
            self.stack.addWidget(w)
        # Появление страницы при переключении: пружинистый подъём снизу (bounce-in).
        # Прозрачность не анимируем: QGraphicsOpacityEffect на стеке конфликтует с тенями карточек.
        self.anim_rise = QPropertyAnimation(self.stack, b"pos", self)
        self.anim_rise.setDuration(520)
        # Пружина как cubic-bezier(0.34, 1.56, 0.64, 1) в вебе
        spring = QEasingCurve(QEasingCurve.Type.OutBack)
        spring.setOvershoot(1.9)
        self.anim_rise.setEasingCurve(spring)
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
        if REDUCED_MOTION:
            return
        self.anim_rise.stop()
        # Позицию берём из раскладки: до первого показа окна она ещё не рассчитана
        end = self.stack.geometry().topLeft()
        if self.isVisible() and not end.isNull():
            self.anim_rise.setStartValue(end + QPoint(0, 22))
            self.anim_rise.setEndValue(end)
            self.anim_rise.start()


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
