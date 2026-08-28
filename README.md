# Tabby

A Claude Code skill that splits a photographed receipt into your YNAB (You
Need A Budget) categories, itemized and reconciled to the exact amount paid.
Handles per-item discounts and proportional sales tax splitting.

## What it does

Give it a receipt photo and it will:

1. Extract every line item (name, price, discount, quantity).
2. Reconcile the receipt math before categorizing anything.
3. Pull categories directly from your YNAB budget (or use cached categories).
4. Assign each item to a YNAB category, looking up any vague line items and asking you about how to categorize anything ambiguous.
5. Compute the proportional tax split and final category totals.
6. Optionally create the split transaction directly in YNAB via the API. Searches for an existing transaction and creates one if not found.
   
## Setup

### Install the plugin (recommended)

Inside Claude Code:

```
/plugin marketplace add mkashgarian/tabby
/plugin install tabby@tabby
```

That's it -- no manual file copying, and `/plugin marketplace update tabby`
pulls future updates.

### Or install manually

1. Copy `skills/tabby/` into your Claude Code skills directory (e.g.
   `~/.claude/skills/`).

### Then, either way: set your YNAB token

1. Get a YNAB Personal Access Token: YNAB web app -> Account Settings ->
   Developer Settings -> New Token. Treat this like a password -- anyone
   with it can read and write your budget.
2. Give the scripts your token, either way works:
   - **`.env` file (recommended):** inside the installed `tabby` skill
     folder, copy `.env.example` to `.env` and fill in your token:
     ```bash
     cp .env.example .env
     ```
     then edit `.env` and set `YNAB_TOKEN=...`. The scripts load this
     automatically -- no shell config needed, and `.env` is already in
     `.gitignore` so it won't get committed.
   - **Shell environment variable:** `export YNAB_TOKEN="your-token"` in
     your `.zshrc`/`.bashrc` or before each session. An `export` you've
     already done always wins over `.env` if both are set.

### A note on network access

The scripts need outbound access to `api.ynab.com` to fetch categories,
accounts, and create transactions. Some sandboxed environments (including
claude.ai's default tool sandbox) block outbound network to hosts that
aren't allowlisted, which will make the API calls fail with a connection
error. If that happens, either allow `api.ynab.com` in that environment's
network settings, or just paste your category list into chat and enter the
split into YNAB manually -- the skill is designed to fall back to that.

See [skills/tabby/SKILL.md](skills/tabby/SKILL.md) for the full
workflow and script details.

## Scripts

- `scripts/fetch_ynab_categories.py` -- fetch and cache your budget's categories
- `scripts/fetch_ynab_accounts.py` -- fetch and cache your budget's accounts
- `scripts/calculate_split.py` -- compute the proportional tax/category split
- `scripts/create_ynab_transaction.py` -- create the split transaction in YNAB (dry-run supported)
