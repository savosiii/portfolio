"""Приёмник заявок для веб-бота (app/index.html).

Крошечный сервер: принимает POST /lead от сайта и пересылает заявку
владельцу в Telegram. Без внешних зависимостей — только стандартная
библиотека Python.

Запуск:
    1. Создайте бота через @BotFather, узнайте свой chat_id через @userinfobot
    2. В папке app/ создайте .env:
           BOT_TOKEN=123456:ABC-...
           CHAT_ID=123456789
           PORT=8787
    3. python relay_bot.py
    4. В src/config.js укажите: leadWebhook: 'http://ВАШ-СЕРВЕР:8787/lead'

Для постоянной работы на сервере положите за systemd / pm2 / nginx+uwsgi —
скрипт специально написан на stdlib, чтобы ставился куда угодно.
"""

import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # dotenv нет — читаем переменные окружения как есть
    pass

TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")
PORT = int(os.getenv("PORT", "8787"))

CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def send_to_telegram(lead: dict) -> bool:
    text = (
        "🔔 <b>Новая заявка с сайта</b>\n"
        f"Компания: {lead.get('company', '—')}\n"
        f"Имя: {lead.get('name', '—')}\n"
        f"Телефон: {lead.get('phone', '—')}\n"
        f"Вопрос: {lead.get('question') or '—'}\n"
        f"Страница: {lead.get('page', '—')}"
    )
    payload = json.dumps({
        "chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
    }).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, obj: dict):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._json(204, {})

    def do_GET(self):
        self._json(200, {"ok": True, "service": "lead-relay",
                         "telegram": bool(TOKEN and CHAT_ID)})

    def do_POST(self):
        if self.path.rstrip("/") != "/lead":
            self._json(404, {"ok": False, "error": "unknown path"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            lead = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._json(400, {"ok": False, "error": "bad json"})
            return
        if not lead.get("name") or not lead.get("phone"):
            self._json(400, {"ok": False, "error": "name and phone required"})
            return
        ok = send_to_telegram(lead) if (TOKEN and CHAT_ID) else False
        self._json(200, {"ok": True, "delivered": ok})

    def log_message(self, *args):  # тихий лог
        pass


if __name__ == "__main__":
    print(f"🚀 Lead-relay слушает порт {PORT}. Проверка: http://localhost:{PORT}/")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
