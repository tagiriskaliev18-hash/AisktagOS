#!/usr/bin/env bash
# Метапакет grub-efi-amd64 внутри уже распакованной системы (только UEFI).
# Модули x86_64-efi, shim и подписанный GRUB ставятся в образ заранее
# (packages/10-base.list) и работают без сети. Метапакет нужен apt, чтобы
# обновление загрузчика не задавало вопросов. На BIOS скрипт не вызывается.
set -u

log() { echo "[aisktagos-efi-grub] $*"; }

export DEBIAN_FRONTEND=noninteractive

shopt -s nullglob
debs=(/usr/share/aisktagos/debs/grub-efi-amd64_*.deb)
shopt -u nullglob

if [ "${#debs[@]}" -eq 0 ]; then
    log "локальный deb не найден, остаются модули из образа"
elif ! apt-get install -y --no-download --no-install-recommends "${debs[0]}"; then
    log "apt не поставил ${debs[0]}"
fi

if [ ! -d /usr/lib/grub/x86_64-efi ]; then
    log "нет модулей /usr/lib/grub/x86_64-efi — UEFI-установка не загрузится"
    exit 1
fi
if ! command -v grub-install >/dev/null 2>&1; then
    log "нет grub-install"
    exit 1
fi
log "загрузчик EFI готов"
exit 0
