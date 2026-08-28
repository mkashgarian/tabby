---
name: tabby
description: Splits a photographed/scanned receipt into a user's YNAB (You Need A Budget) categories, itemized and reconciled to the exact amount paid. Trigger this whenever the user uploads or mentions a receipt and wants it categorized, split, broken down, or entered for YNAB or budgeting purposes -- e.g. "split this receipt", "categorize this Target receipt for YNAB", "how should I budget this", or any photo of a receipt paired with a request to break down spending. Handles per-item discounts and proportional sales tax splitting. Always asks the user rather than guessing when an item's category is unclear.
---

# Receipt to YNAB Category Splitter

Turns one receipt into an itemized, per-YNAB-category breakdown that sums
exactly to the amount paid -- ready to enter into YNAB as a split
transaction.

## Overview of the workflow

1. Get the user's YNAB categories (live from the API if possible, else ask).
2. Get the receipt (image) and the store name.
3. Extract every line item: name, price, discount, quantity.
4. Reconcile the receipt math before doing anything else.
5. Assign each item to a YNAB category. Ask about anything ambiguous --
   never guess silently.
6. Run `scripts/calculate_split.py` to compute the proportional tax split
   and final category totals (don't hand-calculate the money math).
7. Present the itemized list + category totals to the user.
8. Optionally enter it into YNAB via `scripts/create_ynab_transaction.py`,
   dry-run first (only with explicit confirmation -- this writes financial
   data to their account).

## Step 1: Get YNAB categories

Try the live API first:

```bash
export YNAB_TOKEN="<user's personal access token>"
python3 scripts/fetch_ynab_categories.py            # first call: lists budgets
python3 scripts/fetch_ynab_categories.py <budget_id> # then: fetches + caches categories
```

- If the user hasn't given you a token yet, ask for it and tell them where
  to get one: YNAB web app -> Account Settings -> Developer Settings -> New
  Token. Treat the token as a secret: don't print it back, don't put it
  anywhere but the environment variable for this call.
- If this environment's network doesn't allow reaching `api.ynab.com`
  (common in claude.ai's default sandbox -- you'll see a connection/allowlist
  error), tell the user plainly that live lookup isn't available here, and
  ask them to paste their category list instead. Don't retry silently more
  than once.
- If `~/.cache/ynab_categories.json` already exists from a prior run in this
  environment, read it instead of re-fetching, unless the user says their
  categories changed or it's more than a few weeks old (check `fetched_at`).
- Once you have the category list (from API or pasted), that's the *only*
  set of categories you assign items to. Don't invent categories that
  aren't in the list.
- If you'll be entering the transaction in Step 8, also fetch accounts the
  same way, so you have an `account_id` to post against later:

  ```bash
  python3 scripts/fetch_ynab_accounts.py <budget_id>
  ```

  Same caching/network-fallback rules apply (`~/.cache/ynab_accounts.json`).

## Step 2: Get the receipt and store

- Read the receipt image directly (it's an uploaded image, so just look at
  it -- no OCR tooling needed unless it's genuinely illegible, in which case
  say so and ask for a clearer photo).
- Confirm which store it's from if not obvious from the receipt header. The
  user has said they'll tell you the store when needed -- use that to look
  up unfamiliar item codes (see Step 3).

## Step 3: Extract line items

For each line, capture:
- Item name (as printed; expand cryptic abbreviations when you can)
- Price (pre-discount)
- Discount, if the receipt shows one applied to that line (e.g. a markdown,
  coupon, loyalty discount, "you saved $X" line tied to a specific item)
- Quantity, if more than 1

**Cryptic item names:** grocery and big-box receipts often abbreviate items
(e.g. "GV FRZ VEG"). If a name isn't decipherable, web search
`"<store name> receipt abbreviation <code>"` or the store's product listing
to identify it. If you still can't tell what it is, ask the user rather than
guessing the category.

**Receipt-level (not line-level) discounts:** if a discount or coupon
applies to the whole receipt rather than one item (e.g. "$5 off your
purchase"), always ask the user how to allocate it before proceeding --
don't default to prorating it automatically.

**Non-item lines:** ignore lines like loyalty point summaries, "you saved"
totals (unless it's the only place a discount amount is stated), and
payment method footers. Do capture the tax line and the total paid.

## Step 4: Reconcile before categorizing

Before assigning categories, check: `sum(item prices) - sum(discounts) + tax
== total paid` (within a cent for rounding). If it doesn't reconcile:
- Look for a line item or fee you may have missed (bag fee, bottle deposit,
  tip, delivery fee).
- If you still can't make it balance, tell the user what doesn't add up and
  ask them to clarify rather than forcing the numbers to fit.

## Step 5: Assign categories

Go item by item and assign the closest YNAB category from the user's list.

- If an item obviously fits (e.g. "Bananas" -> Groceries), assign it
  directly.
- If an item could plausibly belong to more than one category, or doesn't
  clearly match anything on the list, **stop and ask the user** -- list the
  specific items you're unsure about and your best guesses, and let them
  choose. Don't silently pick one and move on.
- It's fine to batch these questions -- collect all the uncertain items from
  the whole receipt and ask about them together, rather than asking one at a
  time.

## Step 6: Calculate the split

Once every item has a category, hand the data to the script rather than
computing totals by hand -- it keeps everything in integer cents and
guarantees the category totals sum exactly to the total paid:

```bash
echo '{
  "store": "Target",
  "items": [
    {"name": "Bananas", "price": 1.99, "discount": 0.00, "category": "Groceries"},
    {"name": "Paper towels", "price": 6.49, "discount": 1.00, "category": "Household"}
  ],
  "tax": 0.62,
  "total_paid": 8.10
}' | python3 scripts/calculate_split.py
```

Notes on the script's behavior:
- Tax is split proportionally across categories based on each category's
  share of the post-discount, pre-tax subtotal (not equally per category,
  and not per item).
- `price` is the pre-discount line price; `discount` is the dollar amount
  taken off that line.
- If your inputs don't already balance to the exact total (rare rounding
  edge cases), the script nudges the last cent onto the largest category and
  flags `"input_balanced_without_adjustment": false` -- mention this to the
  user if it happens rather than silently smoothing it over.

## Step 7: Present the results

Show, in chat (this is a quick reference for the user, not a deliverable
file -- don't create a markdown/docx file for it unless they ask):

1. **Itemized list**: item, net price (after discount), category.
2. **Category totals**: each category's final dollar amount, including its
   share of tax.
3. Confirm the category totals sum to the receipt's total paid.

Keep this as plain, scannable text or a simple table -- no need for a
visualization tool for a short list like this.

## Step 8: Entering it into YNAB (optional, ask first)

Only do this if the user explicitly asks you to enter the transaction, not
automatically. Creating a transaction writes to their real budget, so:

- Confirm the payee, date, account, and the exact split before writing
  anything.
- You need `budget_id`, `account_id` (from Step 1), `payee_name`, and `date`
  in addition to the `category_totals` / `total_paid` that
  `calculate_split.py` already produced. Ask the user for any of these you
  don't already have (date defaults to today unless the receipt shows one).
- Always dry-run first and show the user the exact payload:

  ```bash
  echo '{
    "budget_id": "<budget id>",
    "account_id": "<account id>",
    "payee_name": "Target",
    "date": "2026-07-19",
    "category_totals": {"Groceries": 6.99, "Household": 5.99},
    "total_paid": 12.98
  }' | python3 scripts/create_ynab_transaction.py --dry-run
  ```

- The script resolves category names to `category_id` using the cache from
  Step 1 (`~/.cache/ynab_categories.json`) -- if a category name doesn't
  match, it will tell you rather than silently dropping it. Re-run
  `fetch_ynab_categories.py` if the cache is stale or missing ids.
- Read back the dry-run payload to the user in plain language (payee,
  date, account, per-category amounts, total) and get a clear go-ahead.
- Only then run it for real, same input, without `--dry-run`:

  ```bash
  echo '{ ... same JSON ... }' | python3 scripts/create_ynab_transaction.py
  ```

- If network access to `api.ynab.com` isn't available in this environment,
  say so and give the user the split so they can enter it manually instead.

## Edge cases worth remembering

- **Returns/refunds on the receipt**: treat as a negative-price line in
  whatever category the original item would be, unless the user says
  otherwise.
- **Multi-quantity lines** (e.g. "3 @ $2.00"): treat the line's total price
  as what gets discounted/categorized, not the per-unit price.
- **Split-category items** (e.g. a gift card that's actually two different
  things): ask the user how to divide that specific line rather than
  guessing.
- **Illegible or missing tax line**: ask the user for the receipt's tax
  amount or the state tax rate rather than assuming 0.
