"""Store voice-skill.txt in Supabase as the active voice skill (older versions are kept, marked inactive).

    python scripts/seed_voice_skill.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from meera.config import ROOT, load_dotenv  # noqa: E402

load_dotenv()

from meera import store  # noqa: E402

if not store.enabled():
    sys.exit("Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env first.")

store._req("PATCH", "voice_skill", params={"active": "eq.true"}, body={"active": False}, prefer="return=minimal")
row = store._one(store._req("POST", "voice_skill", body={"content": (ROOT / "voice-skill.txt").read_text()}))
print(f"Voice skill #{row['id']} is now active.")
