# 🔐 Auth Setup — Manual Steps

> Everything the code can't do for you: Supabase dashboard configuration, Google OAuth
> credentials, and deployment environment variables. Total time: ~25 minutes.
>
> **What was built (already coded, nothing to do):** Supabase Auth on the frontend
> (email/password + **Continue with Google**), JWT verification in FastAPI, user
> profiles with dashboard defaults, saved searches, resume-analysis history, an
> Account page, and sign-in UI in the header. Works fully in local dev already —
> these steps activate it in Supabase and production.

---

## Step 1 — Run the database migrations ✅ required

Supabase dashboard → **SQL Editor** → paste & run, in order:

1. [`database/migrations/001_multi_source_ingestion.sql`](database/migrations/001_multi_source_ingestion.sql) *(scraping bots — skip if already run)*
2. [`database/migrations/002_auth_personalization.sql`](database/migrations/002_auth_personalization.sql)

Both are idempotent (safe to re-run). Migration 002 creates `user_profiles` (auto-filled
by a signup trigger), `saved_searches`, adds `user_id` to `resume_uploads`, and enables
Row-Level Security. **Both migrations have been dry-run-validated against your live
database** — they apply cleanly.

Verify:
```sql
SELECT tablename, rowsecurity FROM pg_tables
WHERE schemaname = 'public' AND tablename IN ('user_profiles','saved_searches');
```

## Step 2 — Configure Auth URLs in Supabase ✅ required

Supabase dashboard → **Authentication → URL Configuration**:

| Setting | Value |
|---------|-------|
| **Site URL** | `https://jobscript.vercel.app` |
| **Redirect URLs** (add all) | `https://jobscript.vercel.app/**` and `http://localhost:5173/**` |

The Email provider is enabled by default. Optional: under **Authentication →
Sign In / Providers → Email**, decide whether to keep **"Confirm email"** on
(users must click an email link before first sign-in) — the UI handles both modes.

## Step 3 — Enable "Continue with Google" ✅ required for Google sign-in

**3a. Google Cloud Console** (https://console.cloud.google.com/):

1. Create/select a project → **APIs & Services → OAuth consent screen**
   - User type **External** → fill app name ("Job Script"), support email → Save.
2. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   - Application type: **Web application**
   - **Authorized JavaScript origins**: `https://jobscript.vercel.app` and `http://localhost:5173`
   - **Authorized redirect URIs**: `https://jyxwmracnxszcqrnfbun.supabase.co/auth/v1/callback`
     *(your Supabase project ref — copy the exact callback URL shown in the Supabase Google provider screen)*
3. Copy the generated **Client ID** and **Client Secret**.

**3b. Supabase dashboard** → **Authentication → Sign In / Providers → Google**:

- Toggle **Enable**, paste the Client ID + Client Secret → Save.

> While the consent screen is in "Testing" mode, only test users you list can sign in.
> Click **Publish app** on the consent screen to open it to everyone.

## Step 4 — Backend environment variable 🔑 recommended

Get the JWT secret: Supabase → **Project Settings → API → JWT Settings → "JWT Secret"**
(on newer dashboards: Project Settings → **JWT Keys** → *Legacy JWT Secret*).

- **Locally** — `backend/.env` already has the placeholder; paste the value:
  ```
  SUPABASE_JWT_SECRET=your-jwt-secret-here
  ```
- **Render** — dashboard → your `skill-hunt-api` service → **Environment** → add
  `SUPABASE_JWT_SECRET` with the same value.

*If you skip this,* auth still works: the backend falls back to verifying tokens
against Supabase's Auth API using `SUPABASE_PROJECT_URL` + `SUPABASE_ANON_KEY`
(already present in your `.env` — make sure both are also set on Render).

Then reinstall backend deps once (adds `PyJWT`):
```bash
cd backend && pip install -r requirements.txt
```

## Step 5 — Frontend environment variables (Vercel) ✅ required for production

Local `frontend/.env` is **already configured**. For production, Vercel dashboard →
your project → **Settings → Environment Variables** → add both, then **redeploy**:

| Variable | Value |
|----------|-------|
| `VITE_SUPABASE_URL` | `https://jyxwmracnxszcqrnfbun.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | the `anon` public key (Project Settings → API) |

(The anon key is public by design — safe in the browser; RLS protects the data.)

## Step 6 — Test the flow 🚀

```bash
# terminal 1
cd backend && uvicorn app.main:app --reload --port 8000
# terminal 2
cd frontend && npm run dev
```

1. Open http://localhost:5173 → click **Sign in** (top-right).
2. Create an email/password account **and** try **Continue with Google**.
3. After sign-in you land on **My Account**: set a display name + default role/country → Save.
4. Pick a role/country in the sidebar → click the **bookmark** icon in the top bar → the search appears under Saved Searches (use **Apply** to restore it).
5. Run a resume analysis on the Resume Analyzer page → it appears under **Resume Analysis History**.
6. Reload the page → still signed in (session persists); your default filters are pre-applied.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Sign-in page says "not configured" | `VITE_SUPABASE_*` vars missing at **build** time — set them and rebuild/redeploy (Vite bakes env vars into the bundle). |
| Google button → `redirect_uri_mismatch` | The Supabase callback URL in Google Cloud doesn't match exactly — copy it verbatim from the Supabase Google provider screen. |
| Google works locally but prod redirects to localhost | Site URL / Redirect URLs (Step 2) don't include your Vercel domain. |
| API returns 401 with a fresh login | Backend can't verify the token — set `SUPABASE_JWT_SECRET` (or `SUPABASE_PROJECT_URL`+`SUPABASE_ANON_KEY`) on Render and redeploy. |
| API returns 503 "Auth is not configured" | Same as above — no verification method configured on the backend. |
| `relation "user_profiles" does not exist` | Run migration 002 (Step 1). |
| Signed in, but analyses don't appear in history | The analysis ran before you signed in, or the backend env vars weren't set when it ran. |

## What's next (not yet built)

- **Email alerts** ("notify me when demand for X changes") — needs an email provider
  (e.g. Resend free tier) + a scheduled job; the saved-searches table is already the
  natural subscription list.
- Per-user rate limiting using the verified user id.

---
**Last Updated:** July 2026
