# shellcheck shell=sh
# AIsktagOS: программная отрисовка, если нет render-узла DRM (/dev/dri/renderD*).
# Без него клиенты Qt Quick рисуют чёрные окна (VMware без 3D, старые видеокарты, fallback-режимы).
# Файл подключается startplasma через «.», поэтому только POSIX sh и без exit.
aisktagos_render=
for aisktagos_node in /dev/dri/renderD*; do
    [ -e "$aisktagos_node" ] && aisktagos_render=1
done
if [ -z "$aisktagos_render" ]; then
    export QT_QUICK_BACKEND=software
    export KWIN_COMPOSE=Q
fi
unset aisktagos_render aisktagos_node
