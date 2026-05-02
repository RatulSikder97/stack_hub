import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api, ApiError, type AuthUser } from '../lib/api'

interface AuthState {
  user: AuthUser | null
  status: 'loading' | 'guest' | 'authed'
  login: (username: string, password: string) => Promise<AuthUser>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [status, setStatus] = useState<'loading' | 'guest' | 'authed'>('loading')

  const refresh = useCallback(async () => {
    try {
      const me = await api.me()
      setUser(me)
      setStatus('authed')
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setUser(null)
        setStatus('guest')
      } else {
        // Network or unexpected — treat as guest so UI still renders.
        setUser(null)
        setStatus('guest')
      }
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const login = useCallback(async (username: string, password: string) => {
    const result = await api.login(username, password)
    setUser(result)
    setStatus('authed')
    return result
  }, [])

  const logout = useCallback(async () => {
    await api.logout().catch(() => undefined)
    setUser(null)
    setStatus('guest')
  }, [])

  const value = useMemo<AuthState>(
    () => ({ user, status, login, logout, refresh }),
    [user, status, login, logout, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
