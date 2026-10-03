#!/usr/bin/env bash
# Проверка лаунчера установщика без Calamares и без прав root.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
launcher="${root}/overlay/usr/bin/aisktag-install"
bash -n "${launcher}"

if grep -vE '^[[:space:]]*#' "${launcher}" | grep -E 'chmod[[:space:]]+0*777|xhost'; then
    echo "в лаунчере остался chmod 0777 или xhost" >&2
    exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT

export AISKTAG_SUDO_LOG="${tmp}/sudo.log"
cat > "${tmp}/sudo" << 'EOF'
#!/bin/sh
printf '%s\n' "$*" >> "$AISKTAG_SUDO_LOG"
# В тесте нет настоящего root: смену владельца только записываем.
if [ "$1" = chown ]; then
    exit 0
fi
exec "$@"
EOF
chmod 0755 "${tmp}/sudo"

python3 - "${tmp}/run/wayland-0" << 'PY'
import os
import socket
import sys
path = sys.argv[1]
os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.bind(path)
os.chmod(path, 0o700)
sock.close()
PY

auth="${tmp}/xauthority"
printf 'cookie' > "${auth}"
chmod 0600 "${auth}"
sock_mode_before="$(stat -c %a "${tmp}/run/wayland-0")"

run_launcher() {
    # Сессия только из аргументов: окружение агента не должно протечь в проверку.
    env -u QT_QUICK_BACKEND -u KWIN_COMPOSE \
        -u WAYLAND_DISPLAY -u DISPLAY -u XAUTHORITY -u XDG_RUNTIME_DIR \
        -u XDG_SESSION_TYPE \
        PATH="${tmp}:${PATH}" \
        HOME="${tmp}/home" \
        AISKTAG_INSTALL_DRY_RUN=1 \
        "$@" \
        bash "${launcher}"
}
mkdir -p "${tmp}/home"

out="$(run_launcher \
    XDG_RUNTIME_DIR="${tmp}/run" \
    WAYLAND_DISPLAY=wayland-0 \
    DISPLAY=:1 \
    XAUTHORITY="${auth}" \
    XDG_CURRENT_DESKTOP=KDE \
    LANG=ru_RU.UTF-8)"
printf '%s\n' "${out}"

grep -qxF 'QT_QPA_PLATFORM=wayland;xcb' <<< "${out}"
grep -qxF 'DISPLAY=:1' <<< "${out}"
grep -qxF "WAYLAND_LINK=${tmp}/run/wayland-0" <<< "${out}"
grep -qxF 'RUNTIME_MODE=700' <<< "${out}"
grep -qxF 'XAUTH_MODE=600' <<< "${out}"
grep -F 'XAUTHORITY=/tmp/aisktagos-calamares-runtime.' <<< "${out}" >/dev/null
grep -q 'chown root:root' "${AISKTAG_SUDO_LOG}"
if grep -E '0777|xhost' "${AISKTAG_SUDO_LOG}"; then
    echo "sudo-журнал содержит chmod 0777 или xhost" >&2
    exit 1
fi
sock_mode_after="$(stat -c %a "${tmp}/run/wayland-0")"
[ "${sock_mode_before}" = "${sock_mode_after}" ]

: > "${AISKTAG_SUDO_LOG}"
out_x11="$(run_launcher DISPLAY=:0 XAUTHORITY="${auth}")"
grep -qxF 'QT_QPA_PLATFORM=xcb' <<< "${out_x11}"
grep -qxF 'XDG_SESSION_TYPE=x11' <<< "${out_x11}"
grep -qxF 'XAUTH_MODE=600' <<< "${out_x11}"
if grep -q '^WAYLAND_DISPLAY=' <<< "${out_x11}"; then
    echo "в сессии X11 не должно быть WAYLAND_DISPLAY" >&2
    exit 1
fi

set +e
run_launcher >/dev/null
rc=$?
set -e
[ "${rc}" -eq 1 ]

echo "лаунчер установщика: проверки пройдены"
