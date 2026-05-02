import { ArrowRight, Sparkles, ShieldCheck, Lock } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../components/AuthProvider'
import { Spinner } from '../components/Spinner'
import { ApiError } from '../lib/api'

export function LoginPage() {
  const { login, status } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // If already authenticated, bounce away.
  useEffect(() => {
    if (status === 'authed') {
      const from = (location.state as { from?: string } | null)?.from || '/home'
      navigate(from, { replace: true })
    }
  }, [status, location.state, navigate])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password) {
      setError('Username and password are required.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await login(username.trim(), password)
      const from = (location.state as { from?: string } | null)?.from || '/home'
      navigate(from, { replace: true })
    } catch (e) {
      if (e instanceof ApiError) setError(e.message)
      else setError('Login failed. Check your credentials.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left: form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-400 to-rose-500 grid place-items-center text-white font-bold">
              S
            </div>
            <div>
              <div className="text-base font-semibold text-ink-1">Stack Hub</div>
              <div className="text-xs text-ink-3">Studio</div>
            </div>
          </div>

          <h1 className="text-2xl font-semibold tracking-tight text-ink-1 mb-1">
            Sign in
          </h1>
          <p className="text-sm text-ink-3 mb-7">
            Use your admin or user credentials to continue.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div>
              <label
                htmlFor="username"
                className="block text-xs uppercase tracking-widest text-ink-3 font-semibold mb-1.5"
              >
                Username
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="input"
                placeholder="admin"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block text-xs uppercase tracking-widest text-ink-3 font-semibold mb-1.5"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input"
                placeholder="••••••"
              />
            </div>

            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="btn-primary w-full"
            >
              {submitting ? (
                <>
                  <Spinner /> Signing in…
                </>
              ) : (
                <>
                  Sign in
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-line-subtle text-xs text-ink-3 space-y-1">
            <p className="font-semibold text-ink-2">Default credentials</p>
            <p>
              <code className="font-mono">admin / admin</code> ·{' '}
              <code className="font-mono">user / user</code>
            </p>
            <p className="text-ink-4 mt-2">
              Change these in <code className="font-mono text-ink-3">.env</code>{' '}
              before exposing on a network.
            </p>
          </div>
        </div>
      </div>

      {/* Right: marketing card */}
      <div className="hidden lg:flex flex-1 bg-bg-sidebar border-l border-line-subtle items-center justify-center p-12">
        <div className="max-w-md">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-bg-elevated border border-line-subtle text-xs text-ink-2 mb-6">
            <Sparkles className="w-3 h-3 text-violet-500" />
            Voice-preserving content pipeline
          </div>
          <h2 className="text-3xl font-semibold tracking-tight text-ink-1 leading-tight mb-4">
            Speak in any language. Ship a Substack post that still sounds like you.
          </h2>
          <p className="text-sm text-ink-2 leading-relaxed">
            Stack Hub turns voice notes into briefs, briefs into drafts, and drafts
            into posts that pass an AI-tells detector before they reach your readers.
            Run it on your laptop. Keep your voice.
          </p>
          <div className="mt-8 grid grid-cols-1 gap-3 text-sm">
            <Feature icon={Lock} text="Localhost only · your data stays on your machine." />
            <Feature
              icon={ShieldCheck}
              text="Two roles: admin edits voice + prompts; user records and ships."
            />
          </div>
        </div>
      </div>
    </div>
  )
}

function Feature({
  icon: Icon,
  text,
}: {
  icon: React.ComponentType<{ className?: string }>
  text: string
}) {
  return (
    <div className="flex items-start gap-3">
      <span className="w-7 h-7 rounded-lg bg-bg-elevated border border-line-subtle grid place-items-center shrink-0 mt-0.5">
        <Icon className="w-3.5 h-3.5 text-ink-2" />
      </span>
      <span className="text-ink-2 leading-relaxed">{text}</span>
    </div>
  )
}
