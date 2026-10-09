#!/bin/sh
# Обновить Джарвиса в уже установленной AIsktagOS без переустановки системы:
#   curl -fsSL https://raw.githubusercontent.com/tagiriskaliev18-hash/AisktagOS/claude/blissful-goldberg-5nsfi3/tools/jarvis-update.sh | sh
# Скачивает из последнего релиза архив jarvis-update.tar.gz, сверяет SHA-256, ставит код в
# ~/.local/share/aisktagos/jarvis, запускатель в ~/.local/bin/jarvis и переводит на него ярлык на рабочем
# столе и в меню. Дальше Джарвис обновляется сам (jarvis --update и проверка раз в 12 часов).
set -eu
REPO="${JARVIS_UPDATE_REPO:-tagiriskaliev18-hash/AisktagOS}"
API="${JARVIS_UPDATE_API:-https://api.github.com}"   # для тестов — свой сервер
DIR="${XDG_DATA_HOME:-$HOME/.local/share}/aisktagos/jarvis"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "==> Ищу обновление Джарвиса в релизах $REPO…"
curl -fsSL -H 'Accept: application/vnd.github+json' "$API/repos/$REPO/releases?per_page=15" -o "$TMP/rel.json"
python3 - "$TMP/rel.json" > "$TMP/urls" <<'PY'
import json, sys
best = None
for r in json.load(open(sys.argv[1])):
    a = {x["name"]: x["browser_download_url"] for x in r.get("assets", [])}
    if "jarvis-update.tar.gz" in a and "jarvis-update.tar.gz.sha256" in a and (best is None or r["created_at"] > best[0]):
        best = (r["created_at"], a["jarvis-update.tar.gz"], a["jarvis-update.tar.gz.sha256"], r["tag_name"])
if not best:
    sys.exit("в релизах пока нет jarvis-update.tar.gz — дождитесь новой сборки на GitHub")
print(best[1]); print(best[2]); print(best[3])
PY
url="$(sed -n 1p "$TMP/urls")"; sha_url="$(sed -n 2p "$TMP/urls")"; tag="$(sed -n 3p "$TMP/urls")"
echo "==> Скачиваю из релиза $tag"
curl -fsSL "$url" -o "$TMP/jarvis-update.tar.gz"
curl -fsSL "$sha_url" -o "$TMP/jarvis-update.tar.gz.sha256"
(cd "$TMP" && sha256sum -c --quiet jarvis-update.tar.gz.sha256) || { echo "Ошибка: архив повреждён"; exit 1; }

mkdir -p "$TMP/x" && tar -xzf "$TMP/jarvis-update.tar.gz" -C "$TMP/x" --no-same-owner
for f in "$TMP"/x/lib/*.py "$TMP/x/bin/jarvis"; do python3 -m py_compile "$f"; done
rm -rf "${DIR:?}/lib"
mkdir -p "$DIR" "$HOME/.local/bin" "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/scalable/apps"
cp -r "$TMP/x/lib" "$DIR/lib"
install -m 0755 "$TMP/x/bin/jarvis" "$HOME/.local/bin/jarvis"
cp "$TMP/x/share/aisktagos-jarvis.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/"

# Ярлыки: меню и рабочий стол запускают обновлённый Джарвис по полному пути
launcher="$HOME/.local/bin/jarvis"
sed "s|^Exec=.*|Exec=kitty --class aisktag-jarvis --title Джарвис $launcher|" "$TMP/x/share/aisktag-jarvis.desktop" \
    > "$HOME/.local/share/applications/aisktag-jarvis.desktop"
desk="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
mkdir -p "$desk"
install -m 0755 "$HOME/.local/share/applications/aisktag-jarvis.desktop" "$desk/jarvis.desktop"
command -v kbuildsycoca5 >/dev/null 2>&1 && kbuildsycoca5 >/dev/null 2>&1 || true
command -v kbuildsycoca6 >/dev/null 2>&1 && kbuildsycoca6 >/dev/null 2>&1 || true

ver="$(grep -m1 '^VERSION' "$DIR/lib/aisktag_jarvis.py" | cut -d'"' -f2)"
echo "==> Готово: Джарвис $ver. Ярлык «Джарвис» на рабочем столе теперь запускает новую версию."
