"""
Tiny stdlib .env loader shared by the other scripts in this directory.

Looks for a `.env` file (KEY=value per line, '#' comments allowed) starting
in the current working directory and walking up through this script's
directory and its parent, so it's found whether you run scripts from
the skill's own directory, its `scripts/` subdirectory, or elsewhere.

Values already set in the real environment are never overwritten -- an
`export YNAB_TOKEN=...` you've already done still wins over `.env`.
"""
import os


def load_dotenv():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(here, ".env"),
        os.path.join(os.path.dirname(here), ".env"),
    ]
    for path in candidates:
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
        return
