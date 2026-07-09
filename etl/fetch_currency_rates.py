"""
Job Script — Currency Rate Fetcher
====================================
Fetches LIVE exchange rates and upserts them into `staging.currency_rates`,
so every salary figure can be converted to a common currency (USD) for
cross-country comparisons — dynamically, refreshed on every run, never a
hardcoded conversion table that drifts out of date.

Source: https://frankfurter.dev (ECB reference rates, free, no API key,
updated daily on ECB business days). Covers all currencies currently seen
in the data (AUD, BRL, CAD, EUR, GBP, INR, MXN, NZD, PLN, SGD, USD, ZAR).

Self-healing behavior: the set of currencies to fetch is read from the
DISTINCT `salary_currency` values actually present in `staging.stg_jobs` —
not a fixed list — so a new source/country's currency is picked up
automatically. If the API is unreachable or a currency isn't covered by it,
existing cached rates are left untouched (logged, not fatal) rather than
falling back to any hardcoded number: a stale-but-real rate is always
preferable to a made-up one, and downstream USD figures simply stay based
on whatever was last fetched successfully.

Usage:
    python fetch_currency_rates.py            # fetch + upsert
    python fetch_currency_rates.py --dry-run  # fetch + print, no DB write
"""

from __future__ import annotations

import os
import sys
import argparse
import logging
from pathlib import Path

import requests
import psycopg2
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("currency_rates.log")],
)
logger = logging.getLogger("fx")

load_dotenv(Path(__file__).parent / ".env")
DB_URL = os.getenv("SUPABASE_URL")
FX_API_URL = "https://api.frankfurter.dev/v1/latest"


def get_currencies_in_use(cur) -> set:
    """Which currencies actually appear in the data right now — dynamic,
    not a fixed list, so new sources/countries are picked up automatically."""
    cur.execute(
        "SELECT DISTINCT salary_currency FROM staging.stg_jobs WHERE salary_currency IS NOT NULL"
    )
    currencies = {r[0] for r in cur.fetchall() if r[0]}
    currencies.add("USD")  # always needed as the conversion target
    return currencies


def fetch_live_rates(currencies: set) -> dict:
    """Query Frankfurter for USD -> each currency, then invert to get
    'units of currency per 1 USD' (rate_to_usd), matching this project's
    convention. Returns {} on any failure (caller keeps old cached rates)."""
    wanted = currencies - {"USD"}
    if not wanted:
        return {"USD": 1.0}
    try:
        resp = requests.get(FX_API_URL, params={"base": "USD", "to": ",".join(sorted(wanted))}, timeout=15)
        if resp.status_code != 200:
            logger.warning("FX API returned HTTP %s — keeping cached rates", resp.status_code)
            return {}
        data = resp.json()
        rates = data.get("rates", {})
        rates["USD"] = 1.0
        missing = wanted - set(rates.keys())
        if missing:
            logger.warning("FX API did not return rates for: %s (keeping cached values for these)", sorted(missing))
        return rates
    except (requests.exceptions.RequestException, ValueError) as e:
        logger.warning("FX fetch failed (%s) — keeping cached rates", e)
        return {}


def upsert_rates(cur, rates: dict) -> int:
    n = 0
    for currency, rate in rates.items():
        cur.execute(
            """
            INSERT INTO staging.currency_rates (currency_code, rate_to_usd, fetched_at, source)
            VALUES (%s, %s, NOW(), 'frankfurter.dev')
            ON CONFLICT (currency_code) DO UPDATE SET
                rate_to_usd = EXCLUDED.rate_to_usd,
                fetched_at = EXCLUDED.fetched_at,
                source = EXCLUDED.source
            """,
            (currency, rate),
        )
        n += 1
    return n


def main():
    parser = argparse.ArgumentParser(description="Fetch live currency exchange rates for salary normalization")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print; do not write to DB")
    args = parser.parse_args()

    if not DB_URL:
        logger.error("SUPABASE_URL not set")
        sys.exit(1)

    conn = psycopg2.connect(DB_URL)
    try:
        cur = conn.cursor()
        currencies = get_currencies_in_use(cur)
        logger.info("Currencies in use: %s", sorted(currencies))

        rates = fetch_live_rates(currencies)
        if not rates:
            logger.warning("No fresh rates fetched this run — existing cached rates remain in effect")
            return

        logger.info("Fetched rates: %s", {k: round(v, 4) for k, v in sorted(rates.items())})

        if args.dry_run:
            logger.info("[dry-run] not writing to DB")
            return

        n = upsert_rates(cur, rates)
        conn.commit()
        logger.info("Upserted %d currency rates into staging.currency_rates", n)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
