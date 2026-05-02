import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './AuthProvider'

export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') {
    return <FullPageMessage label="Loading…" />
  }
  if (status === 'guest') {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }
  return <Outlet />
}

export function RequireAdmin() {
  const { user, status } = useAuth()
  if (status === 'loading') return <FullPageMessage label="Loading…" />
  if (!user || user.role !== 'admin') return <Navigate to="/home" replace />
  return <Outlet />
}

function FullPageMessage({ label }: { label: string }) {
  return (
    <div className="min-h-screen grid place-items-center text-sm text-ink-3">
      {label}
    </div>
  )
}
