#!/usr/bin/env bash
# AIsktagOS: финальная настройка после установки. Запускается установщиком внутри новой системы.
set -u
export DEBIAN_FRONTEND=noninteractive

log() { echo "[aisktagos-post] $*"; }

# 1. Убрать остатки live-системы
apt-get -y autoremove --purge || true
rm -f /etc/casper.conf /etc/xdg/autostart/aisktagos-live.desktop /usr/share/applications/aisktagos-install.desktop

# 2. Корневая ФС из fstab (внутри установщика findmnt видит не ту систему)
read -r root_spec root_type < <(awk '$1 !~ /^#/ && $2 == "/" { print $1, $3; exit }' /etc/fstab)
root_uuid="${root_spec#UUID=}"
log "корень: $root_spec ($root_type)"

# 3. Timeshift: ежедневные снимки Btrfs (откат системы как в Linux Mint)
if [ "$root_type" = "btrfs" ] && [ -n "$root_uuid" ]; then
    mkdir -p /etc/timeshift
    cat > /etc/timeshift/timeshift.json <<EOF
{
  "backup_device_uuid" : "$root_uuid",
  "parent_device_uuid" : "",
  "do_first_run" : "false",
  "btrfs_mode" : "true",
  "include_btrfs_home_for_backup" : "false",
  "include_btrfs_home_for_restore" : "false",
  "stop_cron_emails" : "true",
  "schedule_monthly" : "false",
  "schedule_weekly" : "true",
  "schedule_daily" : "true",
  "schedule_hourly" : "false",
  "schedule_boot" : "false",
  "count_monthly" : "2",
  "count_weekly" : "3",
  "count_daily" : "7",
  "count_hourly" : "6",
  "count_boot" : "5",
  "date_format" : "%Y-%m-%d %H:%M:%S",
  "exclude" : [],
  "exclude-apps" : []
}
EOF
    log "Timeshift настроен"
fi

# 4. BIOS: запомнить диск для обновлений GRUB (иначе apt спросит при обновлении grub-pc)
if [ ! -d /sys/firmware/efi ] && dpkg -s grub-pc >/dev/null 2>&1; then
    part="$(blkid -U "$root_uuid" 2>/dev/null || true)"
    disk="$(lsblk -no pkname "$part" 2>/dev/null | head -1)"
    if [ -n "$disk" ]; then
        byid="$(find /dev/disk/by-id -lname "*/$disk" 2>/dev/null | grep -v -e '-part' -e 'wwn-' | head -1)"
        echo "grub-pc grub-pc/install_devices multiselect ${byid:-/dev/$disk}" | debconf-set-selections
        log "grub-pc: ${byid:-/dev/$disk}"
    fi
fi

# 5. Приветствие при первом входе нового пользователя
for home in /home/*; do
    [ -d "$home" ] || continue
    rm -f "$home/.config/aisktagos/welcome-done"
done

# 6. Запасной путь EFI/BOOT/BOOTX64.EFI.
# Часть прошивок не читает загрузочную запись NVRAM и грузит только этот файл
# (дешёвые платы, некоторые ноутбуки, виртуальные машины). Подписанный shim — первым.
src=/boot/efi/EFI/ubuntu
dst=/boot/efi/EFI/BOOT
if [ -d "$src" ]; then
    mkdir -p "$dst"
    if [ -f "$src/shimx64.efi" ]; then
        cp -f "$src/shimx64.efi" "$dst/BOOTX64.EFI"
    elif [ -f "$src/grubx64.efi" ]; then
        cp -f "$src/grubx64.efi" "$dst/BOOTX64.EFI"
    else
        log "EFI: в $src нет shimx64.efi и grubx64.efi"
    fi
    [ -f "$src/grubx64.efi" ] && cp -f "$src/grubx64.efi" "$dst/grubx64.efi"
    [ -f "$src/grub.cfg" ] && cp -f "$src/grub.cfg" "$dst/grub.cfg"
    [ -f "$src/mmx64.efi" ] && cp -f "$src/mmx64.efi" "$dst/mmx64.efi"
    log "EFI fallback: $dst"
fi

# 7. Экран входа читает /etc/default/keyboard. Установщик записывает одну раскладку,
# из-за этого SDDM остаётся только с ru или только с us. Пара us+ru и Alt+Shift —
# как в live-сессии; чужую выбранную раскладку не выбрасываем, а добавляем us.
kb=/etc/default/keyboard
if [ -f "$kb" ]; then
    kb_get() {
        _val="$(grep "^${1}=" "$kb" | head -1 | cut -d= -f2-)"
        _val="${_val#\"}"
        _val="${_val%\"}"
        printf '%s' "$_val"
    }
    kb_set() {
        if grep -q "^${1}=" "$kb"; then
            sed -i "s|^${1}=.*|${1}=\"${2}\"|" "$kb"
        else
            printf '%s="%s"\n' "$1" "$2" >> "$kb"
        fi
    }
    layout="$(kb_get XKBLAYOUT)"
    variant="$(kb_get XKBVARIANT)"
    options="$(kb_get XKBOPTIONS)"
    layout="${layout:-us}"
    case "$layout" in
        *,*) ;;
        ru)
            layout="us,ru"
            case "$variant" in
                *,*) ;;
                "") variant="," ;;
                *) variant=",${variant}" ;;
            esac
            ;;
        us)
            layout="us,ru"
            case "$variant" in
                *,*) ;;
                "") variant="," ;;
                *) variant="${variant}," ;;
            esac
            ;;
        *)
            layout="${layout},us"
            case "$variant" in
                *,*) ;;
                "") variant="," ;;
                *) variant="${variant}," ;;
            esac
            ;;
    esac
    case ",${options}," in
        *,grp:alt_shift_toggle,*) ;;
        *)
            if [ -n "$options" ]; then
                options="${options},grp:alt_shift_toggle"
            else
                options="grp:alt_shift_toggle"
            fi
            ;;
    esac
    kb_set XKBLAYOUT "$layout"
    kb_set XKBVARIANT "$variant"
    kb_set XKBOPTIONS "$options"
    xorg=/etc/X11/xorg.conf.d/00-keyboard.conf
    if [ -f "$xorg" ]; then
        sed -i \
            -e "s|Option \"XkbLayout\" \".*\"|Option \"XkbLayout\" \"${layout}\"|" \
            -e "s|Option \"XkbVariant\" \".*\"|Option \"XkbVariant\" \"${variant}\"|" \
            -e "s|Option \"XkbOptions\" \".*\"|Option \"XkbOptions\" \"${options}\"|" \
            "$xorg"
    fi
    log "клавиатура: ${layout} (${options})"
fi

exit 0
