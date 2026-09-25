"""Supabase memory layer, via its REST (PostgREST) API.

Optional: if SUPABASE_URL / SUPABASE_SERVICE_KEY aren't set, every call is a
no-op and the bot still drafts. Nothing is ever deleted: rejected notes and
rejected drafts stay in the tables as a record of what needs improving."""

import urllib.parse
from datetime import datetime, timezone

from . import http
from .config import env


def enabled():
    return bool(env("SUPABASE_URL") and env("SUPABASE_SERVICE_KEY"))


def _req(method, table, *, params=None, body=None, prefer="return=representation"):
    key = env("SUPABASE_SERVICE_KEY")
    url = f"{env('SUPABASE_URL').rstrip('/')}/rest/v1/{table}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": prefer}
    return http.request(method, url, headers=headers, body=body, timeout=15)


def _one(rows):
    return rows[0] if rows else None


# --- notes -----------------------------------------------------------------

def note_seen(update_id):
    """True if this Telegram update was already processed (Telegram retries webhooks)."""
    if not enabled():
        return False
    return bool(_req("GET", "notes", params={"telegram_update_id": f"eq.{update_id}", "select": "id"}))


def save_note(**fields):
    if not enabled():
        return None
    return _one(_req("POST", "notes", body=fields))


def update_note(note_id, **fields):
    if enabled() and note_id:
        _req("PATCH", "notes", params={"id": f"eq.{note_id}"}, body=fields, prefer="return=minimal")


# --- drafts ----------------------------------------------------------------

def save_draft(**fields):
    if not enabled():
        return None
    return _one(_req("POST", "drafts", body={"status": "pending", **fields}))


def update_draft(draft_id, **fields):
    if enabled() and draft_id:
        _req("PATCH", "drafts", params={"id": f"eq.{draft_id}"}, body=fields, prefer="return=minimal")


def find_draft(*, draft_id=None, message_id=None, chat_id=None):
    """Find a draft by id, by any Telegram message it was sent as, or else the
    latest pending draft in this chat."""
    if not enabled():
        return None
    params = {"select": "*", "order": "created_at.desc", "limit": 1}
    if draft_id:
        params["id"] = f"eq.{draft_id}"
    elif message_id:
        params["telegram_message_ids"] = f"cs.{{{message_id}}}"
        params["chat_id"] = f"eq.{chat_id}"
    else:
        params["status"] = "eq.pending"
        params["chat_id"] = f"eq.{chat_id}"
    return _one(_req("GET", "drafts", params=params))


def decide_draft(draft_id, status):
    update_draft(draft_id, status=status, decided_at=datetime.now(timezone.utc).isoformat())


# --- voice skill -----------------------------------------------------------

def active_voice_skill():
    """Latest active voice skill from the DB, or None to fall back to voice-skill.txt."""
    if not enabled():
        return None
    try:
        row = _one(_req("GET", "voice_skill", params={
            "select": "content", "active": "eq.true", "order": "created_at.desc", "limit": 1,
        }))
    except http.HTTPError:
        return None
    return row["content"] if row else None
