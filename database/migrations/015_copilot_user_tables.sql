-- ============================================================
-- MIGRATION 015 — Web copilot user tables (Phase 2)
-- ============================================================
-- user_job_profiles  what the feed is matched against (≤ 3 target roles)
-- applications       the job tracker (saved → applied → interviewing → offer/rejected)
-- job_feedback       "not interested" (hidden from the feed)
-- digest_log         which jobs each email digest already sent
--
-- Everything cascades from auth.users, so deleting an account deletes its
-- rows. RLS: owner-only, against direct PostgREST/anon-key access; the API
-- connects as the service role and always filters by the verified user id.
-- Idempotent.
-- ============================================================
BEGIN;

CREATE TABLE IF NOT EXISTS public.user_job_profiles (
    user_id            UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    skills             TEXT[]      NOT NULL DEFAULT '{}',
    years_experience   NUMERIC(4,1),
    current_title      TEXT,
    education          TEXT,
    target_roles       TEXT[]      NOT NULL DEFAULT '{}',
    country            TEXT,
    timezone           TEXT,
    workplace_prefs    TEXT[]      NOT NULL DEFAULT '{remote}',
    min_salary_usd     INTEGER,
    show_unclear       BOOLEAN     NOT NULL DEFAULT FALSE,
    alert_frequency    TEXT        NOT NULL DEFAULT 'weekly',
    last_feed_visit_at TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT user_job_profiles_roles_max3 CHECK (cardinality(target_roles) <= 3),
    CONSTRAINT user_job_profiles_alerts CHECK (alert_frequency IN ('weekly', 'daily', 'off'))
);

CREATE TABLE IF NOT EXISTS public.applications (
    id           BIGSERIAL   PRIMARY KEY,
    user_id      UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    job_id       INTEGER,                       -- staging.stg_jobs.job_id; NULL for an external job
    title        TEXT        NOT NULL,
    company      TEXT,
    apply_url    TEXT,
    status       TEXT        NOT NULL DEFAULT 'saved',
    notes        TEXT,
    applied_at   TIMESTAMPTZ,
    follow_up_at DATE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT applications_status CHECK (status IN ('saved', 'applied', 'interviewing', 'offer', 'rejected')),
    CONSTRAINT applications_user_job_unique UNIQUE (user_id, job_id)
);
CREATE INDEX IF NOT EXISTS applications_user_status_idx ON public.applications (user_id, status);

CREATE TABLE IF NOT EXISTS public.job_feedback (
    user_id    UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    job_id     INTEGER     NOT NULL,
    kind       TEXT        NOT NULL DEFAULT 'not_interested',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, job_id)
);

CREATE TABLE IF NOT EXISTS public.digest_log (
    id      BIGSERIAL   PRIMARY KEY,
    user_id UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    job_ids INTEGER[]   NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS digest_log_user_idx ON public.digest_log (user_id, sent_at DESC);

ALTER TABLE public.user_job_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.applications      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_feedback      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.digest_log        ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_job_profiles_own ON public.user_job_profiles;
CREATE POLICY user_job_profiles_own ON public.user_job_profiles
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS applications_own ON public.applications;
CREATE POLICY applications_own ON public.applications
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS job_feedback_own ON public.job_feedback;
CREATE POLICY job_feedback_own ON public.job_feedback
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS digest_log_select_own ON public.digest_log;
CREATE POLICY digest_log_select_own ON public.digest_log
    FOR SELECT USING (auth.uid() = user_id);

COMMIT;
