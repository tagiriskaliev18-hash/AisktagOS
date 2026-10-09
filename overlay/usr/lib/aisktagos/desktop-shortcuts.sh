#!/bin/sh
# Ярлыки рабочего стола AIsktagOS при каждом входе: Центр, Джарвис, Firefox и др. (/etc/skel/Desktop).
# Папка рабочего стола зависит от языка («Рабочий стол» в русской сессии), поэтому берём её из xdg-user-dir,
# а не полагаемся на ~/Desktop из /etc/skel. Ярлык Firefox возвращается при каждом входе.
command -v xdg-user-dirs-update >/dev/null 2>&1 && xdg-user-dirs-update
desk="$(xdg-user-dir DESKTOP 2>/dev/null)"
[ -n "$desk" ] || desk="$HOME/Desktop"
mkdir -p "$desk"
# Один раз на пользователя кладём все ярлыки из /etc/skel/Desktop (дальше пользователь волен их удалять)
mark="${XDG_CONFIG_HOME:-$HOME/.config}/aisktagos/desktop-shortcuts-v1"
if [ ! -e "$mark" ]; then
    for f in /etc/skel/Desktop/*.desktop; do
        [ -e "$f" ] || continue
        [ -e "$desk/$(basename "$f")" ] || install -m 0755 "$f" "$desk/"
    done
    mkdir -p "$(dirname "$mark")" && touch "$mark"
fi
# Firefox — всегда: если пользователь удалил его ярлык, возвращаем
[ -e "$desk/firefox.desktop" ] || install -m 0755 /etc/skel/Desktop/firefox.desktop "$desk/" 2>/dev/null
exit 0
