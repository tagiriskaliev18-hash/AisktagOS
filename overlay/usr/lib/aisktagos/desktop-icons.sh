#!/usr/bin/env bash
# Ярлыки на рабочем столе при каждом входе: Firefox и ИИ-ассистент.
# Если ярлык удалили или программа обновилась — он появится снова в актуальном виде.
xdg-user-dirs-update 2>/dev/null || true          # «Рабочий стол» должен существовать до нас
desk="$(xdg-user-dir DESKTOP 2>/dev/null)"
[ -n "$desk" ] && [ "$desk" != "$HOME" ] || desk="$HOME/Desktop"
mkdir -p "$desk"

# Первый установленный вариант из списка (как в доке)
place() {
    local f
    for f in "$@"; do
        if [ -f "/usr/share/applications/$f" ]; then
            # Исполняемый .desktop Plasma запускает без вопроса «доверять ли файлу»
            install -m 0755 "/usr/share/applications/$f" "$desk/$f"
            return 0
        fi
    done
}

place firefox.desktop org.mozilla.firefox.desktop org.kde.falkon.desktop
place aisktag-ai.desktop
