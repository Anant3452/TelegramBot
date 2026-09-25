"""Environment config. Read lazily so a local .env loader can run first."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def env(name, default=None):
    value = os.environ.get(name, "").strip()
    return value or default


def load_dotenv(path=ROOT / ".env"):
    """Minimal .env loader for local runs (Vercel injects env vars itself)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# Score at or above this gets drafted. Below it, Meera gets a one-line reason.
SCORE_THRESHOLD = 6
