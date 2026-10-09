#!/usr/bin/env bash
# Выполняется внутри chroot: ставит пакеты и превращает Ubuntu в AIsktagOS.
set -euxo pipefail

B=/tmp/aisktagos-build
# shellcheck source=../config.env
source "$B/config.env"
export DEBIAN_FRONTEND=noninteractive
APT=(apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold)

# --- Сеть внутри chroot -------------------------------------------------------
if [ -s "$B/resolv.conf" ]; then
    rm -f /etc/resolv.conf
    cp "$B/resolv.conf" /etc/resolv.conf
fi

# Без документации в /usr/share/doc (кроме лицензий) — минус ~200 МБ; man-страницы остаются
cat > /etc/dpkg/dpkg.cfg.d/aisktagos-nodoc <<'EOF'
path-exclude=/usr/share/doc/*
path-include=/usr/share/doc/*/copyright
EOF

# Не запускать службы во время сборки
printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
chmod +x /usr/sbin/policy-rc.d

# --- Репозитории Ubuntu -------------------------------------------------------
rm -f /etc/apt/sources.list
cat > /etc/apt/sources.list.d/ubuntu.sources <<EOF
Types: deb
URIs: ${UBUNTU_MIRROR}
Suites: ${UBUNTU_SUITE} ${UBUNTU_SUITE}-updates ${UBUNTU_SUITE}-backports
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg

Types: deb
URIs: http://security.ubuntu.com/ubuntu
Suites: ${UBUNTU_SUITE}-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF

# Без snap (как в Linux Mint): приложения — из deb и Flatpak
cat > /etc/apt/preferences.d/aisktagos-nosnap.pref <<'EOF'
# AIsktagOS не использует snap. Приложения ставятся из deb-пакетов и Flatpak (Flathub).
Package: snapd
Pin: release a=*
Pin-Priority: -10
EOF

apt-get update
"${APT[@]}" dist-upgrade

# --- Локали -------------------------------------------------------------------
"${APT[@]}" install locales
sed -i -e 's/^# *\(ru_RU.UTF-8\)/\1/' -e 's/^# *\(en_US.UTF-8\)/\1/' /etc/locale.gen
locale-gen ru_RU.UTF-8 en_US.UTF-8
update-locale LANG="$DEFAULT_LOCALE"

# --- Сторонние репозитории: Firefox (Mozilla) и VS Code (Microsoft) -----------
install -d -m 0755 /etc/apt/keyrings
BROWSER_PKGS="firefox firefox-l10n-ru"
if curl -fsSL --retry 3 https://packages.mozilla.org/apt/repo-signing-key.gpg -o /etc/apt/keyrings/packages.mozilla.org.asc; then
    cat > /etc/apt/sources.list.d/mozilla.sources <<'EOF'
Types: deb
URIs: https://packages.mozilla.org/apt
Suites: mozilla
Components: main
Signed-By: /etc/apt/keyrings/packages.mozilla.org.asc
EOF
    cat > /etc/apt/preferences.d/aisktagos-mozilla.pref <<'EOF'
# Firefox из официального репозитория Mozilla, а не snap-заглушка Ubuntu
Package: *
Pin: origin packages.mozilla.org
Pin-Priority: 1000

Package: firefox*
Pin: release o=Ubuntu
Pin-Priority: -1
EOF
else
    echo "ВНИМАНИЕ: репозиторий Mozilla недоступен, вместо Firefox будет Falkon"
    BROWSER_PKGS="falkon"
fi

CODE_PKGS=""
if curl -fsSL --retry 3 https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor --yes -o /etc/apt/keyrings/microsoft.gpg; then
    cat > /etc/apt/sources.list.d/vscode.sources <<'EOF'
Types: deb
URIs: https://packages.microsoft.com/repos/code
Suites: stable
Components: main
Architectures: amd64
Signed-By: /etc/apt/keyrings/microsoft.gpg
EOF
    CODE_PKGS="code"
    # Не даём пакету code добавлять свой дубликат списка репозитория
    echo "code code/add-microsoft-repo boolean false" | debconf-set-selections
else
    echo "ВНИМАНИЕ: репозиторий Microsoft недоступен, VS Code не будет предустановлен"
fi

apt-get update

# --- Пакеты -------------------------------------------------------------------
mapfile -t PKGS < <(cat "$B"/packages/*.list | sed -e 's/#.*//' -e 's/[[:space:]]//g' | sed '/^$/d')
# shellcheck disable=SC2086
"${APT[@]}" install "${PKGS[@]}" $BROWSER_PKGS $CODE_PKGS

# Kubuntu-настройки не нужны: у AIsktagOS свои. Плюс крупные пакеты, пришедшие
# только «рекомендациями» (ставятся по желанию через Центр AIsktagOS или apt)
for p in kubuntu-settings-desktop kubuntu-notification-helper plasma-discover-backend-snap snapd \
         fonts-noto-cjk-extra ibus ibus-data $(dpkg-query -W -f='${Package}\n' 'llvm-*-dev' 'ibus-gtk*' 2>/dev/null); do
    if dpkg -s "$p" >/dev/null 2>&1; then
        "${APT[@]}" purge "$p"
    fi
done
"${APT[@]}" autoremove --purge
find /usr/share/doc -type f ! -name copyright -delete
find /usr/share/doc -type d -empty -delete

# --- Файлы AIsktagOS --------------------------------------------------------------
cp -a "$B/overlay/." /
chmod +x /usr/bin/aisktag-* /usr/bin/ai /usr/bin/jarvis /usr/lib/aisktagos/*.sh /usr/lib/aisktagos/*.py \
         /usr/lib/aisktagos/ai/* /etc/xdg/plasma-workspace/env/*.sh 2>/dev/null || true
# Версия в установщике — из config.env (иначе в 1.1 мастер писал «AIsktagOS 1.0»)
sed -i -e "s/^\(    version: *\).*/\1${OS_VERSION} ${OS_CODENAME}/" \
       -e "s/^\(    shortVersion: *\).*/\1\"${OS_VERSION}\"/" \
       -e "s/^\(    versionedName: *\).*/\1${OS_NAME} ${OS_VERSION}/" \
       -e "s/^\(    shortVersionedName: *\).*/\1${OS_NAME} ${OS_VERSION}/" \
       /etc/calamares/branding/aisktagos/branding.desc

# --- lazygit (нет в репозитории Ubuntu 24.04) --------------------------------------
install_lazygit() {
    local tgz="/tmp/lazygit.tar.gz"
    curl -fL --retry 4 --retry-delay 5 -o "$tgz"         "https://github.com/jesseduffield/lazygit/releases/download/v${LAZYGIT_VERSION}/lazygit_${LAZYGIT_VERSION}_linux_x86_64.tar.gz" || return 1
    echo "$LAZYGIT_SHA256  $tgz" | sha256sum -c - || return 1
    tar -xzf "$tgz" -C /usr/local/bin lazygit || return 1
    chmod 755 /usr/local/bin/lazygit
    rm -f "$tgz"
}
install_lazygit || echo "ВНИМАНИЕ: lazygit не установлен (нет сети?) — псевдоним lg работать не будет"

# --- ИИ Mind: движок llama.cpp и встроенная модель ---------------------------------
# Внутри `if install_ai` режим set -e не действует, поэтому каждый критичный шаг явно завершается `|| return 1`.
# Сбой загрузки не должен ломать всю сборку: тогда образ получится без ИИ-движка/модели,
# а доустановить их можно из Центра AIsktagOS («ИИ») или командой `ai model install`.
install_ai() {
    local root=/opt/aisktagos/ai/llama tmp=/tmp/aisktagos-ai variant asset sha srv
    local base="https://github.com/ggml-org/llama.cpp/releases/download/${LLAMACPP_BUILD}"
    mkdir -p "$tmp" "$root"
    for variant in cpu vulkan; do
        if [ "$variant" = cpu ]; then
            asset="llama-${LLAMACPP_BUILD}-bin-ubuntu-x64.tar.gz"; sha="$LLAMACPP_CPU_SHA256"
        else
            asset="llama-${LLAMACPP_BUILD}-bin-ubuntu-vulkan-x64.tar.gz"; sha="$LLAMACPP_VULKAN_SHA256"
        fi
        curl -fL --retry 4 --retry-delay 5 -o "$tmp/$asset" "$base/$asset" || return 1
        echo "$sha  $tmp/$asset" | sha256sum -c - || return 1
        mkdir -p "$tmp/x-$variant" "$root/$variant"
        tar -xzf "$tmp/$asset" -C "$tmp/x-$variant" || return 1
        srv="$(find "$tmp/x-$variant" -name llama-server -type f | head -1)"
        [ -n "$srv" ] || { echo "llama-server не найден в $asset"; return 1; }
        cp -a "$(dirname "$srv")/." "$root/$variant/" || return 1
        chmod -R a+rX "$root/$variant"
        chmod 755 "$root/$variant/llama-server" || return 1
        # Диагностика для журнала сборки: все ли системные библиотеки на месте
        LD_LIBRARY_PATH="$root/$variant" ldd "$root/$variant/llama-server" | grep 'not found' || echo "llama-server ($variant): зависимости найдены"
    done

    local model="${AI_BUNDLE_MODEL:-lite}"
    if [ "$model" != none ]; then
        local catalog=/usr/share/aisktagos/ai/models.json file url msha
        file="$(jq -r --arg id "$model" '.models[] | select(.id == $id) | .file' "$catalog")"
        url="$(jq -r --arg id "$model" '.models[] | select(.id == $id) | .url' "$catalog")"
        msha="$(jq -r --arg id "$model" '.models[] | select(.id == $id) | .sha256' "$catalog")"
        [ -n "$file" ] && [ "$file" != null ] || { echo "модель «$model» не найдена в каталоге"; return 1; }
        mkdir -p /usr/share/aisktagos/ai/models
        curl -fL --retry 5 --retry-delay 10 -C - -o "/usr/share/aisktagos/ai/models/$file" "$url" || return 1
        echo "$msha  /usr/share/aisktagos/ai/models/$file" | sha256sum -c - || return 1
        chmod 644 "/usr/share/aisktagos/ai/models/$file"
        sed -i "s/^AI_MODEL=.*/AI_MODEL=$model/" /etc/aisktagos/ai.conf
        echo "Встроенная модель Mind: $model ($file)"
    fi
}
if install_ai; then
    echo "ИИ Mind установлен"
else
    echo "ВНИМАНИЕ: ИИ Mind установлен не полностью (см. выше) — образ будет без встроенной модели"
fi
rm -rf /tmp/aisktagos-ai

# Значки на рабочем столе нового пользователя (как в Windows): файлы должны быть исполняемыми, иначе Plasma спросит доверие
chmod +x /etc/skel/Desktop/*.desktop 2>/dev/null || true

# Тёмная тема по умолчанию: цвета Breeze Dark + настройки AIsktagOS
{ cat /usr/share/color-schemes/BreezeDark.colors; echo; cat /usr/share/aisktagos/kdeglobals.aisktagos; } > /etc/xdg/kdeglobals

# Пакет grub-efi-amd64 для установщика: на UEFI-машинах он заменит grub-pc
mkdir -p /usr/share/aisktagos/debs
(cd /usr/share/aisktagos/debs && apt-get download grub-efi-amd64)

# Идентификация системы (как в Linux Mint: ID_LIKE=ubuntu, совместимость с PPA и драйверами)
dpkg-divert --local --rename --add /usr/lib/os-release
cat > /usr/lib/os-release <<EOF
PRETTY_NAME="${OS_NAME} ${OS_VERSION} (${OS_CODENAME})"
NAME="${OS_NAME}"
VERSION_ID="${OS_VERSION}"
VERSION="${OS_VERSION} (${OS_CODENAME})"
VERSION_CODENAME=${UBUNTU_SUITE}
ID=${OS_ID}
ID_LIKE="ubuntu debian"
HOME_URL="${OS_URL}"
SUPPORT_URL="${OS_URL}/issues"
BUG_REPORT_URL="${OS_URL}/issues"
LOGO=${OS_ID}-logo
UBUNTU_CODENAME=${UBUNTU_SUITE}
EOF
ln -sf ../usr/lib/os-release /etc/os-release
# Файлы base-files переименовываем через dpkg-divert, чтобы обновления не спрашивали о конфликте
for f in /etc/issue /etc/issue.net /etc/lsb-release; do
    dpkg-divert --local --rename --add "$f"
done
echo "${OS_NAME} ${OS_VERSION} \\n \\l" > /etc/issue
echo "${OS_NAME} ${OS_VERSION}" > /etc/issue.net
# Кодовое имя остаётся от Ubuntu — для совместимости с PPA и сторонними репозиториями
cat > /etc/lsb-release <<EOF
DISTRIB_ID=Ubuntu
DISTRIB_RELEASE=${UBUNTU_VERSION}
DISTRIB_CODENAME=${UBUNTU_SUITE}
DISTRIB_DESCRIPTION="${OS_NAME} ${OS_VERSION} (${OS_CODENAME})"
EOF
# Приветствие терминала без рекламы Ubuntu Pro/Landscape
chmod -x /etc/update-motd.d/10-help-text /etc/update-motd.d/50-motd-news \
         /etc/update-motd.d/91-contract-ua-esm-status 2>/dev/null || true

# Заставка загрузки: логотип AIsktagOS вместо логотипа Ubuntu
# (на ПК с UEFI в центре показывается логотип производителя, как у Windows)
for f in /usr/share/plymouth/themes/spinner/watermark.png /usr/share/plymouth/ubuntu-logo.png; do
    [ -e "$f" ] || continue
    dpkg-divert --local --rename --add "$f"
    cp /usr/share/aisktagos/plymouth-watermark.png "$f"
done
f=/usr/share/plymouth/themes/spinner/bgrt-fallback.png
if [ -e "$f" ]; then
    dpkg-divert --local --rename --add "$f"
    cp /usr/share/aisktagos/plymouth-logo.png "$f"
fi

# --- Пользователи по умолчанию: zsh, группы разработчика ----------------------
sed -i 's|^#\?DSHELL=.*|DSHELL=/usr/bin/zsh|' /etc/adduser.conf
sed -i 's|^#\?SHELL=.*|SHELL=/usr/bin/zsh|' /etc/default/useradd

# --- Службы -------------------------------------------------------------------
systemctl enable NetworkManager sddm aisktagos-flathub.service
# ИИ Mind: сокет слушает 127.0.0.1:6573, модель загружается только по первому запросу
systemctl enable aisktag-llm.socket
systemctl set-default graphical.target
# Сетью управляет NetworkManager. Ожидание сети перед рабочим столом на ноутбуке
# без Wi-Fi и в виртуальной машине добавляет десятки секунд и больше.
systemctl mask systemd-networkd-wait-online.service || true
systemctl disable NetworkManager-wait-online.service || true
systemctl mask NetworkManager-wait-online.service || true
# Docker запускается по первому обращению — не тормозит загрузку
systemctl disable docker.service || true
systemctl enable docker.socket || true
sed -i 's/^ENABLED=.*/ENABLED=yes/' /etc/ufw/ufw.conf

# Flathub (при сборке без сети — добавится при первом запуске службой aisktagos-flathub)
flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo || true

# --- Live-сессия (casper) -----------------------------------------------------
cat > /etc/casper.conf <<EOF
export USERNAME="${LIVE_USER}"
export USERFULLNAME="${OS_NAME} Live"
export HOST="${LIVE_HOSTNAME}"
export BUILD_SYSTEM="Ubuntu"
export FLAVOUR="${OS_NAME}"
EOF

# Шрифты, иконки, initramfs с поддержкой casper и plymouth
fc-cache -f
gtk-update-icon-cache -f /usr/share/icons/hicolor || true
update-initramfs -u -k all

# --- Очистка ------------------------------------------------------------------
apt-get clean
rm -rf /var/lib/apt/lists/* /var/cache/apt/*.bin /tmp/* /var/tmp/* /root/.cache
rm -f /usr/sbin/policy-rc.d /etc/hostname
: > /etc/machine-id
rm -f /var/lib/dbus/machine-id
find /var/log -type f -exec truncate -s 0 {} +
rm -f /etc/resolv.conf
ln -s ../run/systemd/resolve/stub-resolv.conf /etc/resolv.conf

# Кэши актуальны: иначе systemd при каждой загрузке с USB пересобирает ldconfig/hwdb/каталоги
ldconfig
systemd-hwdb update || true
journalctl --update-catalog 2>/dev/null || true
touch /etc/.updated /var/.updated
