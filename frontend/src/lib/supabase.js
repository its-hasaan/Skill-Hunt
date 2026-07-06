/**
 * Supabase client (auth only — data still flows through the FastAPI backend).
 *
 * Needs two env vars (see .env.example / AUTH_SETUP.md):
 *   VITE_SUPABASE_URL       e.g. https://xxxx.supabase.co
 *   VITE_SUPABASE_ANON_KEY  the public "anon" key
 *
 * If they are missing, `supabase` is null and the app runs in
 * anonymous-only mode (sign-in UI shows a setup hint instead of crashing).
 */
import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase = url && anonKey
  ? createClient(url, anonKey, {
      auth: {
        persistSession: true,       // session survives reloads (localStorage)
        autoRefreshToken: true,     // silent refresh before expiry
        detectSessionInUrl: true,   // completes the Google OAuth redirect
      },
    })
  : null

export const isAuthEnabled = Boolean(supabase)

/** Current access token, or null. Used by the API client. */
export async function getAccessToken() {
  if (!supabase) return null
  const { data } = await supabase.auth.getSession()
  return data?.session?.access_token || null
}
