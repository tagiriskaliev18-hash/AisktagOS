#!/usr/bin/env bash
# Архив обновления Джарвиса для релиза: jarvis --update и tools/jarvis-update.sh ставят его
# в ~/.local/share/aisktagos/jarvis без переустановки ОС.
#   tools/release/make-jarvis-update.sh <папка вывода>
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
out="${1:?папка вывода}"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/lib" "$tmp/bin" "$tmp/share" "$out"
o="$root/overlay"
cp "$o"/usr/lib/aisktagos/{aisktag_jarvis.py,aisktag_jarvis_cli.py,aisktag_browser.py,aisktag_ai.py} "$tmp/lib/"
cp "$o/usr/bin/jarvis" "$tmp/bin/"
cp "$o/usr/share/applications/aisktag-jarvis.desktop" "$o/usr/share/icons/hicolor/scalable/apps/aisktagos-jarvis.svg" "$tmp/share/"
for f in "$tmp"/lib/*.py "$tmp/bin/jarvis"; do python3 -m py_compile "$f"; done
find "$tmp" -name __pycache__ -prune -exec rm -rf {} +
tar --owner=0 --group=0 --sort=name -C "$tmp" -czf "$out/jarvis-update.tar.gz" lib bin share
(cd "$out" && sha256sum jarvis-update.tar.gz > jarvis-update.tar.gz.sha256)
echo "Готово: $out/jarvis-update.tar.gz (Джарвис $(grep -m1 '^VERSION' "$tmp/lib/aisktag_jarvis.py" | cut -d'"' -f2))"
