#!/usr/bin/env bash
# Копирует MindKit (общие службы экосистемы MindTagSystem) в overlay образа.
# Источник правды — репозиторий MindTagSystem; здесь лежит его копия, чтобы
# сборка ISO не зависела от сети.
#   tools/sync-mindkit.sh [путь к MindTagSystem]   (по умолчанию ../mindtagsystem или клон с GitHub)
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:-}"
TMP=""
if [ -z "$SRC" ]; then
    for cand in "$ROOT_DIR/../mindtagsystem" "$ROOT_DIR/../MindTagSystem"; do
        [ -d "$cand/mindkit" ] && SRC="$cand" && break
    done
fi
if [ -z "$SRC" ]; then
    TMP="$(mktemp -d)"
    git clone --depth 1 https://github.com/tagiriskaliev18-hash/MindTagSystem.git "$TMP/mts"
    SRC="$TMP/mts"
fi
DEST="$ROOT_DIR/overlay/usr/lib/python3/dist-packages/mindkit"
rm -rf "$DEST"
mkdir -p "$DEST"
cp -a "$SRC/mindkit/." "$DEST/"
find "$DEST" -name '__pycache__' -prune -exec rm -rf {} +
echo "MindKit $(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$DEST/__init__.py") ← $SRC ($(git -C "$SRC" rev-parse --short HEAD 2>/dev/null || echo '?'))"
[ -n "$TMP" ] && rm -rf "$TMP"
exit 0
