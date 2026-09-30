# AIsktagOS

Полное описание проекта, архитектурные решения, найденные ловушки и план работ находятся в [AGENTS.md](AGENTS.md). Прочитайте его перед любыми изменениями.

- Отвечайте пользователю по-русски; комментарии в коде тоже на русском.
- Название, версия и база системы меняются только в `config.env`.
- Прежде чем что-то публиковать, соберите быстрый тестовый ISO (`SQUASHFS_COMP=zstd ZSTD_LEVEL=3`) и проверьте его в `tools/test-vm.py`.
- Перед коммитом: `shellcheck -S warning build.sh scripts/*.sh overlay/usr/lib/aisktagos/*.sh overlay/etc/xdg/plasma-workspace/env/*.sh overlay/usr/bin/aisktag-install` и `python3 -m py_compile overlay/usr/lib/aisktagos/aisktag-center.py overlay/usr/bin/aisktag-ai`.
