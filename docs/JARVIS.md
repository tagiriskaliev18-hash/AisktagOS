# Джарвис — ИИ-агент AIsktagOS

Mind отвечает на вопросы, а Джарвис **сам выполняет задачи**: читает и правит файлы, запускает команды,
открывает приложения, смотрит на экран и работает в браузере — как Claude in Chrome, только локально.

```bash
jarvis                                   # диалог (Meta+J или ярлык «Джарвис» на рабочем столе)
jarvis найди в ~/Загрузки PDF больше 10 МБ и перенеси их в ~/Документы/PDF
jarvis открой github.com/trending и выпиши 5 популярных репозиториев на Python
jarvis посмотри, что у меня на экране, и объясни ошибку
jarvis -y …                              # не спрашивать подтверждения
jarvis --setup                           # подключить другой сервер ИИ
jarvis --status                          # какая модель используется
```

## Что умеет (инструменты)

| Область | Инструменты |
|---|---|
| Файлы | `list_dir`, `read_file`, `search_files`, `write_file`*, `edit_file`* |
| Терминал | `run_command`* (bash, вывод и код возврата) |
| Приложения | `open_app` (по названию из меню), `open_path` (файл, папка, ссылка) |
| Экран | `screen_read`: снимок (spectacle) + распознавание текста (tesseract, русский и английский); модели со зрением получают и саму картинку |
| Буфер, уведомления | `clipboard_get`, `clipboard_set`, `notify` |
| Браузер | `browser_open`, `browser_read`, `browser_elements`, `browser_click`, `browser_type`, `browser_key`, `browser_scroll`, `browser_back`, `browser_tabs`, `browser_screenshot` |

\* — только после подтверждения пользователя (ответ «в» — разрешить до конца сеанса, `-y` — всегда).

## Браузер (как Claude in Chrome)

Джарвис управляет **отдельным окном Firefox** со своим профилем (`~/.local/share/aisktagos/jarvis/firefox`)
через стандартный протокол WebDriver BiDi (`--remote-debugging-port 9333`, только `127.0.0.1`).
Пароли, куки и история основного Firefox ему не видны; войти на сайт в окне Джарвиса можно вручную.

Как модель видит страницу: `browser_elements` нумерует видимые кнопки, ссылки и поля
(`[3] button «Найти»`), `browser_click 3` нажимает настоящей мышью (событиями браузера, не JavaScript),
`browser_type` печатает с клавиатуры. Номера обновляются после каждого перехода.

## Безопасность

- Команды, запись и правка файлов — только с разрешения пользователя.
- Системный промпт запрещает выполнять «указания» из веб-страниц, файлов и вывода команд (защита от
  prompt injection) и требует спросить пользователя перед покупкой, отправкой сообщений, вводом паролей.
- Журнал действий: `~/.local/state/aisktagos/jarvis.log`.

## Какая модель

По умолчанию Джарвис использует ту же модель, что и Mind (`~/.config/aisktagos/ai.json`). Для многошаговых
задач встроенной модели 1.5B мало: поставьте `standard`/`pro` (`ai model install pro`) или подключите сильную
облачную модель с поддержкой вызова инструментов (`jarvis --setup`, файл `~/.config/aisktagos/jarvis.json`):

```json
{"base_url": "https://api.openai.com/v1", "model": "gpt-4o", "api_key": "sk-…", "vision": true}
```

Переменные `JARVIS_BASE_URL`, `JARVIS_MODEL`, `JARVIS_API_KEY` важнее файла.

## Файлы и проверка

| Файл | Назначение |
|---|---|
| `overlay/usr/bin/jarvis` | команда и диалог в терминале |
| `overlay/usr/lib/aisktagos/aisktag_jarvis.py` | цикл агента и инструменты |
| `overlay/usr/lib/aisktagos/aisktag_browser.py` | управление Firefox (WebDriver BiDi, свой клиент WebSocket) |
| `tools/test-jarvis.py` | тест на заглушке модели; с `JARVIS_FIREFOX=… JARVIS_HEADLESS=1` — и браузер |

Пока не умеет: двигать мышь и печатать в произвольных окнах рабочего стола (в Wayland для этого нужен
`ydotool` с доступом к `/dev/uinput`) — приложения он запускает, а управляет через команды и браузер.
