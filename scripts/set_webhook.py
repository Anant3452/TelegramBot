"""Point Telegram at your deployment (includes the secret token, if you set one).

    python scripts/set_webhook.py https://your-project.vercel.app
    python scripts/set_webhook.py --info
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from meera.config import env, load_dotenv  # noqa: E402

load_dotenv()

from meera import telegram  # noqa: E402

if len(sys.argv) != 2:
    sys.exit(__doc__)

if sys.argv[1] == "--info":
    print(telegram.call("getWebhookInfo"))
else:
    params = {
        "url": sys.argv[1].rstrip("/") + "/api/webhook",
        "allowed_updates": ["message", "channel_post"],
        "drop_pending_updates": True,
    }
    if env("TELEGRAM_WEBHOOK_SECRET"):
        params["secret_token"] = env("TELEGRAM_WEBHOOK_SECRET")
    print(telegram.call("setWebhook", **params))
    print(telegram.call("getWebhookInfo"))
