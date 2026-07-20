#!/usr/bin/env python3
"""
create_ynab_transaction.py

Takes a category-split receipt (the JSON shape produced by
calculate_split.py, plus a few transaction-level fields) and creates a
single YNAB transaction with one subtransaction per category, via
POST /budgets/{budget_id}/transactions.

This WRITES to the user's real budget. Always run with --dry-run first,
show the user the exact payload, and only run for real after they
explicitly confirm.

Requires a YNAB Personal Access Token: YNAB Web App -> Account Settings ->
Developer Settings -> New Token.

Category names are resolved to category_ids using the cache written by
fetch_ynab_categories.py (~/.cache/ynab_categories.json). Run that script
first (for the same budget) if the cache is missing or stale.

Usage:
    export YNAB_TOKEN="your-personal-access-token"
    python3 create_ynab_transaction.py --dry-run < input.json
    python3 create_ynab_transaction.py < input.json

Input JSON on stdin (or a file path as argv[1], before any flags), shaped like:

{
  "budget_id": "<budget id>",
  "account_id": "<account id>",
  "payee_name": "Target",
  "date": "2026-07-19",
  "memo": "optional memo",
  "category_totals": {"Groceries": 12.34, "Household": 5.60},
  "total_paid": 17.94
}

("category_totals" and "total_paid" are exactly what calculate_split.py
outputs -- pipe that output through, adding the four transaction-level
fields above.)
"""
import json
import os
import sys
import urllib.request
import urllib.error

API_BASE = "https://api.ynab.com/v1"
CATEGORY_CACHE_PATH = os.path.expanduser("~/.cache/ynab_categories.json")


def to_milliunits(dollars):
    # Outflows are negative in YNAB. Round to nearest milliunit (dollars * 1000).
    return -round(dollars * 1000)


def load_category_ids(budget_id):
    if not os.path.exists(CATEGORY_CACHE_PATH):
        print(f"No category cache at {CATEGORY_CACHE_PATH}. "
              f"Run fetch_ynab_categories.py {budget_id} first.")
        sys.exit(1)

    with open(CATEGORY_CACHE_PATH) as f:
        cache = json.load(f)

    if cache.get("budget_id") != budget_id:
        print(f"Category cache is for budget {cache.get('budget_id')}, not {budget_id}. "
              f"Run fetch_ynab_categories.py {budget_id} to refresh it.")
        sys.exit(1)

    by_name = {}
    for c in cache["categories"]:
        if "id" not in c:
            print("Category cache doesn't include category ids -- it's from an older "
                  "version of fetch_ynab_categories.py. Re-run it to refresh the cache.")
            sys.exit(1)
        by_name[c["name"]] = c
    return by_name


def build_payload(data):
    budget_id = data["budget_id"]
    by_name = load_category_ids(budget_id)

    subtransactions = []
    for category_name, amount in data["category_totals"].items():
        match = by_name.get(category_name)
        if not match:
            print(f"Category '{category_name}' not found in cached categories for this budget. "
                  "Re-run fetch_ynab_categories.py, or fix the category name, and try again.")
            sys.exit(1)
        subtransactions.append({
            "amount": to_milliunits(amount),
            "category_id": match["id"],
            "memo": category_name,
        })

    transaction = {
        "account_id": data["account_id"],
        "date": data["date"],
        "amount": to_milliunits(data["total_paid"]),
        "payee_name": data.get("payee_name") or data.get("store"),
        "memo": data.get("memo", ""),
        "cleared": "uncleared",
        "approved": True,
        "subtransactions": subtransactions,
    }

    return budget_id, {"transaction": transaction}


def create_transaction(budget_id, payload, token):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{API_BASE}/budgets/{budget_id}/transactions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def main():
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry_run = "--dry-run" in sys.argv

    if args:
        with open(args[0]) as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    budget_id, payload = build_payload(data)

    if dry_run:
        print("DRY RUN -- nothing sent. This is the exact payload that would be POSTed:")
        print(json.dumps(payload, indent=2))
        return

    token = os.environ.get("YNAB_TOKEN")
    if not token:
        print("Set YNAB_TOKEN in your environment first (your YNAB Personal Access Token).")
        sys.exit(1)

    try:
        result = create_transaction(budget_id, payload, token)
    except urllib.error.URLError as e:
        print(f"Could not reach api.ynab.com ({e}).")
        sys.exit(1)
    except urllib.error.HTTPError as e:
        print(f"YNAB API error {e.code}: {e.read().decode(errors='replace')}")
        sys.exit(1)

    created = result["data"]["transaction"]
    print(f"Created transaction {created['id']}: {created['payee_name']} "
          f"on {created['date']} for {created['amount'] / 1000:.2f}")


if __name__ == "__main__":
    main()
