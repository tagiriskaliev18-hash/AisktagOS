#!/bin/sh
# Интеграция с VirtualBox в сессии Wayland (и запасной запуск в X11).
# Пакет virtualbox-guest-x11 стартует VBoxClient только из Xsession.
# На физическом ПК устройства vboxguest нет — скрипт сразу выходит
# и не трогает разрешение, драйвер и буфер обмена.
if [ ! -e /dev/vboxguest ] && [ ! -d /sys/class/misc/vboxguest ]; then
    exit 0
fi
command -v VBoxClient >/dev/null 2>&1 || exit 0
if command -v pgrep >/dev/null 2>&1 && pgrep -x VBoxClient >/dev/null 2>&1; then
    exit 0
fi
VBoxClient --clipboard >/dev/null 2>&1 || true
# VMSVGA (контроллер по умолчанию в VirtualBox 7) слушает --vmsvga.
VBoxClient --vmsvga >/dev/null 2>&1 || VBoxClient --display >/dev/null 2>&1 || true
exit 0
