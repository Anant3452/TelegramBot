"""Run notes through the pipeline locally: no Telegram, no Supabase writes.

    python scripts/try_note.py samples/note_02.txt samples/weak_reminder.txt
    python scripts/try_note.py "some note text"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from meera.config import load_dotenv  # noqa: E402

load_dotenv()

from meera import pipeline  # noqa: E402


def main(args):
    if not args:
        sys.exit(__doc__)
    for arg in args:
        path = Path(arg)
        note = path.read_text().strip() if path.is_file() else arg
        print(f"\n{'=' * 70}\n{path.name if path.is_file() else 'note'}\n{'=' * 70}")
        result = pipeline.develop(note)
        if not result["passed"]:
            print(pipeline.format_rejection(result))
            continue
        print(f"[search: {result['search_phrase']!r} · drafted by {result['provider']}/{result['model']}]\n")
        print(pipeline.format_draft(result))


if __name__ == "__main__":
    main(sys.argv[1:])
