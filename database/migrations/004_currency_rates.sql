-- ============================================================
-- MIGRATION 004 — Currency Rates (dynamic salary normalization)
-- ============================================================
-- Root cause fixed by this migration + etl/fetch_currency_rates.py:
--
-- Every mart groups salary by (search_role, country_code), which is
-- currency-safe WITHIN one row (one country -> one currency). But when
-- the API aggregates ACROSS countries (the default "All Countries" view),
-- it averaged the native-currency numbers directly — e.g. an Indian salary
-- of INR 2,500,000-3,600,000 (a normal ~$30-43k USD role) got averaged
-- against a US salary of USD 130,000 as if they were the same unit,
-- inflating skills like "ETL" and "Claude" to a reported ~$700-800k.
--
-- Fix: a small, PERIODICALLY REFRESHED (dynamic, not hardcoded) table of
-- currency -> USD rates, fetched live from a free FX API. dbt joins this
-- table to add *_usd columns to every salary figure; the backend uses the
-- _usd columns only when blending across countries, and keeps the native
-- currency figures unchanged for single-country queries (those were never
-- wrong — one country is already one currency).
--
-- Idempotent — safe to run repeatedly.
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS staging.currency_rates (
    currency_code TEXT PRIMARY KEY,     -- ISO 4217, e.g. 'GBP', 'INR'
    rate_to_usd   NUMERIC NOT NULL,      -- units of this currency per 1 USD
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source        TEXT DEFAULT 'frankfurter.dev'  -- where the rate came from
);

-- USD is always 1:1 with itself; seed it so USD-only setups work even
-- before the first fetch runs (never a "hardcoded rate" — it's definitional).
INSERT INTO staging.currency_rates (currency_code, rate_to_usd, source)
VALUES ('USD', 1.0, 'definitional')
ON CONFLICT (currency_code) DO NOTHING;

COMMIT;

-- ------------------------------------------------------------
-- Populate real rates:
--   cd etl && python fetch_currency_rates.py
-- Verify:
--   SELECT * FROM staging.currency_rates ORDER BY currency_code;
-- ------------------------------------------------------------
