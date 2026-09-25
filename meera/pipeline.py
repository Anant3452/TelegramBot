"""The pipeline: note -> score -> (news) -> draft -> Telegram, with Supabase memory.

Nothing here posts to LinkedIn. The bot's last step is sending Meera a draft;
reviewing, editing and publishing stay with her (the Cut: check 07)."""

import re

from . import llm, news, prompts, store, telegram
from .config import ROOT, SCORE_THRESHOLD, env

DIVIDER = "─" * 33

HELP = (
    "Send me a note (text or a voice note). I'll score it, and if it's worth "
    f"developing ({SCORE_THRESHOLD}/10 or above) I'll send back a LinkedIn draft in your voice.\n\n"
    "Reply to a draft with APPROVE or REJECT to record your decision. "
    "I never publish anything. That part is yours."
)


# --- core: pure function, no Telegram or DB, so it can be run locally ------

def voice_skill():
    return store.active_voice_skill() or (ROOT / "voice-skill.txt").read_text()


def score(note):
    result = llm.gemini_json(f'Note:\n"""{note}"""', system=prompts.SCORE_SYSTEM)
    value = max(0, min(10, int(round(float(result.get("score", 0))))))
    return value, str(result.get("reason", "")).strip()


def find_news(note):
    try:
        result = llm.gemini_json(prompts.KEYWORDS_PROMPT.format(note=note))
        phrase = str(result.get("search_phrase", "")).strip()
    except Exception:
        return None, None
    return phrase, (news.top_story(phrase) if phrase else None)


def draft(note, story):
    news_block = prompts.NEWS_BLOCK.format(**story) if story else prompts.NO_NEWS_BLOCK
    text, provider, model = llm.draft_model(
        prompts.DRAFT_PROMPT.format(note=note, news_block=news_block),
        system=prompts.DRAFT_SYSTEM.format(voice=voice_skill()),
    )
    # The model reports whether it used the news; we strip that line and add
    # the verify block ourselves so it can never be silently left off.
    match = re.search(r"\n?\s*USED_NEWS:\s*(yes|no)\s*$", text, re.I)
    used_news = bool(story) and (match is None or match.group(1).lower() == "yes")
    post = text[: match.start()].rstrip() if match else text.rstrip()
    return post, used_news, provider, model


def develop(note):
    """Run one note through the whole pipeline. Returns a dict describing what happened."""
    value, reason = score(note)
    result = {"score": value, "reason": reason, "passed": value >= SCORE_THRESHOLD}
    if not result["passed"]:
        return result
    phrase, story = find_news(note)
    post, used_news, provider, model = draft(note, story)
    result.update(search_phrase=phrase, news=story, post=post,
                  used_news=used_news, provider=provider, model=model)
    return result


def verify_block(story):
    return (
        f"{DIVIDER}\n"
        f"NEWS SOURCE: {story['headline']}\n"
        f"FROM: {story['source']} · {story['date']}\n"
        f"LINK: {story['link']}\n"
        f"⚠ Check this before publishing - you are the author of this claim\n"
        f"{DIVIDER}"
    )


def format_draft(result, draft_id=None):
    label = f"DRAFT #{draft_id}" if draft_id else "DRAFT"
    parts = [f"📝 {label} · scored {result['score']}/10: {result['reason']}", result["post"]]
    if result["used_news"]:
        parts.append(verify_block(result["news"]))
    parts.append("Reply to this message with APPROVE or REJECT." if draft_id
                 else "Review, edit, and publish it yourself when it's ready.")
    return "\n\n".join(parts)


def format_rejection(result):
    return (f"No draft: scored {result['score']}/10 (needs {SCORE_THRESHOLD}+).\n"
            f"{result['reason']}")


# --- Telegram glue ---------------------------------------------------------

def handle_update(update):
    msg = update.get("channel_post") or update.get("message")
    if not msg:
        return  # edits, reactions, membership changes, etc.
    chat_id = msg["chat"]["id"]

    allowed = env("TELEGRAM_CHAT_ID")
    if allowed and str(chat_id) != allowed:
        return  # only listen to Meera's capture channel

    text = (msg.get("text") or msg.get("caption") or "").strip()

    if text.startswith("/"):
        if text.split()[0].split("@")[0] in ("/start", "/help"):
            telegram.send(chat_id, HELP)
        return

    decision = re.fullmatch(r"(APPROVE|REJECT)\s*#?(\d+)?", text, re.I)
    if decision:
        return handle_decision(msg, decision.group(1).upper(), decision.group(2))

    if store.note_seen(update["update_id"]):
        return  # Telegram re-delivered an update we already handled

    source = "text"
    voice = msg.get("voice") or msg.get("audio")
    if voice:
        source = "voice"
        audio = telegram.download(voice["file_id"])
        text, _ = llm.gemini(prompts.TRANSCRIBE_PROMPT,
                             audio=(audio, voice.get("mime_type", "audio/ogg")), temperature=0)
    if not text:
        return

    note = store.save_note(telegram_update_id=update["update_id"], chat_id=chat_id,
                           message_id=msg["message_id"], source=source, text=text)
    note_id = note and note["id"]

    try:
        result = develop(text)
    except Exception as e:
        store.update_note(note_id, status="error", error=str(e)[:1000])
        telegram.send(chat_id, f"Something went wrong processing this note: {e}", reply_to=msg["message_id"])
        raise

    store.update_note(note_id, score=result["score"], score_reason=result["reason"],
                      status="drafted" if result["passed"] else "rejected")

    if not result["passed"]:
        telegram.send(chat_id, format_rejection(result), reply_to=msg["message_id"])
        return

    story = result["news"] or {}
    row = store.save_draft(
        note_id=note_id, chat_id=chat_id, body=result["post"],
        provider=result["provider"], model=result["model"],
        search_phrase=result["search_phrase"], used_news=result["used_news"],
        news_headline=story.get("headline"), news_source=story.get("source"),
        news_date=story.get("date"), news_link=story.get("link"),
    )
    draft_id = row and row["id"]
    ids = telegram.send(chat_id, format_draft(result, draft_id), reply_to=msg["message_id"])
    store.update_draft(draft_id, telegram_message_ids=ids)


def handle_decision(msg, verdict, draft_id):
    chat_id = msg["chat"]["id"]
    if not store.enabled():
        telegram.send(chat_id, "Decisions aren't being saved: Supabase isn't configured.")
        return
    replied = (msg.get("reply_to_message") or {}).get("message_id")
    row = store.find_draft(draft_id=draft_id, message_id=None if draft_id else replied, chat_id=chat_id)
    if not row:
        telegram.send(chat_id, "I couldn't find that draft. Reply directly to the draft, "
                               "or send e.g. APPROVE 12.", reply_to=msg["message_id"])
        return
    status = "approved" if verdict == "APPROVE" else "rejected"
    store.decide_draft(row["id"], status)
    follow_up = ("Publishing is yours: copy it to LinkedIn when you're ready."
                 if status == "approved" else "Kept on file so we can see what needs improving.")
    telegram.send(chat_id, f"Draft #{row['id']} marked {status}. {follow_up}", reply_to=msg["message_id"])
