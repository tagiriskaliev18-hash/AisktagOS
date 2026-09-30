#!/bin/sh
# AIsktagOS: программная отрисовка при отсутствии аппаратного узла renderD*
# Защищает от чёрных окон Qt Quick в виртуальных машинах и при nomodeset
if ! ls /dev/dri/renderD* >/dev/null 2>&1; then
    export QT_QUICK_BACKEND=software
    export KWIN_COMPOSE=Q
fi
