-- ============================================================
-- MIGRATION 014 — Company career-page registry (Phase 1d)
-- ============================================================
-- One row per company site the career-page crawler reads
-- (etl/connectors/careerpage.py). status:
--   candidate  never crawled
--   jsonld     publishes schema.org JobPosting JSON-LD (crawled daily)
--   empty      no JobPostings and no hiring-system embed (retried weekly)
--   ats        embeds a Greenhouse/Lever/Ashby/SmartRecruiters/Workable board;
--              the board went to ops.companies and the site isn't scraped
--   blocked    robots.txt disallows the careers page (retried weekly)
-- fail_count: consecutive unreachable crawls (3 = given up).
-- Idempotent.
-- ============================================================
BEGIN;

CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS ops.career_sites (
    id              BIGSERIAL   PRIMARY KEY,
    domain          TEXT        NOT NULL UNIQUE,
    careers_url     TEXT,
    status          TEXT        NOT NULL DEFAULT 'candidate',
    ats             TEXT,
    board_token     TEXT,
    jobs_found      INTEGER,
    fail_count      INTEGER     NOT NULL DEFAULT 0,
    last_crawled_at TIMESTAMPTZ,
    etag            TEXT,
    last_modified   TEXT,
    discovered_via  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS career_sites_status_idx ON ops.career_sites (status, last_crawled_at);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON SCHEMA ops FROM anon, authenticated';
    END IF;
END $$;

COMMIT;
