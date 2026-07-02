-- ============================================================
-- RESUME ANALYSIS STORAGE
-- Parent upload record + normalized detail tables.
-- Idempotent: safe to run multiple times (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).
-- ============================================================

-- ------------------------------------------------------------
-- Parent: one row per analysis run (gap analysis OR role match)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.resume_uploads (
    id               UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    filename         TEXT        NOT NULL,
    file_size        INTEGER,                         -- bytes
    analysis_type    TEXT,                            -- 'gap_analysis' | 'role_match'
    target_role      TEXT,                            -- role used / top matched role
    extracted_skills_count INTEGER DEFAULT 0,
    extracted_skills JSONB,                           -- snapshot: [{skill_name, category, mention_count}]
    match_score      FLOAT,                           -- 0-100 (gap %) or top role score
    storage_path     TEXT,                            -- path inside Supabase Storage bucket
    storage_url      TEXT,                            -- public download URL (if bucket is public)
    uploaded_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Added after the initial release: country the analysis was scoped to (NULL = global)
ALTER TABLE public.resume_uploads ADD COLUMN IF NOT EXISTS country TEXT;

-- Index for browsing uploads by date
CREATE INDEX IF NOT EXISTS idx_resume_uploads_uploaded_at
    ON public.resume_uploads (uploaded_at DESC);

-- ------------------------------------------------------------
-- Skills extracted from the resume text (both analysis types)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.resume_skills (
    id             BIGSERIAL PRIMARY KEY,
    resume_id      UUID NOT NULL REFERENCES public.resume_uploads(id) ON DELETE CASCADE,
    skill_name     TEXT NOT NULL,
    skill_category TEXT,
    mention_count  INTEGER DEFAULT 1,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resume_skills_resume
    ON public.resume_skills (resume_id);

-- ------------------------------------------------------------
-- Gap analysis detail: one row per market skill for the target
-- role, flagged as owned (has_skill = TRUE) or a gap (FALSE).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.resume_gap_analysis (
    id                BIGSERIAL PRIMARY KEY,
    resume_id         UUID NOT NULL REFERENCES public.resume_uploads(id) ON DELETE CASCADE,
    target_role       TEXT NOT NULL,
    country           TEXT,                           -- NULL = global aggregate
    skill_name        TEXT NOT NULL,
    skill_category    TEXT,
    has_skill         BOOLEAN NOT NULL,               -- TRUE = on resume, FALSE = missing/gap
    job_count         INTEGER,
    demand_percentage NUMERIC(6,2),
    avg_salary        NUMERIC,
    market_rank       INTEGER,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resume_gap_resume
    ON public.resume_gap_analysis (resume_id);
CREATE INDEX IF NOT EXISTS idx_resume_gap_role
    ON public.resume_gap_analysis (target_role);

-- ------------------------------------------------------------
-- Role match detail: one row per evaluated role (ranked).
-- Matched/missing skills kept as JSONB (top 5 each).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.resume_role_matches (
    id                     BIGSERIAL PRIMARY KEY,
    resume_id              UUID NOT NULL REFERENCES public.resume_uploads(id) ON DELETE CASCADE,
    country                TEXT,                       -- NULL = global aggregate
    role                   TEXT NOT NULL,
    match_score            NUMERIC(6,2),               -- 0-100
    matched_skills_count   INTEGER,
    total_skills_evaluated INTEGER,
    rank                   INTEGER,                    -- 1 = best fit
    top_matched_skills     JSONB,                      -- [{skill_name, category, job_count}]
    top_missing_skills     JSONB,
    created_at             TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resume_role_matches_resume
    ON public.resume_role_matches (resume_id);
CREATE INDEX IF NOT EXISTS idx_resume_role_matches_role
    ON public.resume_role_matches (role);
