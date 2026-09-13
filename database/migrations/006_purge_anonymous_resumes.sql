-- ============================================================
-- MIGRATION 006 — Purge anonymous resume analyses
-- ============================================================
-- The API no longer stores anonymous resume analyses at all (see
-- backend/app/routers/resume.py). This removes the rows written before
-- that change.
--
-- Why these rows must go: every RLS policy on these tables keys on
-- `auth.uid() = user_id`. A row with user_id IS NULL matches no policy,
-- so nobody can read or delete it through Supabase — including the
-- person whose resume it is. They are unreachable personal data
-- (names, emails, phone numbers) with no deletion path.
--
-- ⚠️  DESTRUCTIVE AND IRREVERSIBLE. Read the counts first (step 1),
--     then run the delete (step 2).
--
-- Run in the Supabase SQL editor, or:
--   psql "$SUPABASE_URL" -f database/migrations/006_purge_anonymous_resumes.sql
-- ============================================================

-- ------------------------------------------------------------
-- STEP 1 — Inspect before deleting. Run this on its own first.
-- ------------------------------------------------------------
-- SELECT COUNT(*) AS anonymous_uploads,
--        MIN(uploaded_at) AS oldest,
--        MAX(uploaded_at) AS newest,
--        COUNT(storage_path) AS files_in_storage
-- FROM public.resume_uploads
-- WHERE user_id IS NULL;

-- Storage objects are NOT removed by this script. List the paths that
-- need deleting from the `resumes` bucket, then remove them in the
-- Supabase dashboard (Storage -> resumes) or via the storage API:
--
-- SELECT storage_path
-- FROM public.resume_uploads
-- WHERE user_id IS NULL AND storage_path IS NOT NULL
-- ORDER BY uploaded_at;

-- ------------------------------------------------------------
-- STEP 2 — Delete. Detail rows cascade from resume_uploads.
-- ------------------------------------------------------------
BEGIN;

DELETE FROM public.resume_uploads
WHERE user_id IS NULL;

COMMIT;

-- ------------------------------------------------------------
-- Verify: should return 0.
-- ------------------------------------------------------------
-- SELECT COUNT(*) FROM public.resume_uploads WHERE user_id IS NULL;
