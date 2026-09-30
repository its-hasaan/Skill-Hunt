-- ============================================================
-- MIGRATION 008 — Clear dead public resume URLs
-- ============================================================
-- The `resumes` bucket is private, so the public URLs stored in
-- resume_uploads.storage_url never worked (HTTP 400/403) and must not be
-- handed out. The API stops writing them (backend/app/storage.py); this
-- clears the old ones. storage_path remains the reference to the file.
-- Idempotent.
-- ============================================================
BEGIN;
UPDATE public.resume_uploads SET storage_url = NULL WHERE storage_url IS NOT NULL;
COMMIT;
