# shellcheck shell=sh
# AIsktagOS: в live-сессии (USB/DVD) не блокировать экран, не гасить его и не уходить в сон —
# иначе установка прерывается экраном блокировки, а у live-пользователя нет пароля.
# Файл подключается startplasma через «.», поэтому только POSIX sh и без exit.
if grep -qw 'boot=casper' /proc/cmdline 2>/dev/null && command -v kwriteconfig6 >/dev/null 2>&1; then
    kwriteconfig6 --file kscreenlockerrc --group Daemon --key Autolock false
    kwriteconfig6 --file kscreenlockerrc --group Daemon --key LockOnResume false
    for aisktagos_profile in AC Battery LowBattery; do
        kwriteconfig6 --file powerdevilrc --group "$aisktagos_profile" --group SuspendAndShutdown --key AutoSuspendAction 0
        kwriteconfig6 --file powerdevilrc --group "$aisktagos_profile" --group Display --key DimDisplayWhenIdle false
        kwriteconfig6 --file powerdevilrc --group "$aisktagos_profile" --group Display --key TurnOffDisplayWhenIdle false
    done
    unset aisktagos_profile
fi
