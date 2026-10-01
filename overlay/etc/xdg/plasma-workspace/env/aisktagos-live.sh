# shellcheck shell=sh
# AIsktagOS: в live-сессии (USB/DVD) не блокировать экран, не гасить его и не уходить в сон —
# иначе установка прерывается экраном блокировки, а у live-пользователя нет пароля.
# Файл подключается startplasma через «.», поэтому только POSIX sh и без exit.
# kwriteconfig6 — Plasma 6 (Ubuntu 26.04), kwriteconfig5 — Plasma 5 (Ubuntu 24.04).
aisktagos_kwc=
for aisktagos_c in kwriteconfig6 kwriteconfig5; do
    if [ -z "$aisktagos_kwc" ] && command -v "$aisktagos_c" >/dev/null 2>&1; then
        aisktagos_kwc=$aisktagos_c
    fi
done
if grep -qw 'boot=casper' /proc/cmdline 2>/dev/null && [ -n "$aisktagos_kwc" ]; then
    "$aisktagos_kwc" --file kscreenlockerrc --group Daemon --key Autolock false
    "$aisktagos_kwc" --file kscreenlockerrc --group Daemon --key LockOnResume false
    for aisktagos_profile in AC Battery LowBattery; do
        # Plasma 6
        "$aisktagos_kwc" --file powerdevilrc --group "$aisktagos_profile" --group SuspendAndShutdown --key AutoSuspendAction 0
        "$aisktagos_kwc" --file powerdevilrc --group "$aisktagos_profile" --group Display --key DimDisplayWhenIdle false
        "$aisktagos_kwc" --file powerdevilrc --group "$aisktagos_profile" --group Display --key TurnOffDisplayWhenIdle false
        # Plasma 5: отключить затемнение, гашение экрана (DPMS) и сон
        "$aisktagos_kwc" --file powermanagementprofilesrc --group "$aisktagos_profile" --group DimDisplay --key idleTime 0
        "$aisktagos_kwc" --file powermanagementprofilesrc --group "$aisktagos_profile" --group DPMSControl --key idleTime 0
        "$aisktagos_kwc" --file powermanagementprofilesrc --group "$aisktagos_profile" --group SuspendSession --key suspendType 0
    done
    unset aisktagos_profile
fi
unset aisktagos_kwc aisktagos_c
