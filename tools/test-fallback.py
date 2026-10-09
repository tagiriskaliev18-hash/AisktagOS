#!/usr/bin/env python3
"""Проверка запасных поставщиков ИИ без настоящих серверов.

  python3 tools/test-fallback.py

Три заглушки: «облако A» (OpenAI-формат, кончились токены), «облако B» (формат Anthropic, как Kimi через
tokenwave.ru) и «встроенная модель». Проверяем, что Джарвис и Mind сами переходят к следующему поставщику,
говорят об этом, а формат Anthropic (вызовы инструментов, потоковый ответ) переводится правильно.
"""
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "overlay/usr/lib/aisktagos"))
TMP = Path(tempfile.mkdtemp(prefix="fallback-test-"))
os.environ["HOME"] = str(TMP)
for v in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME",
          "JARVIS_BASE_URL", "JARVIS_MODEL", "JARVIS_API_KEY", "AI_BASE_URL", "AI_MODEL", "AI_API_KEY"):
    os.environ.pop(v, None)

state = {"a": 429, "b": 200}       # что отвечают облака сейчас
seen = {"a": [], "b": [], "local": []}


def send(h, code, data, ctype="application/json"):
    raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
    h.send_response(code)
    h.send_header("Content-Type", ctype)
    h.send_header("Content-Length", str(len(raw)))
    h.end_headers()
    h.wfile.write(raw)


class CloudA(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        seen["a"].append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        send(self, state["a"], {"error": {"message": "Rate limit reached: tokens per day"}})


class CloudB(BaseHTTPRequestHandler):
    """Сервер в формате Anthropic: /v1/messages."""
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seen["b"].append({"path": self.path, "body": body, "key": self.headers.get("x-api-key"),
                          "auth": self.headers.get("Authorization")})
        if self.path != "/v1/messages":
            return send(self, 404, {"error": "not found"})
        if state["b"] != 200:
            return send(self, state["b"], {"type": "error", "error": {"type": "billing_error",
                                                                      "message": "insufficient balance"}})
        if body.get("stream"):
            events = [{"type": "message_start"}, {"type": "content_block_start", "index": 0},
                      {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Привет "}},
                      {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "от Kimi"}},
                      {"type": "message_stop"}]
            raw = "".join(f"event: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events)
            return send(self, 200, raw.encode(), "text/event-stream")
        last = body["messages"][-1]
        has_result = any(b.get("type") == "tool_result" for b in last["content"])
        if body.get("tools") and not has_result:
            content = [{"type": "text", "text": "Запишу файл."},
                       {"type": "tool_use", "id": "tu_1", "name": "write_file",
                        "input": {"path": str(TMP / "kimi.txt"), "content": "записал Kimi\n"}}]
        else:
            content = [{"type": "text", "text": "Готово, ответил Kimi."}]
        send(self, 200, {"type": "message", "role": "assistant", "content": content, "stop_reason": "end_turn"})


class Local(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        send(self, 404, {})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seen["local"].append(body)
        if body.get("stream"):
            chunk = {"choices": [{"delta": {"content": "ответ встроенной модели"}}]}
            raw = f"data: {json.dumps(chunk, ensure_ascii=False)}\n\ndata: [DONE]\n\n".encode()
            return send(self, 200, raw, "text/event-stream")
        send(self, 200, {"choices": [{"message": {"role": "assistant", "content": "Готово, ответила встроенная."}}]})


def serve(handler, host):
    srv = HTTPServer((host, 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://{host}:{srv.server_address[1]}/v1"


# 127.0.0.2 — тоже этот компьютер, но для AIsktagOS это «внешний сервер» (не локальная модель)
URL_A, URL_B, URL_LOCAL = serve(CloudA, "127.0.0.2"), serve(CloudB, "127.0.0.2"), serve(Local, "127.0.0.1")

import aisktag_ai as ai  # noqa: E402
import aisktag_jarvis as jv  # noqa: E402
import aisktag_jarvis_cli as cli  # noqa: E402

ai.LOCAL_URL = URL_LOCAL
ai.DEFAULTS["base_url"] = URL_LOCAL
ai.list_models = lambda: {"active": "standard", "models": []}

failed = False


def check(cond, what):
    global failed
    print(("OK   " if cond else "FAIL ") + what)
    failed |= not cond


# --- Подключение Kimi: формат определяется сам, ключ — только в файлах пользователя -------------
cli.PROVIDERS["kimi"] = ("Kimi", URL_B, "", ["kimi-k3"])
cli.PROVIDERS["groq"] = ("Groq", URL_A, "", ["llama"])
check(cli.connect("kimi", "sk-test-kimi", backup=True), "kimi подключается запасной (формат Anthropic)")
prov = ai.load_providers()
check(prov and prov[0]["api"] == "anthropic" and prov[0]["model"] == "kimi-k3", "в providers.json записан формат и модель")
check(oct(ai.PROVIDERS_CONF.stat().st_mode & 0o777) == "0o600", "файл с ключами доступен только владельцу")
check(seen["b"][-1]["key"] == "sk-test-kimi" and seen["b"][-1]["auth"] == "Bearer sk-test-kimi",
      "ключ уходит в x-api-key и Authorization")

# Основная — «облако A» (как Groq), у него кончились токены
jv.CONF.parent.mkdir(parents=True, exist_ok=True)
jv.CONF.write_text(json.dumps({"base_url": URL_A, "model": "llama", "api_key": "k", "name": "Groq"}), encoding="utf-8")
names = [ai.label(c) for c in ai.chain(jv.load_config())]
check(len(names) == 3 and names[0].startswith("Groq") and names[1].startswith("Kimi") and "встроенная" in names[2],
      f"порядок: основная → запасная → встроенная ({' → '.join(names)})")

# --- Джарвис: основной отказал (429) → Kimi с инструментами ----------------------------------------
events = []
agent = jv.Agent(lambda n, w: True, lambda k, t: events.append((k, t)))
answer = agent.ask("запиши файл kimi.txt")
switches = [t for k, t in events if k == "switch"]
check(answer == "Готово, ответил Kimi.", f"Джарвис ответил через запасную ({answer!r})")
check(switches and "лимит" in switches[0] and "Kimi" in switches[0], f"Джарвис сказал о переключении: {switches[:1]}")
check((TMP / "kimi.txt").read_text(encoding="utf-8") == "записал Kimi\n", "вызов инструмента в формате Anthropic выполнен")
second = seen["b"][-1]["body"]["messages"]
check(any(b.get("type") == "tool_use" for b in second[-2]["content"])
      and second[-1]["content"][0]["type"] == "tool_result" and second[-1]["content"][0]["tool_use_id"] == "tu_1",
      "история с вызовом и результатом переведена в формат Anthropic")
check(isinstance(seen["b"][-1]["body"].get("system"), str) and seen["b"][-1]["body"]["tools"][0].get("input_schema"),
      "системный промпт и описания инструментов переданы")

# Следующая задача: «облако A» отдыхает после отказа — его не ждём
before_a = len(seen["a"])
events.clear()
agent.ask("ещё раз")
check(len(seen["a"]) == before_a, "отказавший сервер пропускается, пока отдыхает")

# --- Деньги кончились и у Kimi: отвечает встроенная модель --------------------------------------------
state["b"] = 402
events.clear()
answer = agent.ask("последняя задача")
switches = [t for k, t in events if k == "switch"]
check(answer == "Готово, ответила встроенная.", f"последней отвечает встроенная модель ({answer!r})")
check(any("деньги" in s and "встроенная" in s for s in switches), f"сказано, кто ответил: {switches}")
agent.close()

# --- Mind (потоковый ответ) ----------------------------------------------------------------------------
STATE = ai.STATE_FILE
STATE.unlink(missing_ok=True)                 # забыть паузы
state.update(a=402, b=200)
notes = []
mind_cfg = dict(ai.load_config(), base_url=URL_A, model="llama", api_key="k", name="Groq")
text = "".join(ai.stream_chat([{"role": "system", "content": "s"}, {"role": "user", "content": "привет"}],
                              mind_cfg, on_switch=lambda p, n, e: notes.append(ai.switch_text(p, n, e))))
check(text == "Привет от Kimi", f"Mind: потоковый ответ от Kimi в формате Anthropic ({text!r})")
check(notes and "деньги" in notes[0] and "Kimi" in notes[0], f"Mind: сообщение о переключении: {notes}")

# Ошибка самого запроса (400, контекст) — не повод менять поставщика
class Bad(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        send(self, 400, {"error": {"message": "context length exceeded"}})


try:
    "".join(ai.stream_chat([{"role": "user", "content": "x"}], dict(mind_cfg, base_url=serve(Bad, "127.0.0.2"))))
    check(False, "400 (контекст) не переключает поставщика")
except ai.ProviderDown:
    check(False, "400 (контекст) не переключает поставщика")
except ai.AIError:
    check(True, "400 (контекст) не переключает поставщика")

check("sk-test-kimi" not in (ROOT / "overlay").joinpath("usr/lib/aisktagos/aisktag_jarvis_cli.py").read_text(),
      "ключей в коде нет")
print("Папка теста:", TMP)
sys.exit(1 if failed else 0)
