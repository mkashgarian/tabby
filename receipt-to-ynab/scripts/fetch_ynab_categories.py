#!/usr/bin/env python3
"""
fetch_ynab_categories.py

Fetches your YNAB budget's category groups and category names via the real
YNAB API (https://api.ynab.com/v1) and caches them locally so you don't have
to hit the API every single time you split a receipt.

Requires a YNAB Personal Access Token: YNAB Web App -> Account Settings ->
Developer Settings -> New Token.

NOTE ON NETWORK ACCESS: this script needs outbound network access to
api.ynab.com. Some sandboxed environments (including claude.ai's default
bash tool) restrict outbound network to an allowlist that does not include
api.ynab.com. If that's the case, this script will fail with a connection
error -- in that situation, just tell Claude your category list directly
(paste it in chat) instead of relying on this script. In Claude Code /
Desktop / other environments where you control network egress settings,
add api.ynab.com to the allowlist and this will work normally.

Usage:
    export YNAB_TOKEN="your-personal-access-token"
    python3 fetch_ynab_categories.py                 # lists your budgets
    python3 fetch_ynab_categories.py <budget_id>      # fetches + caches categories

Cache is written to ~/.cache/ynab_categories.json with a timestamp, and
subsequent runs of the calling skill should prefer reading that cache over
re-fetching, unless you tell Claude your categories changed.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

API_BASE = "https://api.ynab.com/v1"
CACHE_PATH = os.path.expanduser("~/.cache/ynab_categories.json")


def api_get(path, token):
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def list_budgets(token):
    data = api_get("/budgets", token)
    budgets = data["data"]["budgets"]
    print("Your YNAB budgets:")
    for b in budgets:
        print(f"  {b['id']}  {b['name']}")
    print("\nRun again with a budget id to fetch + cache its categories.")


def fetch_categories(budget_id, token):
    data = api_get(f"/budgets/{budget_id}/categories", token)
    groups = data["data"]["category_groups"]

    categories = []
    for g in groups:
        if g.get("hidden") or g.get("deleted"):
            continue
        for c in g["categories"]:
            if c.get("hidden") or c.get("deleted"):
                continue
            categories.append({"id": c["id"], "group": g["name"], "name": c["name"]})

    cache = {
        "budget_id": budget_id,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "categories": categories,
    }
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)

    print(f"Cached {len(categories)} categories to {CACHE_PATH}\n")
    for c in categories:
        print(f"  [{c['group']}] {c['name']}")


def main():
    token = os.environ.get("YNAB_TOKEN")
    if not token:
        print("Set YNAB_TOKEN in your environment first (your YNAB Personal Access Token).")
        sys.exit(1)

    try:
        if len(sys.argv) > 1:
            fetch_categories(sys.argv[1], token)
        else:
            list_budgets(token)
    except urllib.error.URLError as e:
        print(f"Could not reach api.ynab.com ({e}).")
        print("This environment's network may not allow api.ynab.com. "
              "Paste your category list directly in chat instead.")
        sys.exit(1)
    except urllib.error.HTTPError as e:
        print(f"YNAB API error {e.code}: {e.read().decode(errors='replace')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
