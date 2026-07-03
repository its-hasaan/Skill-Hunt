/**
 * Login / Sign-up page — Supabase Auth.
 * Email + password, plus "Continue with Google" (OAuth).
 */
import { useState } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
import { LogIn, Mail, Lock, UserPlus, AlertCircle, CheckCircle2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { Spinner } from '../components/ui'

function GoogleIcon({ className = 'h-5 w-5' }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.1c-.22-.66-.35-1.36-.35-2.1s.13-1.44.35-2.1V7.06H2.18A10.97 10.97 0 0 0 1 12c0 1.77.43 3.45 1.18 4.94l3.66-2.84z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
    </svg>
  )
}

export default function LoginPage() {
  const { user, loading, isAuthEnabled, signIn, signUp, signInWithGoogle } = useAuth()
  const navigate = useNavigate()

  const [mode, setMode] = useState('signin') // 'signin' | 'signup'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)

  // Already signed in → straight to the account dashboard
  if (!loading && user) return <Navigate to="/account" replace />

  if (!isAuthEnabled) {
    return (
      <div className="max-w-md mx-auto card text-center">
        <AlertCircle className="h-10 w-10 mx-auto text-amber-500 mb-3" />
        <h2 className="card-header mb-2">Sign-in is not configured</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Set <code>VITE_SUPABASE_URL</code> and <code>VITE_SUPABASE_ANON_KEY</code> in the
          frontend environment, then rebuild. See <code>AUTH_SETUP.md</code>.
        </p>
      </div>
    )
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setNotice('')
    setBusy(true)
    try {
      if (mode === 'signin') {
        await signIn(email, password)
        navigate('/account')
      } else {
        const { needsConfirmation } = await signUp(email, password)
        if (needsConfirmation) {
          setNotice('Account created — check your email for a confirmation link, then sign in.')
          setMode('signin')
        } else {
          navigate('/account')
        }
      }
    } catch (err) {
      setError(err.message || 'Authentication failed')
    } finally {
      setBusy(false)
    }
  }

  const handleGoogle = async () => {
    setError('')
    try {
      await signInWithGoogle() // redirects away; errors only happen pre-redirect
    } catch (err) {
      setError(err.message || 'Google sign-in failed')
    }
  }

  return (
    <div className="max-w-md mx-auto">
      <div className="card">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center h-12 w-12 rounded-xl bg-primary-50 dark:bg-primary-900/30 mb-3">
            {mode === 'signin'
              ? <LogIn className="h-6 w-6 text-primary-600 dark:text-primary-400" />
              : <UserPlus className="h-6 w-6 text-primary-600 dark:text-primary-400" />}
          </div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
            {mode === 'signin' ? 'Welcome back' : 'Create your account'}
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Saved searches, resume history, and personalized defaults
          </p>
        </div>

        {/* Continue with Google */}
        <button
          type="button"
          onClick={handleGoogle}
          className="w-full flex items-center justify-center gap-3 px-4 py-2.5 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-600 transition-colors"
        >
          <GoogleIcon />
          Continue with Google
        </button>

        <div className="flex items-center gap-3 my-5">
          <div className="flex-1 h-px bg-gray-200 dark:bg-gray-700" />
          <span className="text-xs text-gray-400 uppercase">or</span>
          <div className="flex-1 h-px bg-gray-200 dark:bg-gray-700" />
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
              Email
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="select-input pl-9"
                autoComplete="email"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
              Password
            </label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="select-input pl-9"
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
              />
            </div>
          </div>

          {error && (
            <div className="flex items-start gap-2 text-sm text-red-600 dark:text-red-400">
              <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {notice && (
            <div className="flex items-start gap-2 text-sm text-green-600 dark:text-green-400">
              <CheckCircle2 className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>{notice}</span>
            </div>
          )}

          <button type="submit" disabled={busy} className="btn-primary w-full flex items-center justify-center gap-2">
            {busy && <Spinner size="sm" />}
            {mode === 'signin' ? 'Sign in' : 'Sign up'}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500 dark:text-gray-400 mt-5">
          {mode === 'signin' ? (
            <>Don&apos;t have an account?{' '}
              <button className="text-primary-600 dark:text-primary-400 font-medium hover:underline" onClick={() => { setMode('signup'); setError('') }}>
                Sign up
              </button>
            </>
          ) : (
            <>Already have an account?{' '}
              <button className="text-primary-600 dark:text-primary-400 font-medium hover:underline" onClick={() => { setMode('signin'); setError('') }}>
                Sign in
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  )
}
