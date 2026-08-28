#!/usr/bin/env python3
"""
fetch_ynab_accounts.py

Fetches a YNAB budget's open accounts via the real YNAB API
(https://api.ynab.com/v1) and caches them locally, same pattern as
fetch_ynab_categories.py.

Requires a YNAB Personal Access Token: YNAB Web App -> Account Settings ->
Developer Settings -> New Token.

NOTE ON NETWORK ACCESS: this script needs outbound network access to
api.ynab.com. Some sandboxed environments restrict outbound network to an
allowlist that does not include api.ynab.com. If that's the case, this
script will fail with a connection error -- in that situation, ask the
user which account to use instead.

Usage:
    export YNAB_TOKEN="your-personal-access-token"   # or set it in a .env file
    python3 fetch_ynab_accounts.py <budget_id>

Cache is written to ~/.cache/ynab_accounts.json with a timestamp.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

from _env import load_dotenv

API_BASE = "https://api.ynab.com/v1"
CACHE_PATH = os.path.expanduser("~/.cache/ynab_accounts.json")


def api_get(path, token):
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def fetch_accounts(budget_id, token):
    data = api_get(f"/budgets/{budget_id}/accounts", token)
    all_accounts = data["data"]["accounts"]

    accounts = [
        {"id": a["id"], "name": a["name"], "type": a["type"], "on_budget": a["on_budget"]}
        for a in all_accounts
        if not a.get("closed") and not a.get("deleted")
    ]

    cache = {
        "budget_id": budget_id,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "accounts": accounts,
    }
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)

    print(f"Cached {len(accounts)} accounts to {CACHE_PATH}\n")
    for a in accounts:
        print(f"  {a['id']}  {a['name']} ({a['type']}, {'on' if a['on_budget'] else 'off'}-budget)")


def main():
    load_dotenv()
    token = os.environ.get("YNAB_TOKEN")
    if not token:
        print("Set YNAB_TOKEN in your environment first (your YNAB Personal Access Token).")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python3 fetch_ynab_accounts.py <budget_id>")
        sys.exit(1)

    try:
        fetch_accounts(sys.argv[1], token)
    except urllib.error.URLError as e:
        print(f"Could not reach api.ynab.com ({e}).")
        print("This environment's network may not allow api.ynab.com. "
              "Ask the user which account to use instead.")
        sys.exit(1)
    except urllib.error.HTTPError as e:
        print(f"YNAB API error {e.code}: {e.read().decode(errors='replace')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
