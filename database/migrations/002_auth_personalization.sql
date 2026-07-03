-- ============================================================
-- MIGRATION 002 — Auth & Personalization
-- ============================================================
-- Supabase Auth integration: user profiles, saved searches, and
-- linking resume analyses to accounts.
--
-- Idempotent — safe to run repeatedly. Run once in the Supabase
-- SQL editor (or: psql "$SUPABASE_URL" -f this-file).
--
-- Notes:
--  * auth.users is managed by Supabase Auth (email/password + Google
--    OAuth both land there). We never write to it directly.
--  * The FastAPI backend connects as the postgres role, which BYPASSES
--    RLS — the RLS policies below protect the tables from direct
--    PostgREST access with the public anon key.
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- 1. User profiles (1:1 with auth.users)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_profiles (
    id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email           TEXT,
    display_name    TEXT,
    avatar_url      TEXT,
    default_role    TEXT,           -- preferred dashboard role filter
    default_country TEXT,           -- preferred dashboard country filter
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-create a profile whenever a user signs up (email or Google).
-- SECURITY DEFINER so the auth-schema trigger may write to public.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public
AS $$
BEGIN
    INSERT INTO public.user_profiles (id, email, display_name, avatar_url)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name',
                 NEW.raw_user_meta_data->>'name',
                 split_part(NEW.email, '@', 1)),
        NEW.raw_user_meta_data->>'avatar_url'
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Backfill profiles for any users who signed up before this migration.
INSERT INTO public.user_profiles (id, email, display_name, avatar_url)
SELECT u.id, u.email,
       COALESCE(u.raw_user_meta_data->>'full_name',
                u.raw_user_meta_data->>'name',
                split_part(u.email, '@', 1)),
       u.raw_user_meta_data->>'avatar_url'
FROM auth.users u
ON CONFLICT (id) DO NOTHING;

-- ------------------------------------------------------------
-- 2. Saved searches
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.saved_searches (
    id         BIGSERIAL PRIMARY KEY,
    user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    role       TEXT NOT NULL,
    country    TEXT,               -- NULL = all countries
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT saved_searches_unique UNIQUE (user_id, role, country)
);

CREATE INDEX IF NOT EXISTS idx_saved_searches_user
    ON public.saved_searches (user_id, created_at DESC);

-- ------------------------------------------------------------
-- 3. Link resume analyses to accounts
-- ------------------------------------------------------------
-- NULL user_id = anonymous upload (feature keeps working logged-out).
ALTER TABLE public.resume_uploads
    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_resume_uploads_user
    ON public.resume_uploads (user_id, uploaded_at DESC);

-- ------------------------------------------------------------
-- 4. Row Level Security
-- ------------------------------------------------------------
-- Protects against direct PostgREST/anon-key access. The backend's
-- postgres connection bypasses RLS, so the API is unaffected.

ALTER TABLE public.user_profiles      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saved_searches     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resume_uploads     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resume_skills      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resume_gap_analysis  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resume_role_matches  ENABLE ROW LEVEL SECURITY;

-- user_profiles: users see/update only their own profile
DROP POLICY IF EXISTS user_profiles_select_own ON public.user_profiles;
CREATE POLICY user_profiles_select_own ON public.user_profiles
    FOR SELECT USING (auth.uid() = id);
DROP POLICY IF EXISTS user_profiles_update_own ON public.user_profiles;
CREATE POLICY user_profiles_update_own ON public.user_profiles
    FOR UPDATE USING (auth.uid() = id);

-- saved_searches: full CRUD on own rows
DROP POLICY IF EXISTS saved_searches_all_own ON public.saved_searches;
CREATE POLICY saved_searches_all_own ON public.saved_searches
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- resume_uploads: users see their own uploads
DROP POLICY IF EXISTS resume_uploads_select_own ON public.resume_uploads;
CREATE POLICY resume_uploads_select_own ON public.resume_uploads
    FOR SELECT USING (auth.uid() = user_id);

-- detail tables: visible when the parent upload is yours
DROP POLICY IF EXISTS resume_skills_select_own ON public.resume_skills;
CREATE POLICY resume_skills_select_own ON public.resume_skills
    FOR SELECT USING (EXISTS (
        SELECT 1 FROM public.resume_uploads r
        WHERE r.id = resume_id AND r.user_id = auth.uid()));

DROP POLICY IF EXISTS resume_gap_select_own ON public.resume_gap_analysis;
CREATE POLICY resume_gap_select_own ON public.resume_gap_analysis
    FOR SELECT USING (EXISTS (
        SELECT 1 FROM public.resume_uploads r
        WHERE r.id = resume_id AND r.user_id = auth.uid()));

DROP POLICY IF EXISTS resume_matches_select_own ON public.resume_role_matches;
CREATE POLICY resume_matches_select_own ON public.resume_role_matches
    FOR SELECT USING (EXISTS (
        SELECT 1 FROM public.resume_uploads r
        WHERE r.id = resume_id AND r.user_id = auth.uid()));

COMMIT;

-- ------------------------------------------------------------
-- Verify (optional):
--   SELECT * FROM public.user_profiles LIMIT 5;
--   SELECT tablename, rowsecurity FROM pg_tables
--   WHERE schemaname='public' AND tablename IN
--     ('user_profiles','saved_searches','resume_uploads');
-- ------------------------------------------------------------
