# Встроенный ИИ AIsktagOS — Mind

Mind — локальная языковая модель, встроенная в систему. Она работает на вашем компьютере: без интернета, без аккаунтов, без телеметрии.

## Как это устроено

```
 ai / окно Mind / VS Code (Continue) / aider …
                │  OpenAI-совместимый API
                ▼
 aisktag-llm.socket   127.0.0.1:6573   ← слушает всегда, памяти почти не занимает
                │  первый запрос будит службы
                ▼
 aisktag-llm.service  systemd-socket-proxyd (выходит после 15 минут простоя)
                │  Requires=
                ▼
 aisktag-llm-backend.service   llama-server на 127.0.0.1:6574
                │  StopWhenUnneeded=yes → остановится вместе с прокси
                ▼
 /opt/aisktagos/ai/llama/{cpu,vulkan}/llama-server  +  модель .gguf
```

- Запрос «будит» модель; пока она грузится (на обычном ноутбуке 5–20 секунд, на медленном диске дольше), клиент ждёт в очереди сокета. `aisktag-llm-wait` пропускает запросы только после ответа `/health` = 200.
- После 15 минут без запросов прокси завершается, следом останавливается сервер — память освобождается.
- Службе разрешён только loopback (`IPAddressAllow=localhost`), она работает под временным пользователем (`DynamicUser`) с ограничениями `ProtectSystem=strict`, `NoNewPrivileges` и др.
- Веб-интерфейс самой модели: <http://127.0.0.1:6573> (команда `ai web`).

## Движок и модели

| Что | Откуда | Как закреплено |
|---|---|---|
| llama.cpp (CPU и Vulkan) | релизы ggml-org/llama.cpp (MIT) | сборка и SHA-256 в `config.env` |
| Модели | Hugging Face, только Apache-2.0 | `overlay/usr/share/aisktagos/ai/models.json`: URL и SHA-256 |

Каталог (`ai model`):

| id | Модель | Размер | Память | Для чего |
|---|---|---|---|---|
| `lite` | Qwen2.5-Coder 1.5B | 1,1 ГБ | от 3,4 ГБ | вшита в образ; быстрые вопросы и код |
| `standard` | Qwen3 4B Instruct | 2,4 ГБ | от 6,3 ГБ | умнее, лучше по-русски |
| `pro` | Qwen2.5-Coder 7B | 4,6 ГБ | от 10,7 ГБ | рефакторинг, ревью, тесты |

Движок выбирается автоматически (`/etc/aisktagos/ai.conf`, `AI_BACKEND=auto`): Vulkan, если есть настоящая видеокарта (программные llvmpipe/lavapipe не считаются), иначе процессор. Потоки — физические ядра; контекст — по модели, но не больше, чем позволяет свободная память.

## Команды

```bash
ai как отменить последний коммит              # вопрос
git diff | ai review                           # ревью изменений
cat ошибка.log | ai что это значит             # вывод команды как контекст
ai why                                         # разбор ошибки последней команды (в kitty берёт её вывод сам)
ai commit [-y]                                 # сообщение коммита по git diff --staged
ai cmd найти файлы больше 100 МБ               # одна shell-команда
ai explain main.py · ai review main.py         # объяснить / проверить файл
ai chat                                        # диалог (/persona code|review|admin|translate)
ai status · ai model [install|use|remove id]  # состояние и модели
ai env · ai run aider                          # переменные OPENAI_* / запуск инструмента с подключением к Mind
```

В zsh: **Ctrl+G** — описание в строке превращается в команду (подставляется, но не запускается); в kitty: **Ctrl+Shift+E** — объяснить вывод последней команды в окне поверх терминала. Модель **никогда не выполняет** команды сама.

## Подключение других инструментов

- **VS Code:** `code --install-extension Continue.continue` (или кнопка в Центре). Конфиг `~/.continue/config.yaml` уже указывает на Mind, в том числе для автодополнения.
- **Любой OpenAI-совместимый клиент:** base URL `http://127.0.0.1:6573/v1`, модель `aisktag-mind`, ключ любой.
- **Внешний сервер вместо локального:** Центр AIsktagOS → ИИ Mind → «Другой сервер» или `~/.config/aisktagos/ai.json`; переменные `AI_BASE_URL`, `AI_MODEL`, `AI_API_KEY` имеют приоритет.

## Файлы

| Файл | Назначение |
|---|---|
| `overlay/usr/bin/ai` | команда `ai` |
| `overlay/usr/lib/aisktagos/aisktag_ai.py` | клиентская библиотека (конфиг, потоковый чат, состояние, подбор модели) |
| `overlay/usr/lib/aisktagos/aisktag-mind.py` | окно ассистента (PyQt6), запуск: `aisktag-mind`, Meta+A |
| `overlay/usr/lib/aisktagos/ai/aisktag-llm-run` | запуск llama-server под железо |
| `overlay/usr/lib/aisktagos/ai/aisktag-ai-model` | установка и смена моделей (root, polkit-действие `org.aisktagos.ai.model`) |
| `overlay/usr/lib/systemd/system/aisktag-llm*.{socket,service}` | службы |
| `overlay/etc/aisktagos/ai.conf` | настройки |
| `overlay/usr/share/aisktagos/zsh/aisktag-ai.zsh` | интеграция с zsh |

## Разработка и тесты без модели

```bash
python3 tools/mock-llm.py 16573                            # заглушка OpenAI-сервера
AI_BASE_URL=http://127.0.0.1:16573/v1 python3 overlay/usr/bin/ai вопрос
python3 tools/shot-ui.py mind /tmp/mind.png                # снимок окна Mind (Qt offscreen)
```

## Известные ограничения

- Маленькая модель (1,5B) ошибается чаще большой: проверяйте команды перед запуском, для серьёзного кода берите `standard` или `pro`.
- Не проверено на реальном железе: Vulkan-ускорение на разных видеокартах, скорость первой загрузки на HDD. Если Vulkan не стартует, укажите `AI_BACKEND=cpu` в `/etc/aisktagos/ai.conf`.
