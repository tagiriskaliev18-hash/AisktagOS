#!/bin/sh
# AIsktagOS: запасной графический режим для любой видеокарты.
# Экран входа всегда работает в X11 (см. /etc/sddm.conf.d/10-aisktagos.conf).
# Сеанс Wayland требует DRM-устройство /dev/dri/card*. Его нет при nomodeset без simpledrm,
# на очень старых/экзотических видеокартах и в некоторых виртуальных машинах.
# Тогда автовход переводится на X11-сеанс Plasma (драйверы vesa/fbdev работают везде).
#
# Имена сеансов зависят от версии Plasma:
#   Plasma 5 (Ubuntu 24.04): plasma.desktop — X11, plasmawayland.desktop — Wayland;
#   Plasma 6 (Ubuntu 26.04): plasmax11.desktop — X11, plasma.desktop — Wayland.

# Видеодрайвер может загрузиться чуть позже экрана входа — ждём до 5 секунд
i=0
while [ $i -lt 10 ]; do
    if ls /dev/dri/card* >/dev/null 2>&1; then
        exit 0
    fi
    sleep 0.5
    i=$((i + 1))
done

echo "AIsktagOS: нет DRM-устройства, сеанс Plasma запускается в X11"

# X11-сеанс этой версии Plasma
x11=
for s in plasmax11.desktop plasma.desktop; do
    if [ -f "/usr/share/xsessions/$s" ]; then
        x11=$s
        break
    fi
done
[ -n "$x11" ] || exit 0

# Автовход live-сессии (casper пишет /etc/sddm.conf) и установленной системы
for f in /etc/sddm.conf /etc/sddm.conf.d/*.conf; do
    [ -f "$f" ] || continue
    grep -q '^Session=' "$f" || continue
    cur="$(sed -n 's/^Session=//p' "$f" | head -1)"
    case "$cur" in *.desktop) ;; *) cur="$cur.desktop" ;; esac
    # Сеанс уже X11 — ничего не меняем
    [ -f "/usr/share/xsessions/$cur" ] && continue
    sed -i "s/^Session=.*/Session=$x11/" "$f"
done
exit 0
