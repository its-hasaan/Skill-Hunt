/**
 * Auth context — wraps Supabase Auth (email/password + Google OAuth).
 *
 * Exposes: { user, session, loading, isAuthEnabled,
 *            signIn, signUp, signInWithGoogle, signOut }
 *
 * `user` is the Supabase user object (id, email, user_metadata.avatar_url...).
 * When Supabase env vars are missing, everything is a safe no-op and
 * `isAuthEnabled` is false.
 */
import { createContext, useContext, useEffect, useState } from 'react'
import { supabase, isAuthEnabled } from '../lib/supabase'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(isAuthEnabled)

  useEffect(() => {
    if (!supabase) return

    supabase.auth.getSession().then(({ data }) => {
      setSession(data?.session ?? null)
      setLoading(false)
    })

    const { data: sub } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession)
      setLoading(false)
    })
    return () => sub?.subscription?.unsubscribe()
  }, [])

  const requireClient = () => {
    if (!supabase) throw new Error('Auth is not configured (missing VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY)')
    return supabase
  }

  const signIn = async (email, password) => {
    const { error } = await requireClient().auth.signInWithPassword({ email, password })
    if (error) throw error
  }

  const signUp = async (email, password) => {
    const { data, error } = await requireClient().auth.signUp({ email, password })
    if (error) throw error
    // When email confirmation is ON, no session is returned until confirmed.
    return { needsConfirmation: !data?.session }
  }

  const signInWithGoogle = async () => {
    const { error } = await requireClient().auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/account` },
    })
    if (error) throw error
  }

  const signOut = async () => {
    const { error } = await requireClient().auth.signOut()
    if (error) throw error
  }

  const value = {
    session,
    user: session?.user ?? null,
    loading,
    isAuthEnabled,
    signIn,
    signUp,
    signInWithGoogle,
    signOut,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
