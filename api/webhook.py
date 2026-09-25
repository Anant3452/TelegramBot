"""Vercel serverless entry point. Telegram POSTs every update here.

setWebhook URL: https://<your-project>.vercel.app/api/webhook
"""

import hmac
import json
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from meera import pipeline  # noqa: E402
from meera.config import env  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Handy for checking that the deployment is live.
        self._reply(200, {"ok": True, "service": "meera-content-bot"})

    def do_POST(self):
        secret = env("TELEGRAM_WEBHOOK_SECRET")
        given = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if secret and not hmac.compare_digest(given, secret):
            return self._reply(401, {"ok": False})

        length = int(self.headers.get("Content-Length") or 0)
        try:
            update = json.loads(self.rfile.read(length) or b"{}")
            pipeline.handle_update(update)
        except Exception:
            traceback.print_exc()  # visible in Vercel's function logs
        # Always 200: a non-200 makes Telegram redeliver the same update in a loop.
        self._reply(200, {"ok": True})

    def _reply(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
