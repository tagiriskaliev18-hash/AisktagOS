# AIsktagOS: передача проекта ИИ-агенту (Claude Code, Antigravity/Gemini и др.)

Этот файл для ИИ-ассистента, который продолжает работу над проектом на другом компьютере. Прочитайте его целиком, прежде чем что-то менять. Пользователь общается по-русски, поэтому отвечайте и пишите комментарии в коде на русском.

## Что это

AIsktagOS — дистрибутив Linux для программистов. Пользователь хотел систему «между macOS и Linux Mint», похожую по ощущениям на Хакинтош, но работающую на любом ПК и с любой видеокартой. Главные требования:

- ISO-образ можно записать на флешку (Rufus, balenaEtcher, Ventoy) или запустить в **VMware**;
- **установщик простой и пошаговый, как у Windows**;
- интерфейс как у macOS: строка меню сверху, док снизу, кнопки-«светофор», Spotlight, Mission Control;
- удобство и надёжность как у Mint: снимки Timeshift, менеджер драйверов, центр приветствия, никаких snap;
- для разработчика всё готово из коробки.

## Архитектурные решения (менять только с веской причиной)

| Решение | Почему |
|---|---|
| База **Ubuntu 26.04 LTS «resolute»**, а не своё ядро | Драйверы всех видеокарт (amdgpu, i915/xe, nouveau/NVK, NVIDIA 580, vmwgfx) — только так реально «любая видеокарта». Mint тоже на Ubuntu LTS |
| **KDE Plasma 6.6** | Единственный DE, где можно собрать строку меню с глобальным меню и плавающий док штатными средствами (look-and-feel + layout.js) |
| **Calamares** | Установщик-мастер как у Windows, его же использует Kubuntu 26.04, конфиги которого взяты за основу |
| **casper** (live-система Ubuntu) + сборка вручную debootstrap → squashfs → xorriso | Без live-build: проще, прозрачнее, полный контроль |
| **Btrfs + Timeshift**, подтома `@`, `@home`, `@cache`, `@log` | Снимок перед каждым apt (хук `80aisktagos-snapshot`) даёт откат обновлений |
| **shim + подписанный GRUB Ubuntu** | Secure Boot работает без отключения |
| Без snap (pin `snapd` = -10), Firefox из репозитория Mozilla, VS Code из репозитория Microsoft | Как в Mint |

## Структура

```
config.env                  имя/версия/база/язык — единственное место для смены названия
build.sh                    all | system | iso | boot | clean
packages/*.list             пакеты по группам (10-base, 20-desktop, 30-dev, 40-hardware, 90-live)
scripts/chroot-setup.sh     всё, что делается внутри образа (репозитории, пакеты, overlay, os-release, службы, очистка)
iso/grub.cfg, iso/theme/    меню загрузки live-USB (пункт «Установить» ставит параметр aisktagos.install)
overlay/                    файлы поверх Ubuntu; копируются в / внутри chroot
  etc/calamares/            установщик: settings.conf, modules/*.conf, branding/aisktagos/
  etc/xdg/                  умолчания KDE (kdeglobals собирается в chroot из BreezeDark.colors + usr/share/aisktagos/kdeglobals.aisktagos)
  etc/xdg/plasma-workspace/env/  aisktagos-render.sh (программная отрисовка без renderD*), aisktagos-live.sh (live: без блокировки/сна)
  usr/share/plasma/look-and-feel/org.aisktagos.desktop/  раскладка: строка меню + док (layout.js)
  usr/share/aurorae/themes/AIsktagOS/  тема окон со «светофором» (генерируется assets/make-aurorae.py)
  usr/lib/aisktagos/        aisktag-center.py (PyQt6: приветствие, драйверы, dev-инструменты), post-install.sh,
                            display-fallback.sh (SDDM→X11 без DRM), live-session.sh, pre-apt-snapshot.sh
  usr/bin/aisktag-*         запуск центра и установщика
assets/                     генераторы графики (Pillow + rsvg-convert + шрифт Inter)
tools/test-vm.py            стенд QEMU: «железо» VMware, снимки экрана, клики, консоль ttyS0
.github/workflows/build-iso.yml  сборка ISO (xz) и публикация в Releases (части по 1,9 ГБ, если больше 2 ГБ)
```

## Как собрать и проверить

```bash
sudo apt install debootstrap squashfs-tools xorriso grub-pc-bin grub-efi-amd64-bin mtools dosfstools qemu-system-x86 ovmf
# быстрая тестовая сборка (zstd вместо xz, ~10 мин сжатия вместо ~80):
sudo SQUASHFS_COMP=zstd ZSTD_LEVEL=3 WORK_DIR=/var/tmp/aisktagos-work OUT_DIR=/var/tmp/aisktagos-out ./build.sh all
# только загрузчик и ISO, без пересжатия:
sudo WORK_DIR=... OUT_DIR=... ./build.sh boot
```

Проверка в QEMU (`tools/test-vm.py`):

```bash
qemu-img create -f qcow2 /var/tmp/aisktagos-vm/disk.qcow2 40G
VGA=std python3 tools/test-vm.py start t1 uefi out/aisktagos-1.0-amd64.iso /var/tmp/aisktagos-vm/disk.qcow2
python3 tools/test-vm.py shot t1 /tmp/s.png          # снимок экрана
python3 tools/test-vm.py click t1 1000 734           # клик (экран 1280x800)
python3 tools/test-vm.py type t1 Hello
# с консолью: прямая загрузка ядра, вывод в /var/tmp/aisktagos-vm/<имя>.serial, ввод командой sh
APPEND="boot=casper console=ttyS0,115200" VGA=std python3 tools/test-vm.py start dbg bios out/...iso
python3 tools/test-vm.py sh dbg aisktag              # вход live-пользователем (без пароля)
```

Режимы: `bios`, `uefi`, `secureboot`. Переменная `VGA`: `std` (bochs), `vmware`, `virtio`.

## Проверено (29.09.2026, QEMU без KVM)

- BIOS и UEFI: меню GRUB с темой (1920×1080 в UEFI) через shim и подписанный GRUB;
- live-сессия: Plasma на Wayland, строка меню, док, обои, значок «Установить AIsktagOS»;
- пункт «Установить» сам открывает Calamares; шаги «Добро пожаловать», «Местоположение», «Клавиатура», «Разделы» («Стереть диск» → EFI 512 МБ + Btrfs), «Пользователи», «Сводка», «Установка» пройдены;
- zsh + starship у пользователя, os-release/lsb-release/issue с названием AIsktagOS;
- запасные режимы графики: X11 без DRM, программная отрисовка без render-узла.

**Не проверено до конца:** завершение установки и первая загрузка установленной системы (под TCG распаковка шла ~1 час). Первым делом проверьте это в VMware или QEMU/KVM: вход в SDDM, Центр AIsktagOS при первом входе, Timeshift (`/etc/timeshift/timeshift.json`), раскладку us+ru на экране входа (установщик мог выставить только ru).

## Найденные и исправленные ловушки (не наступите снова)

1. `sudo -E` не работает: в 26.04 **sudo-rs** игнорирует `-E`. Переменные окружения нужно передавать явно (`sudo env WAYLAND_DISPLAY=… calamares`), см. `usr/bin/aisktag-install`.
2. `/usr/lib/shim/shimx64.efi.signed` — ссылка на `/etc/alternatives`, с хоста битая. Брать `shimx64.efi.signed.latest`.
3. Метка FAT для ESP — не длиннее 11 символов.
4. Без `/dev/dri/renderD*` клиенты Qt Quick рисуют чёрные окна. Решение: `QT_QUICK_BACKEND=software`, `KWIN_COMPOSE=Q` в `plasma-workspace/env`.
5. Эмуляция `-vga vmware` в QEMU неполная: vmwgfx отказывается и гасит sysfb. В настоящем VMware всё работает; для тестов в QEMU используйте `VGA=std`.
6. VS Code в новых версиях — `com.microsoft.VSCode.desktop`, иконка `vscode`. Док выбирает приложения через `applicationExists()`.
7. Без `touch /etc/.updated /var/.updated` live-система при каждой загрузке запускает долгий `ldconfig.service`.
8. У Kubuntu squashfs слоёный, у нас один слой: casper/calamares удаляет модуль `packages`, остатки live — `post-install.sh`.
9. `Calamares` на Ubuntu ставит GRUB в `EFI/ubuntu` (так требует подписанный GRUB), поэтому `efiBootloaderId: "ubuntu"`.
10. **`/dev/pts` в среде установки обязателен**: без него apt падает с «Can not write log (Is /dev/pts mounted?)». В `mount.conf` есть bind `/dev/pts`, а apt в своих командах запускается с `-o Dpkg::Use-Pty=0`.
11. В песочнице без доступа к packages.mozilla.org вместо Firefox ставится Falkon. На GitHub Actions Firefox ставится нормально.

## Что делать дальше (приоритеты)

1. Довести до конца тест установки и первой загрузки (см. выше). Проверить `contextualprocess_efi_grub` (замена grub-pc на grub-efi-amd64 на UEFI) и `post-install.sh`.
2. Опубликовать репозиторий на GitHub и запустить workflow. Размер ISO с xz ≈ 2,6–3 ГБ, поэтому будет разрезан на части по 1,9 ГБ (+ `join-windows.bat`). Если нужен один файл до 2 ГБ, уберите из образа `docker.io`, `clang`, `fonts-noto-cjk` или VS Code (его можно ставить из Центра).
3. Слайд-шоу установщика: проверить, что слайды листаются (Timer в `show.qml`).
4. Возможные улучшения: своя тема SDDM в стиле macOS, логотип-символ для строки меню, Latte-подобное увеличение значков в доке, интеграция с мультимодельной сетью пользователя (multillm-bridge) в Центре AIsktagOS.
