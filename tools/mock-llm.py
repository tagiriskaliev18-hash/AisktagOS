#!/usr/bin/env python3
"""Заглушка OpenAI-совместимого сервера для разработки Mind без модели.

    python3 tools/mock-llm.py [порт]        # по умолчанию 6573, как у настоящей службы

Отдаёт /health и потоковый /v1/chat/completions: ответ строится из последнего сообщения пользователя,
поэтому видно, что именно получила «модель» (системный промпт, вложенный вывод команд, diff).
Задержка первого токена имитирует загрузку модели: MOCK_LOAD_SECONDS=3 python3 tools/mock-llm.py
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 6573
LOAD = float(os.environ.get("MOCK_LOAD_SECONDS", "0"))


def reply_for(messages: list[dict]) -> str:
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    if "ОДНУ команду" in system:                      # режим ai cmd
        return "find . -type f -size +100M"
    if "git-коммита" in user:                         # режим ai commit
        return "feat(ai): добавить встроенного ассистента\n\n- команда ai и окно Mind"
    return (f"**Mock Mind**: получил {len(messages)} сообщ.\n\n"
            f"Роль: `{system[:50]}…`\n\nВопрос:\n\n```text\n{user[:300]}\n```\n\n"
            "Пример кода:\n\n```python\nprint('привет из AIsktagOS')\n```\n")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith(("/health", "/v1/health")):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_error(404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        text = reply_for(body.get("messages", []))
        time.sleep(LOAD)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for i in range(0, len(text), 6):
            chunk = {"choices": [{"delta": {"content": text[i:i + 6]}}]}
            self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()
            time.sleep(0.01)
        self.wfile.write(b"data: [DONE]\n\n")


if __name__ == "__main__":
    print(f"mock-llm слушает 127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
