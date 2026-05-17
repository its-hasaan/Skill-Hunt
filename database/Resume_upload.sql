-- ============================================================
-- RESUME UPLOADS
-- ============================================================
CREATE TABLE IF NOT EXISTS public.resume_uploads (
    id               UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    filename         TEXT        NOT NULL,
    file_size        INTEGER,                         -- bytes
    analysis_type    TEXT,                            -- 'gap_analysis' | 'role_match'
    target_role      TEXT,                            -- role used / top matched role
    extracted_skills_count INTEGER DEFAULT 0,
    extracted_skills JSONB,                           -- [{skill_name, category, mention_count}]
    match_score      FLOAT,                           -- 0-100
    storage_path     TEXT,                            -- path inside Supabase Storage bucket
    storage_url      TEXT,                            -- public download URL (if bucket is public)
    uploaded_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index for browsing uploads by date
CREATE INDEX IF NOT EXISTS idx_resume_uploads_uploaded_at
    ON public.resume_uploads (uploaded_at DESC);
