# Meera's Content Bot (MESA Case 1)

Meera drops a note (text or voice) into her private Telegram channel. The bot:

1. **Scores** it 0–10 with Gemini Flash. Below 6, it replies with a one-line reason and stops.
2. **Finds a news angle**: Gemini pulls a search phrase, then it takes the top Google News result from the last 30 days (no key needed).
3. **Drafts** a LinkedIn post in Meera's voice (`voice-skill.txt`), using the news only if it genuinely fits.
4. **Sends the draft back** to the channel. Any draft that uses news ends with a `NEWS SOURCE … ⚠ Check this before publishing` block, which the code appends itself so the model can't leave it off.
5. **Remembers** everything in Supabase. Meera replies `APPROVE` or `REJECT` to a draft to record her decision. Nothing is deleted.

**The Cut (check 07, Judgment Protected):** the bot never publishes or schedules. Its last step is a draft in Telegram; reviewing, editing and posting to LinkedIn stay with Meera.

```
Telegram channel ──webhook──▶ api/webhook.py (Vercel)
                                 │
            ┌────────────────────┼─────────────────────┐
     Gemini Flash          Google News RSS       Gemini / Claude
   score · keywords ·       top story            draft in voice
   voice transcription                                  │
                                 ▼                      ▼
                            Supabase  ◀──── draft back to Telegram ──▶ Meera reviews,
                       notes · drafts · voice_skill                     edits, publishes
```

## Files

| Path | What it does |
| --- | --- |
| `api/webhook.py` | Vercel function Telegram posts every update to |
| `meera/pipeline.py` | The flow: score → news → draft → reply, plus APPROVE/REJECT |
| `meera/prompts.py` | Every prompt, in one place for tuning |
| `meera/llm.py` | Gemini and Claude calls (with model fallback on overload) |
| `meera/news.py` | Google News RSS lookup |
| `meera/store.py` | Supabase tables (optional: the bot drafts without it) |
| `voice-skill.txt` | Meera's voice profile, built from the 15 published pieces |
| `supabase/schema.sql` | The three tables: `notes`, `drafts`, `voice_skill` |
| `scripts/try_note.py` | Run notes locally, no Telegram needed |
| `samples/` | Meera's five notes plus two weak ones for testing the scorer |

No dependencies: everything uses the Python standard library.

## Setup

**1. Keys.** `cp .env.example .env` and fill in `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `TELEGRAM_CHAT_ID` (the `-100…` id from @userinfobot) and a random `TELEGRAM_WEBHOOK_SECRET`. `.env` is gitignored.

**2. Try it locally** (makes Gemini calls; nothing is sent to Telegram):

```bash
python3 scripts/try_note.py samples/note_02.txt samples/weak_reminder.txt
```

**3. Supabase (memory).** Create a project, run `supabase/schema.sql` in the SQL editor, put `SUPABASE_URL` and the **service_role** key in `.env` as `SUPABASE_SERVICE_KEY`, then optionally `python3 scripts/seed_voice_skill.py` so the voice skill lives in the DB (the bot falls back to `voice-skill.txt`).

**4. Deploy.** Push to GitHub → import the repo in Vercel → add every variable from `.env` under *Environment Variables* → Deploy. Opening `https://<project>.vercel.app/api/webhook` should show `{"ok": true, ...}`.

**5. Connect Telegram:**

```bash
python3 scripts/set_webhook.py https://<project>.vercel.app
```

This is the same as the class's `setWebhook?url=…` browser link, but it also passes the secret token. If you use the browser link instead, add `&secret_token=<your secret>`, or leave `TELEGRAM_WEBHOOK_SECRET` unset.

**6. Test.** Post `samples/note_02.txt` in the channel → a draft should arrive in about 15–30 s. Post `samples/weak_reminder.txt` → a rejection. Reply `APPROVE` to the draft → its row in `drafts` flips to `approved`.

## Model comparison (B1 final 15 min)

Set `DRAFT_PROVIDER=claude` and `ANTHROPIC_API_KEY` (and optionally `CLAUDE_MODEL`, default `claude-sonnet-5`), redeploy, and send the same note again. Scoring and keywords stay on Gemini Flash; only drafting switches. Each draft row records its `provider` and `model`.

## Notes

- **Gemini free tier:** about 20 requests per model per day, and each note uses 3 (score, keywords, draft). The code falls through `gemini-3.8-flash → gemini-3.5-flash → gemini-flash-latest` when one is over quota or overloaded, but for real daily use, enable billing on the key.
- The bot only listens to `TELEGRAM_CHAT_ID`. It also works in a direct chat with the bot if you set that chat's id instead.
- Telegram redelivers updates that fail; with Supabase on, repeats are skipped by `update_id`.
