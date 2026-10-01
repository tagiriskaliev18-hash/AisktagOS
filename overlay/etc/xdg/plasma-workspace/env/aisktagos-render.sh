# shellcheck shell=sh
# AIsktagOS: программная отрисовка, если нет render-узла DRM (/dev/dri/renderD*).
# Без него клиенты Qt Quick рисуют чёрные окна (VMware без 3D, старые видеокарты, fallback-режимы).
# Файл подключается startplasma через «.», поэтому только POSIX sh и без exit,
# все переменные с префиксом aisktagos_ и удаляются в конце.
aisktagos_render=
for aisktagos_node in /dev/dri/renderD*; do
    [ -e "$aisktagos_node" ] && aisktagos_render=1
done
if [ -z "$aisktagos_render" ]; then
    export QT_QUICK_BACKEND=software
    export KWIN_COMPOSE=Q
fi

# Лёгкая графика: без render-узла и в любой виртуальной машине (VirtualBox без 3D даёт
# render-узел, но рисует процессором). Размытие и контраст фона там тормозят всю систему.
aisktagos_light=
[ -z "$aisktagos_render" ] && aisktagos_light=1
if command -v systemd-detect-virt >/dev/null 2>&1 && systemd-detect-virt --vm --quiet; then
    aisktagos_light=1
fi

# Утилита записи настроек KDE: kwriteconfig5 (Plasma 5.27) или kwriteconfig6 (Plasma 6)
aisktagos_kwc=
for aisktagos_c in kwriteconfig5 kwriteconfig6; do
    if [ -z "$aisktagos_kwc" ] && command -v "$aisktagos_c" >/dev/null 2>&1; then
        aisktagos_kwc=$aisktagos_c
    fi
done
# Метка «эффекты отключены нами»: по ней настройки возвращаются на нормальном железе
aisktagos_mark="${XDG_CONFIG_HOME:-$HOME/.config}/aisktagos-lowgfx"

if [ -n "$aisktagos_light" ]; then
    # Один раз, пока метки нет: пользователь может потом включить эффекты сам
    if [ -n "$aisktagos_kwc" ] && [ ! -e "$aisktagos_mark" ]; then
        "$aisktagos_kwc" --file kwinrc --group Plugins --key blurEnabled false
        "$aisktagos_kwc" --file kwinrc --group Plugins --key contrastEnabled false
        "$aisktagos_kwc" --file kdeglobals --group KDE --key AnimationDurationFactor 0.35
        mkdir -p "${aisktagos_mark%/*}" && : > "$aisktagos_mark"
    fi
elif [ -n "$aisktagos_kwc" ] && [ -e "$aisktagos_mark" ]; then
    # Система перенесена на настоящий ПК: убираем наши значения, снова действуют умолчания /etc/xdg
    "$aisktagos_kwc" --file kwinrc --group Plugins --key blurEnabled --delete
    "$aisktagos_kwc" --file kwinrc --group Plugins --key contrastEnabled --delete
    "$aisktagos_kwc" --file kdeglobals --group KDE --key AnimationDurationFactor --delete
    rm -f "$aisktagos_mark"
fi

unset aisktagos_render aisktagos_node aisktagos_light aisktagos_kwc aisktagos_c aisktagos_mark
