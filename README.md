# Tabby

A Claude Code skill that splits a photographed receipt into your YNAB (You
Need A Budget) categories, itemized and reconciled to the exact amount paid.
Handles per-item discounts and proportional sales tax splitting.

## What it does

Give it a receipt photo and your YNAB category list, and it will:

1. Extract every line item (name, price, discount, quantity).
2. Reconcile the receipt math before categorizing anything.
3. Assign each item to a YNAB category, asking you about anything ambiguous.
4. Compute the proportional tax split and final category totals.
5. Optionally create the split transaction directly in YNAB via the API.

## Setup

1. Copy `receipt-to-ynab/` into your Claude Code skills directory (e.g.
   `~/.claude/skills/`).
2. Get a YNAB Personal Access Token: YNAB web app -> Account Settings ->
   Developer Settings -> New Token.
3. Export it before use: `export YNAB_TOKEN="your-token"`.

See [receipt-to-ynab/SKILL.md](receipt-to-ynab/SKILL.md) for the full
workflow and script details.

## Scripts

- `scripts/fetch_ynab_categories.py` -- fetch and cache your budget's categories
- `scripts/fetch_ynab_accounts.py` -- fetch and cache your budget's accounts
- `scripts/calculate_split.py` -- compute the proportional tax/category split
- `scripts/create_ynab_transaction.py` -- create the split transaction in YNAB (dry-run supported)
