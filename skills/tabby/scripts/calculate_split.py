#!/usr/bin/env python3
"""
calculate_split.py

Takes an itemized receipt (after discounts have been applied to each line
and each item has been assigned a YNAB category) and computes:
  - subtotal per category (post-discount, pre-tax)
  - each category's proportional share of sales tax
  - final per-category total
  - a reconciliation check against the receipt's stated total paid

Money is handled in integer cents throughout to avoid floating point drift.
Any leftover penny from rounding is assigned to the category with the
largest subtotal, so the category totals always sum EXACTLY to the total paid.

Input: JSON on stdin (or a file path as argv[1]) shaped like:

{
  "store": "Trader Joe's",
  "items": [
    {"name": "Bananas", "price": 1.99, "discount": 0.00, "category": "Groceries"},
    {"name": "Paper towels", "price": 6.49, "discount": 1.00, "category": "Household"}
  ],
  "tax": 0.62,
  "total_paid": 8.10
}

- "price" is the line price BEFORE any discount on that line.
- "discount" is the dollar amount knocked off that line (0 if none).
- "category" is the YNAB category name for that line. Use null/"" and the
  script will report it as "Uncategorized" so you can catch anything that
  slipped through without being assigned.

Optional rate-based tax: when a receipt taxes items at different rates
(e.g. groceries at a reduced food rate, marked by a tax code letter next to
each line), add a top-level "tax_rates" map and a "tax_code" on each item:

  "tax_rates": {"A": 0.075, "E": 0.02},
  "items": [{"name": "Butter", "price": 10.99, "tax_code": "E", ...}, ...]

Each category's tax is then based on its items' own rates instead of its
share of the subtotal. The per-category amounts are scaled so they still sum
exactly to the receipt's stated "tax"; "rate_based_tax_estimate" in the
output shows what the rates alone produce, so a large mismatch with the
receipt (wrong rates or codes) is easy to spot. Use a rate of 0 for untaxed
codes.

Output: JSON with category_totals, itemized breakdown, and a reconciled bool.
"""
import json
import sys
from collections import defaultdict


def to_cents(dollars):
    return round(dollars * 100)


def allocate(total_cents, weights):
    """Split total_cents across keys in proportion to weights (largest
    remainder), so the parts sum exactly to total_cents."""
    weight_sum = sum(weights.values())
    if not weight_sum:
        return {k: 0 for k in weights}
    exact = {k: total_cents * w / weight_sum for k, w in weights.items()}
    parts = {k: int(v // 1) for k, v in exact.items()}
    leftover = total_cents - sum(parts.values())
    for k in sorted(exact, key=lambda k: exact[k] - parts[k], reverse=True)[:leftover]:
        parts[k] += 1
    return parts


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    items = data["items"]
    tax_cents = to_cents(data["tax"])
    total_paid_cents = to_cents(data["total_paid"])

    # Net (post-discount) price per line, in cents
    for item in items:
        item["_net_cents"] = to_cents(item["price"]) - to_cents(item.get("discount", 0))
        item["_category"] = item.get("category") or "Uncategorized"

    subtotal_cents = sum(item["_net_cents"] for item in items)

    # Per-category subtotal (post-discount, pre-tax)
    cat_subtotal = defaultdict(int)
    for item in items:
        cat_subtotal[item["_category"]] += item["_net_cents"]

    cats_sorted = sorted(cat_subtotal.keys(), key=lambda c: -cat_subtotal[c])
    tax_rates = data.get("tax_rates")
    rate_based_estimate = None

    if tax_rates:
        # Rate-based tax split: weight each category by the tax its own
        # items would incur at their codes' rates.
        cat_rate_tax = defaultdict(float)
        for item in items:
            code = item.get("tax_code")
            if code not in tax_rates:
                print(f"Item '{item['name']}' has tax_code {code!r}, which isn't in "
                      f"tax_rates {sorted(tax_rates)}. Give every item a valid tax_code.")
                sys.exit(1)
            cat_rate_tax[item["_category"]] += item["_net_cents"] * tax_rates[code]
        for cat in cat_subtotal:
            cat_rate_tax.setdefault(cat, 0.0)
        rate_based_estimate = round(sum(cat_rate_tax.values())) / 100
        cat_tax = allocate(tax_cents, cat_rate_tax)
    else:
        # Proportional tax split per category, in cents, with remainder handling
        cat_tax = {}
        running_tax = 0
        for i, cat in enumerate(cats_sorted):
            if i == len(cats_sorted) - 1:
                # last category absorbs whatever tax remains (rounding safe)
                cat_tax[cat] = tax_cents - running_tax
            else:
                share = round(tax_cents * cat_subtotal[cat] / subtotal_cents) if subtotal_cents else 0
                cat_tax[cat] = share
                running_tax += share

    # Category totals = subtotal + tax share
    cat_total = {cat: cat_subtotal[cat] + cat_tax[cat] for cat in cat_subtotal}

    computed_total_cents = sum(cat_total.values())
    # Reconcile any last penny drift against stated total_paid to the
    # largest category, so output always matches the receipt exactly.
    drift = total_paid_cents - computed_total_cents
    reconciled = True
    if drift != 0:
        largest_cat = cats_sorted[0]
        cat_total[largest_cat] += drift
        reconciled = False  # flag that the input didn't already balance

    result = {
        "store": data.get("store"),
        "items": [
            {
                "name": it["name"],
                "price": it["price"],
                "discount": it.get("discount", 0),
                "net_price": round(it["_net_cents"] / 100, 2),
                "category": it["_category"],
                **({"tax_code": it.get("tax_code")} if tax_rates else {}),
            }
            for it in items
        ],
        "subtotal": round(subtotal_cents / 100, 2),
        "tax": round(tax_cents / 100, 2),
        "tax_method": "rate_based" if tax_rates else "proportional",
        **({"rate_based_tax_estimate": rate_based_estimate} if tax_rates else {}),
        "total_paid": round(total_paid_cents / 100, 2),
        "category_totals": {cat: round(v / 100, 2) for cat, v in cat_total.items()},
        "category_subtotals_pretax": {cat: round(v / 100, 2) for cat, v in cat_subtotal.items()},
        "category_tax_share": {cat: round(v / 100, 2) for cat, v in cat_tax.items()},
        "sum_of_category_totals": round(sum(cat_total.values()) / 100, 2),
        "input_balanced_without_adjustment": reconciled,
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
