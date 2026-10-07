# AIsktagOS: передача проекта ИИ-агенту (Claude Code, Antigravity/Gemini и др.)

Этот файл для ИИ-ассистента, который продолжает работу над проектом. Прочитайте его целиком, прежде чем что-то менять. Пользователь общается по-русски, поэтому отвечайте и пишите комментарии в коде на русском.

## Что это

AIsktagOS — дистрибутив Linux для программистов со встроенным ИИ. История требований:

1. Версия 1.0 «Genesis»: «между macOS и Linux Mint», интерфейс как у macOS (строка меню, док, «светофор»).
2. Версия 1.1 «Hybrid» (текущая): по просьбе пользователя рабочий стол **«между Windows и Linux»**, **встроенная модель ИИ (Mind)** и полный набор для разработки, единый уникальный дизайн «Aurora».

Неизменные требования: ISO для флешки (Rufus, balenaEtcher, Ventoy) и ВМ (VMware, VirtualBox); установщик простой и пошаговый, как у Windows; любая видеокарта; надёжность как у Mint (снимки Timeshift, менеджер драйверов, никаких snap).

## Архитектурные решения (менять только с веской причиной)

| Решение | Почему |
|---|---|
| База **Ubuntu 24.04 LTS «noble»** (переход с 26.04 в коммите `e5d8989`; `config.env` — источник правды) | Драйверы всех видеокарт, стабильный LTS до 2029. README и этот файл раньше называли 26.04/Plasma 6.6 — это было устаревшим |
| **KDE Plasma 5.27 / Qt 5** | Версия Ubuntu 24.04. Никаких решений, требующих Plasma 6, Qt 6, Latte Dock, сторонних PPA, snap. PyQt6-приложения (Центр, Mind) работают отдельно от Qt 5 Plasma |
| Раскладка «Hybrid»: панель задач снизу, значки на столе, кнопки справа | Просьба пользователя; штатные средства Plasma (look-and-feel + layout.js), без сторонних виджетов |
| **Calamares** | Установщик-мастер как у Windows; конфиги взяты у Kubuntu |
| **casper** + сборка вручную debootstrap → squashfs → xorriso | Без live-build: прозрачно, полный контроль |
| **Btrfs + Timeshift**, подтома `@`, `@home`, `@cache`, `@log` | Снимок перед каждым apt (хук `80aisktagos-snapshot`) даёт откат |
| **shim + подписанный GRUB Ubuntu** | Secure Boot без отключения |
| Без snap (pin `snapd` = -10), Firefox из репозитория Mozilla, VS Code из Microsoft | Как в Mint |
| **ИИ: llama.cpp + systemd socket activation**, не Ollama | Лёгкий статический движок (MIT), закреплённая сборка с SHA-256, ноль памяти в простое, нет сторонних демонов и лишних портов |
| Модели только Apache-2.0/MIT, закреплённые SHA-256 в `models.json` | Можно свободно распространять в образе; Qwen2.5-3B под исследовательской лицензией не годится |
| Дизайн-токены в `assets/tokens.py` | Единый источник цветов для Qt-приложений и генераторов графики; контраст проверяется (WCAG AA) |

## Структура

```
config.env                  имя/версия/база/язык, закреплённые версии llama.cpp и lazygit, AI_BUNDLE_MODEL
build.sh                    all | system | iso | boot | clean
packages/*.list             пакеты по группам (10-base, 20-desktop, 30-dev, 35-ai, 40-hardware, 90-live)
scripts/chroot-setup.sh     всё, что делается внутри образа (репозитории, пакеты, lazygit, ИИ-движок и модель, overlay, os-release, службы, очистка)
iso/grub.cfg, iso/theme/    меню загрузки live-USB
overlay/                    файлы поверх Ubuntu; копируются в / внутри chroot
  etc/aisktagos/ai.conf     настройки ИИ (модель, движок, контекст, потоки)
  etc/calamares/            установщик: settings.conf, modules/*.conf, branding/aisktagos/ (stylesheet.qss, show.qml, branding.desc)
  etc/xdg/                  умолчания KDE: kwinrc (кнопки справа, 4 стола), kglobalshortcutsrc (Meta+E/A/R, Ctrl+Alt+T…), kdeglobals собирается в chroot
  etc/skel/                 zsh, kitty, starship, VS Code, git, ~/.continue (Mind), Desktop/*.desktop (значки на столе)
  etc/sysctl.d, security/limits.d, systemd/{system,user}.conf.d   настройки под разработку
  usr/bin/                  ai, aisktag-mind, aisktag-new, aisktag-doctor, aisktag-welcome/devsetup/drivers/install
  usr/lib/aisktagos/        aisktag-center.py (Центр), aisktag-mind.py (окно ИИ), aisktag_ai.py (клиент), aisktag_jarvis.py + aisktag_browser.py (агент Джарвис), aisktag_theme.py (тема Qt из токенов),
                            ai/{aisktag-llm-run, aisktag-llm-wait, aisktag-ai-model}, post-install.sh, display-fallback.sh, live-session.sh
  usr/lib/systemd/system/   aisktag-llm.socket, aisktag-llm.service (прокси), aisktag-llm-backend.service (llama-server)
  usr/share/aisktagos/      ai/models.json (каталог моделей), design/tokens.json (генерируется), zsh/aisktag-ai.zsh
  usr/share/plasma/look-and-feel/org.aisktagos.desktop/   layout.js: панель задач Hybrid
  usr/share/aurorae/themes/AIsktagOS/     тема окон (генерируется assets/make-aurorae.py)
  usr/share/plasma/desktoptheme/AIsktagOS/ стиль панелей (генерируется assets/make-plasma-theme.py)
  usr/share/polkit-1/actions/org.aisktagos.ai.policy
assets/                     tokens.py (дизайн-токены, --check), make-assets.py [icons|wallpapers|grub|slides], make-aurorae.py, make-plasma-theme.py
tools/                      test-vm.py (QEMU), vbox-vm.ps1, mock-llm.py (заглушка ИИ-сервера), shot-ui.py (снимки Qt-окон без сессии)
docs/AI.md, docs/JARVIS.md, docs/DESIGN.md  устройство ИИ, агент Джарвис и дизайн-система
.github/workflows/build-iso.yml  lint (shellcheck, py_compile, токены) + сборка ISO и публикация в Releases (части по 1,9 ГБ)
```

## Как собрать и проверить

```bash
sudo apt install debootstrap squashfs-tools xorriso grub-pc-bin grub-efi-amd64-bin mtools dosfstools qemu-system-x86 ovmf
# быстрая тестовая сборка (zstd вместо xz, без модели):
sudo AI_BUNDLE_MODEL=none SQUASHFS_COMP=zstd ZSTD_LEVEL=3 WORK_DIR=/var/tmp/aisktagos-work OUT_DIR=/var/tmp/aisktagos-out ./build.sh all
```

Проверка в QEMU: `tools/test-vm.py` (команды start/shot/click/type/sh, режимы `bios|uefi|secureboot`, `VGA=std|vmware|virtio`).

**Проверка без ВМ (работает и на Windows):** `python3 tools/mock-llm.py 16573`, затем `python3 tools/shot-ui.py center|mind out.png` (Qt offscreen), `python3 assets/tokens.py --check`, `python3 -m py_compile …`, `node --check …layout.js`.

Перед коммитом (CLAUDE.md): `shellcheck -S warning build.sh scripts/*.sh overlay/usr/lib/aisktagos/*.sh overlay/usr/lib/aisktagos/ai/aisktag-llm-* overlay/usr/bin/aisktag-install` и `python3 -m py_compile overlay/usr/lib/aisktagos/*.py`.

## Состояние проверки (честно)

**Проверено (29.09–01.10.2026, QEMU/VirtualBox, версия 1.0):** BIOS/UEFI, GRUB, live-сессия Plasma, Calamares «Стереть диск» до «Установки», zsh+starship, запасные режимы графики.

**Версия 1.1 (05.10.2026) проверена только статически и на заглушке** (на машине разработки не было Linux/QEMU): синтаксис скриптов (`bash -n`, `py_compile`, `node --check`), контраст токенов, рендер окон Центра и Mind в Qt offscreen, генерация проектов `aisktag-new`, CLI `ai` против `mock-llm.py`, SVG темы окон и панели. **Не проверено на реальной системе — первым делом проверьте:**

1. Сборка проходит целиком (особенно `install_ai`: URL llama.cpp/моделей, `ldd llama-server`, права `/opt/aisktagos/ai`).
2. `systemctl status aisktag-llm.socket`; `ai вопрос` будит модель, ответ приходит; через 15 минут служба выгружается. Особенно: поведение `systemd-socket-proxyd` при долгой загрузке (клиент ждёт в очереди сокета?), `DynamicUser` + `SupplementaryGroups=render video`, `MemoryHigh=80%`.
3. Выбор Vulkan на реальной видеокарте (`llama-server --list-devices` — формат строк `Vulkan0:` проверен только по документации).
4. Раскладка Plasma 5.27: все виджеты (`pager`, `icontasks` launchers, `showdesktop`, `digitalclock` `BelowTime`), кнопки окна справа (`ButtonsOnRight=IAX` в kwinrc и в look-and-feel/defaults), 4 стола (`[Desktops] Number=4` без `Id_N` — KWin должен создать сам), значки на столе (нужен `chmod +x`, делает chroot-setup).
5. Горячие клавиши из `kglobalshortcutsrc` (`[services][aisktag-mind.desktop]`, `Meta+E`, `Ctrl+Alt+T`) и kitty `shell_integration`, `allow_remote_control`, `Ctrl+Shift+E`.
6. Завершение установки и первая загрузка установленной системы (с версии 1.0 остаётся открытым): SDDM, Центр при первом входе, Timeshift (`/etc/timeshift/timeshift.json`), раскладка us+ru на экране входа.

## Найденные ловушки (не наступите снова)

1. `sudo -E` не работает в Ubuntu 26.04 (sudo-rs); на 24.04 работает, но `aisktag-install` передаёт переменные явно (`sudo env WAYLAND_DISPLAY=… calamares`).
2. `/usr/lib/shim/shimx64.efi.signed` — ссылка на `/etc/alternatives`, с хоста битая. Брать `shimx64.efi.signed.latest`.
3. Метка FAT для ESP — не длиннее 11 символов.
4. Без `/dev/dri/renderD*` клиенты Qt Quick рисуют чёрные окна. Решение: `QT_QUICK_BACKEND=software`, `KWIN_COMPOSE=Q` в `plasma-workspace/env`.
5. Эмуляция `-vga vmware` в QEMU неполная; для тестов в QEMU используйте `VGA=std`.
6. VS Code в новых версиях — `com.microsoft.VSCode.desktop`, иконка `vscode`. Панель выбирает приложения через `applicationExists()`.
7. Без `touch /etc/.updated /var/.updated` live-система при каждой загрузке запускает долгий `ldconfig.service`.
8. У Kubuntu squashfs слоёный, у нас один слой: casper/calamares удаляет модуль `packages`, остатки live — `post-install.sh`.
9. Calamares на Ubuntu ставит GRUB в `EFI/ubuntu` (подписанный GRUB), поэтому `efiBootloaderId: "ubuntu"`.
10. В песочнице без доступа к packages.mozilla.org вместо Firefox ставится Falkon.
11. **Пакеты Ubuntu 24.04:** `lazygit` и `tokei` в noble нет (lazygit ставится из GitHub-релиза в chroot-setup). Любой отсутствующий пакет в `packages/*.list` валит всю сборку: проверяйте через Launchpad API (`getPublishedBinaries`, `distro_arch_series=…/noble/amd64`) до коммита.
12. **llama.cpp:** релизы ggml-org публикуются почти ежедневно под тегами `bNNNNN`; последний «release» без бинарников (`v0.5.0` с `nightly-tag.txt`) — не путать. Сборка закреплена в `config.env` вместе с SHA-256 (digest берётся из GitHub API `assets[].digest`). Флаги `llama-server` сверены с `tools/server/README.md` тега `b11408`; при смене сборки перепроверьте (`--cache-ram`, `--alias`, `-c`, `-t`, `--list-devices`).
13. **Windows при разработке:** в репозитории `.gitattributes` задаёт LF. Python на Windows пишет CRLF, если не указать `newline=''`. Скрипты, работающие с `\` и `\n` в heredoc, лучше править инструментом правки файлов, а не `python - <<EOF`.
14. Размер ISO с моделью lite ≈ 3,5–4 ГБ: workflow режет на части по 1,9 ГБ. Для быстрой сборки `AI_BUNDLE_MODEL=none`.
15. Модель — в `/usr/share/aisktagos/ai/models`, скачанные — в `/var/lib/aisktagos/ai/models`. Служба работает как `DynamicUser`, поэтому оба каталога должны быть читаемы всем (`chmod 644`/`755`).
16. **Шрифты GRUB:** `grub-mkfont -n` задаёт только семейство, GRUB сам дописывает стиль и размер. С `-n "Inter Regular 20"` шрифт назывался «Inter Regular 20 Regular 20», тема его не находила и меню рисовалось огромным Inter Bold 44. Правильно: `-n Inter` (+ `-b` для жирного). При Secure Boot подписанный GRUB вообще не грузит свои шрифты (`prohibited by secure boot policy`) и берёт unicode.pf2 — это нормально.
17. **Rufus:** образ проверен как «ISO-режим» (файлы на FAT32, UEFI) и как DD-образ (BIOS и UEFI) — всё грузится до установщика. В ISO-режиме для BIOS Rufus ставит свой GRUB и может попросить скачать файлы под нашу версию; при сомнениях — режим «DD-образ». Самая частая «ошибка Rufus» — недокачанная часть ISO, поэтому `join-windows.bat` сверяет SHA-256.
18. **Джарвис и Firefox:** управление через WebDriver BiDi (`--remote-debugging-port`), CDP в Firefox удалён. В песочнице Firefox из образа запускается так: распаковать `usr/lib/firefox` из squashfs (`unsquashfs -o <смещение ISO>`), `JARVIS_FIREFOX=…/firefox JARVIS_HEADLESS=1 python3 tools/test-jarvis.py`. Не используйте `pkill -f` с шаблоном из своей же команды — убьёт оболочку.
19. **Папка рабочего стола** в русской сессии — «Рабочий стол», а не `~/Desktop` из `/etc/skel`: ярлыки раскладывает `desktop-shortcuts.sh` через `xdg-user-dir DESKTOP`.
20. **Джарвис на малой памяти:** при MemAvailable < 3 ГБ `aisktag-llm-run` даёт модели контекст 2048, а промпт Джарвиса с 22 инструментами — ~2200 токенов (ошибка 400 `exceed_context_size_error`, найдено в ВМ на 3 ГБ). Агент спрашивает `/props` и при n_ctx < 4096 берёт короткий промпт и 13 инструментов (~1000–1250 токенов), режет вывод инструментов под бюджет.
21. **Qwen2.5-Coder 1.5B и инструменты:** вызов приходит не в `tool_calls`, а текстом (блок ```json, иногда план из нескольких вызовов); модель повторяет один вызов и «додумывает» результат. Разбор текста, защита от повторов и предупреждение в диалоге — в `aisktag_jarvis.py`; для настоящей работы агента нужна standard/pro или облачная модель.

## Что делать дальше (приоритеты)

1. Выполнить проверки из раздела «Состояние проверки», исправить найденное. Начать со сборки на GitHub Actions и проверки ISO в VirtualBox/VMware.
2. Живая индикация ИИ на панели (виджет Plasma с состоянием модели) и Dev HUD (загрузка CPU/RAM/температуры): нужен свой QML-плазмоид, в 5.27 `org.kde.ksysguard.sensors`.
3. Своя тема SDDM и заставка загрузки в стиле Aurora (сейчас Breeze); светлая тема как вторая схема.
4. Уникальные обои «Aurora» (процедурные ленты) и пересмотр меню GRUB: отдельные пункты «Попробовать» и «Установить».
5. Контекстное меню Dolphin «Спросить Mind о файле», KRunner-плагин для `ai:`-запросов.
6. Джарвис: окно с чатом (сейчас — терминал kitty), управление мышью и клавиатурой в окнах рабочего стола (ydotool + uinput), проверка на реальной модели с вызовом инструментов (standard/pro).
