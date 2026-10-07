#!/usr/bin/env python3
"""Проверка Джарвиса без настоящей модели: заглушка OpenAI-сервера отдаёт заранее заданные вызовы инструментов.

  python3 tools/test-jarvis.py                  файлы, команды, разбор вызова из текста, отказ пользователя
  JARVIS_FIREFOX=/путь/к/firefox JARVIS_HEADLESS=1 python3 tools/test-jarvis.py   ещё и браузер
"""
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "overlay/usr/lib/aisktagos"))
TMP = Path(tempfile.mkdtemp(prefix="jarvis-test-"))
os.environ["HOME"] = str(TMP)                      # профиль браузера, журнал и настройки — во временной папке
os.environ.pop("XDG_CONFIG_HOME", None)
os.environ.pop("XDG_STATE_HOME", None)
os.environ.pop("XDG_DATA_HOME", None)

PAGE = ('<html><head><meta charset="utf-8"><title>Тест</title></head><body><form action="r.html">'
        '<input name="q" placeholder="Что найти"><button>Найти</button></form></body></html>')
RESULT = ('<html><head><meta charset="utf-8"><title>Итог</title></head><body><p id=r></p><script>'
          'r.innerText="Вы искали: "+new URLSearchParams(location.search).get("q")</script></body></html>')

STEPS = [
    [("write_file", {"path": str(TMP / "a.txt"), "content": "первая строка\nвторая строка\n"})],
    [("read_file", {"path": str(TMP / "a.txt")}), ("list_dir", {"path": str(TMP)})],
    [("edit_file", {"path": str(TMP / "a.txt"), "old": "вторая", "new": "2-я"})],
    [("run_command", {"command": "rm -rf /tmp/never"})],          # пользователь откажет
    "TEXT:<tool_call>{\"name\": \"search_files\", \"arguments\": {\"path\": \"%s\", \"pattern\": \"*.txt\", "
    "\"text\": \"2-я\"}}</tool_call>" % TMP,
    [("run_command", {"command": "echo $((6*7))"})],
]
BROWSER_STEPS = [
    [("browser_open", {"url": "http://127.0.0.1:{web}/index.html"})],
    [("browser_elements", {})],
    [("browser_type", {"id": 1, "text": "котики", "submit": True})],
    [("browser_read", {})],
]
browser = bool(os.environ.get("JARVIS_FIREFOX"))
if browser:
    STEPS += BROWSER_STEPS
STEPS.append("Готово.")
requests = []


class LLM(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        requests.append(body)
        step = STEPS[min(len(requests) - 1, len(STEPS) - 1)]
        if isinstance(step, list):
            msg = {"role": "assistant", "content": None, "tool_calls": [
                {"id": f"c{len(requests)}_{k}", "type": "function",
                 "function": {"name": n, "arguments": json.dumps(a, ensure_ascii=False).replace("{web}", str(WEB_PORT))}}
                for k, (n, a) in enumerate(step)]}
        else:
            msg = {"role": "assistant", "content": step[5:] if step.startswith("TEXT:") else step}
        data = json.dumps({"choices": [{"message": msg}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(handler, directory=None):
    h = handler if directory is None else (lambda *a, **k: Quiet(*a, directory=directory, **k))
    srv = HTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


web_dir = TMP / "web"
web_dir.mkdir()
(web_dir / "index.html").write_text(PAGE, encoding="utf-8")
(web_dir / "r.html").write_text(RESULT, encoding="utf-8")
WEB_PORT = serve(None, str(web_dir))
os.environ["JARVIS_BASE_URL"] = f"http://127.0.0.1:{serve(LLM)}/v1"
os.environ["JARVIS_MODEL"] = "test"

import aisktag_jarvis as jv  # noqa: E402

asked, events = [], []


def confirm(name, what):
    asked.append(what)
    return name != "run_command" or "rm -rf" not in what


agent = jv.Agent(confirm, lambda kind, text: events.append((kind, text)))
try:
    answer = agent.ask("проверка")
finally:
    agent.close()

results = [t for k, t in events if k == "result"]


def check(cond, what):
    print(("OK   " if cond else "FAIL ") + what)
    if not cond:
        check.failed = True


check.failed = False
check(answer == "Готово.", "агент дошёл до ответа")
check((TMP / "a.txt").read_text(encoding="utf-8") == "первая строка\n2-я строка\n", "запись и правка файла")
check(any("первая строка" in r for r in results), "чтение файла")
check(any("отказался" in r for r in results), "отказ пользователя не выполняет команду")
check(any("a.txt:2" in r for r in results), "вызов инструмента из текста (<tool_call>)")
check(any("42" in r for r in results), "выполнение команды")
check(len(asked) == 4, f"подтверждение спрашивается для записи, правки и команд ({len(asked)})")
check(all(len(r["tools"]) == len(jv.TOOLS) for r in requests), "модель получает список инструментов")
check(requests[-1]["messages"][0]["role"] == "system", "системное сообщение на месте")
if browser:
    check(any("Вы искали: котики" in r for r in results), "браузер: ввод в поле, отправка формы, чтение страницы")
print("Журнал:", TMP / ".local/state/aisktagos/jarvis.log")
sys.exit(1 if check.failed else 0)
