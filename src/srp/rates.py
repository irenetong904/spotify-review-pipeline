"""Editable, dated rates (cost/rates.csv). item_cost = billed_units x price_per_unit."""

import csv
from functools import lru_cache

from srp.paths import ROOT

RATES_PATH = ROOT / "cost" / "rates.csv"
USAGE_FIELDS = ("input_tokens", "cache_write_input_tokens", "cache_read_input_tokens", "output_tokens")


@lru_cache(maxsize=4)
def load_rates(path=RATES_PATH):
    with open(path, encoding="utf-8", newline="") as f:
        return {(r["model"], r["billing_item"]): float(r["price_usd_per_unit"]) for r in csv.DictReader(f)}


def call_cost(model, usage, rates=None):
    """usage: dict with mutually exclusive token categories. Missing usage -> None (unknown, never 0)."""
    rates = rates or load_rates()
    if usage.get("input_tokens") is None:
        return None
    total = 0.0
    for item in USAGE_FIELDS:
        units = usage.get(item) or 0
        if units:
            total += units * rates[(model, item)]
    return total
