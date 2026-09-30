-- ============================================================
-- MIGRATION 009 — Five new tracked roles (Phase 1a)
-- ============================================================
-- The platform grows from 15 to 20 roles. "Software Engineer" is the most
-- common title on company job boards and was previously dropped; the
-- others widen the audience (QA, design, product, support).
-- Idempotent.
-- ============================================================
BEGIN;

INSERT INTO staging.dim_job_roles (role_name, role_category) VALUES
    ('Software Engineer', 'Engineering'),
    ('QA Engineer', 'Engineering'),
    ('UI/UX Designer', 'Design'),
    ('Product Manager', 'Product'),
    ('Technical Support Engineer', 'Support')
ON CONFLICT (role_name) DO NOTHING;

COMMIT;
