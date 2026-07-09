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
# Fallback for currencies the ECB reference set does not publish (notably
# PKR — critical for the Pakistan job sources). open.er-api.com is free,
# keyless, and returns USD -> every ISO currency in one call.
FX_FALLBACK_URL = "https://open.er-api.com/v6/latest/USD"


def get_currencies_in_use(cur) -> set:
    """Which currencies actually appear in the data right now — dynamic,
    not a fixed list, so new sources/countries are picked up automatically."""
    cur.execute(
        "SELECT DISTINCT salary_currency FROM staging.stg_jobs WHERE salary_currency IS NOT NULL"
    )
    currencies = {r[0] for r in cur.fetchall() if r[0]}
    currencies.add("USD")  # always needed as the conversion target
    return currencies


def fetch_live_rates(currencies: set) -> tuple:
    """Query Frankfurter for USD -> each currency ('units of currency per
    1 USD', matching this project's convention). Currencies the ECB set
    doesn't publish (e.g. PKR) are filled from the fallback API.

    Returns (rates, sources): {currency: rate}, {currency: source_name}.
    ({}, {}) on total failure — caller keeps old cached rates."""
    wanted = currencies - {"USD"}
    if not wanted:
        return {"USD": 1.0}, {}
    try:
        resp = requests.get(FX_API_URL, params={"base": "USD", "to": ",".join(sorted(wanted))}, timeout=15)
        if resp.status_code != 200:
            logger.warning("FX API returned HTTP %s — trying fallback source", resp.status_code)
            fallback = _fetch_fallback_rates(wanted)
            if not fallback:
                return {}, {}
            fallback["USD"] = 1.0
            return fallback, {c: "open.er-api.com" for c in fallback}
        data = resp.json()
        rates = data.get("rates", {})
        rates["USD"] = 1.0
        sources = {}
        missing = wanted - set(rates.keys())
        if missing:
            # Primary source (ECB) doesn't publish every currency — e.g. PKR.
            # Try the fallback API for just the missing ones so those
            # countries' salaries still get USD-normalized.
            fallback = _fetch_fallback_rates(missing)
            rates.update(fallback)
            sources = {c: "open.er-api.com" for c in fallback}
            still_missing = missing - set(fallback.keys())
            if still_missing:
                logger.warning(
                    "No source returned rates for: %s (keeping cached values for these)",
                    sorted(still_missing),
                )
        return rates, sources
    except (requests.exceptions.RequestException, ValueError) as e:
        logger.warning("FX fetch failed (%s) — trying fallback source", e)
        fallback = _fetch_fallback_rates(wanted)
        if not fallback:
            return {}, {}
        fallback["USD"] = 1.0
        return fallback, {c: "open.er-api.com" for c in fallback}


def _fetch_fallback_rates(currencies: set) -> dict:
    """Fetch USD -> currency rates for `currencies` from the fallback API.
    Returns only the requested currencies; {} on any failure."""
    if not currencies:
        return {}
    try:
        resp = requests.get(FX_FALLBACK_URL, timeout=15)
        if resp.status_code != 200:
            logger.warning("Fallback FX API returned HTTP %s", resp.status_code)
            return {}
        data = resp.json()
        all_rates = data.get("rates", {})
        found = {c: float(all_rates[c]) for c in currencies if c in all_rates}
        if found:
            logger.info("Fallback FX source covered: %s", sorted(found.keys()))
        return found
    except (requests.exceptions.RequestException, ValueError, TypeError) as e:
        logger.warning("Fallback FX fetch failed (%s)", e)
        return {}


def upsert_rates(cur, rates: dict, sources: dict = None) -> int:
    sources = sources or {}
    n = 0
    for currency, rate in rates.items():
        cur.execute(
            """
            INSERT INTO staging.currency_rates (currency_code, rate_to_usd, fetched_at, source)
            VALUES (%s, %s, NOW(), %s)
            ON CONFLICT (currency_code) DO UPDATE SET
                rate_to_usd = EXCLUDED.rate_to_usd,
                fetched_at = EXCLUDED.fetched_at,
                source = EXCLUDED.source
            """,
            (currency, rate, sources.get(currency, "frankfurter.dev")),
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

        rates, sources = fetch_live_rates(currencies)
        if not rates:
            logger.warning("No fresh rates fetched this run — existing cached rates remain in effect")
            return

        logger.info("Fetched rates: %s", {k: round(v, 4) for k, v in sorted(rates.items())})

        if args.dry_run:
            logger.info("[dry-run] not writing to DB")
            return

        n = upsert_rates(cur, rates, sources)
        conn.commit()
        logger.info("Upserted %d currency rates into staging.currency_rates", n)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
