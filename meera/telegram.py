"""Telegram Bot API calls."""

from . import http
from .config import env

API = "https://api.telegram.org/bot{token}/{method}"
FILE = "https://api.telegram.org/file/bot{token}/{path}"
MAX_LEN = 4096  # Telegram's per-message limit


def _token():
    token = env("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    return token


def call(method, **params):
    resp = http.request("POST", API.format(token=_token(), method=method), body=params, timeout=30)
    if not resp.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {resp}")
    return resp["result"]


def send(chat_id, text, reply_to=None):
    """Send plain text (no parse_mode, so drafts never break on stray * or _).
    Long text is split on paragraph boundaries. Returns the sent message ids."""
    ids = []
    for i, chunk in enumerate(_chunks(text)):
        params = {"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True}
        if reply_to and i == 0:
            params["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
        ids.append(call("sendMessage", **params)["message_id"])
    return ids


def download(file_id):
    path = call("getFile", file_id=file_id)["file_path"]
    return http.request("GET", FILE.format(token=_token(), path=path), raw=True, timeout=30)


def _chunks(text, limit=MAX_LEN):
    chunks, current = [], ""
    for para in text.split("\n\n"):
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(para) > limit:
            chunks.append(para[:limit])
            para = para[limit:]
        current = para
    if current:
        chunks.append(current)
    return chunks or [""]
