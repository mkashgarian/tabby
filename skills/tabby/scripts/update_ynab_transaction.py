#!/usr/bin/env python3
"""
update_ynab_transaction.py

Splits a transaction that ALREADY exists in YNAB (e.g. imported from the
bank feed) into categories, instead of creating a duplicate with
create_ynab_transaction.py. Its date, payee, account and amount are left
alone; only the category is replaced by one subtransaction per category,
and the transaction is marked approved.

Two modes:

  --find     Read-only. Lists transactions in the account whose amount
             equals total_paid, within 3 days of "date". Use this to get
             the transaction_id to update.
  (default)  Updates "transaction_id" via
             PUT /budgets/{budget_id}/transactions/{transaction_id}.
             Run with --dry-run first, show the user the payload, and only
             run for real after they explicitly confirm.

YNAB can't change the subtransactions of a transaction that is already a
split, so this refuses to touch one; the user has to un-split it in YNAB
first (or delete it there and use create_ynab_transaction.py).

Usage:
    python3 update_ynab_transaction.py --find < input.json
    python3 update_ynab_transaction.py --dry-run < input.json
    python3 update_ynab_transaction.py < input.json

Input JSON is the same shape as create_ynab_transaction.py's, plus
"transaction_id" for the update modes (payee_name is ignored):

{
  "budget_id": "<budget id>",
  "account_id": "<account id>",
  "transaction_id": "<id from --find>",
  "date": "2026-10-04",
  "category_totals": {"Groceries": 12.34, "Household": 5.60},
  "total_paid": 17.94
}
"""
import datetime
import json
import os
import sys
import urllib.request
import urllib.error

from _env import load_dotenv
from create_ynab_transaction import API_BASE, build_subtransactions, to_milliunits

SEARCH_WINDOW_DAYS = 3


def api(token, path, method="GET", payload=None):
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)["data"]


def get_token():
    load_dotenv()
    token = os.environ.get("YNAB_TOKEN")
    if not token:
        print("Set YNAB_TOKEN in your environment first (your YNAB Personal Access Token).")
        sys.exit(1)
    return token


def find(data, token):
    date = datetime.date.fromisoformat(data["date"])
    since = date - datetime.timedelta(days=SEARCH_WINDOW_DAYS)
    until = date + datetime.timedelta(days=SEARCH_WINDOW_DAYS)
    amount = to_milliunits(data["total_paid"])

    txns = api(token, f"/budgets/{data['budget_id']}/accounts/{data['account_id']}"
                      f"/transactions?since_date={since.isoformat()}")["transactions"]
    matches = [t for t in txns
               if t["amount"] == amount and t["date"] <= until.isoformat()]
    if not matches:
        print(f"No transaction for {data['total_paid']:.2f} in this account between "
              f"{since} and {until}.")
        return
    for t in matches:
        split = f"split into {len(t['subtransactions'])}" if t["subtransactions"] else t["category_name"]
        print(f"{t['id']}  {t['date']}  {t['amount'] / 1000:.2f}  {t['payee_name']}  "
              f"[{split}]  {'approved' if t['approved'] else 'unapproved'}")


def build_update(data):
    subtransactions = build_subtransactions(data)
    return {"transaction": {
        "amount": to_milliunits(data["total_paid"]),
        "category_id": None,
        "approved": True,
        "subtransactions": subtransactions,
    }}


def check_existing(existing, data):
    if existing["amount"] != to_milliunits(data["total_paid"]):
        print(f"Transaction amount is {existing['amount'] / 1000:.2f}, but the receipt "
              f"total is -{data['total_paid']:.2f}. Not updating -- confirm with the user "
              "that this is the right transaction.")
        sys.exit(1)
    if existing["subtransactions"]:
        print("This transaction is already split, and YNAB's API can't change an existing "
              "split. Ask the user to un-split it in YNAB first, then retry.")
        sys.exit(1)


def main():
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if args:
        with open(args[0]) as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    try:
        if "--find" in flags:
            find(data, get_token())
            return

        payload = build_update(data)

        if "--dry-run" in flags:
            print("DRY RUN -- nothing sent. This is the exact payload that would be PUT "
                  f"to transaction {data['transaction_id']}:")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return

        token = get_token()
        path = f"/budgets/{data['budget_id']}/transactions/{data['transaction_id']}"
        check_existing(api(token, path)["transaction"], data)
        updated = api(token, path, method="PUT", payload=payload)["transaction"]
    except urllib.error.HTTPError as e:
        print(f"YNAB API error {e.code}: {e.read().decode(errors='replace')}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Could not reach api.ynab.com ({e}).")
        sys.exit(1)

    print(f"Updated transaction {updated['id']}: {updated['payee_name']} on "
          f"{updated['date']} for {updated['amount'] / 1000:.2f}")
    for s in updated["subtransactions"]:
        print(f"  {s['amount'] / 1000:.2f}  {s['category_name']}")


if __name__ == "__main__":
    main()
