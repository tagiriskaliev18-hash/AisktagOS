#!/bin/sh
# AIsktagOS: настройки окружения для live-сессии
if grep -qw 'boot=casper' /proc/cmdline 2>/dev/null; then
    # Отключение автоматического гашения экрана и блокировки в live-режиме
    export KDE_DEBUG=1
fi
