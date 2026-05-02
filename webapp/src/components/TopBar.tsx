import { Bell, BookOpen, ChevronDown, LogOut, MessageSquare, PanelLeft, Sparkles, User as UserIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthProvider'
import { cn } from '../lib/utils'

const ROUTE_TITLES: Array<[string, string]> = [
  ['/home', 'Home'],
  ['/studio', 'Studio'],
  ['/library', 'Library'],
  ['/translate', 'Translate'],
  ['/settings', 'Settings'],
  ['/admin', 'Admin'],
]

function titleFor(pathname: string): string {
  if (pathname.startsWith('/library/')) return 'Post detail'
  for (const [prefix, label] of ROUTE_TITLES) {
    if (pathname.startsWith(prefix)) return label
  }
  return ''
}

export function TopBar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const title = titleFor(location.pathname)
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  const initial = user?.username[0]?.toUpperCase() ?? '?'
  const isAdmin = user?.role === 'admin'

  return (
    <header className="h-14 sticky top-0 z-10 bg-bg-base/85 backdrop-blur border-b border-line-subtle flex items-center justify-between px-6">
      <div className="flex items-center gap-3 min-w-0">
        <button type="button" className="btn-ghost p-2" title="Toggle sidebar">
          <PanelLeft className="w-4 h-4" />
        </button>
        <h1 className="text-base font-semibold text-ink-1 truncate">{title}</h1>
      </div>

      <div className="flex items-center gap-1">
        <a
          href="https://github.com/anthropics/claude-code"
          target="_blank"
          rel="noreferrer"
          className="btn-secondary !py-1.5 !px-3 text-xs"
        >
          <MessageSquare className="w-3.5 h-3.5" />
          Feedback
        </a>
        <a
          href="/api/docs"
          target="_blank"
          rel="noreferrer"
          className="btn-secondary !py-1.5 !px-3 text-xs"
        >
          <BookOpen className="w-3.5 h-3.5" />
          API Docs
        </a>
        <button type="button" className="btn-ghost p-2" title="Tips">
          <Sparkles className="w-4 h-4" />
        </button>
        <button type="button" className="btn-ghost p-2 relative" title="Notifications">
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-2 w-1.5 h-1.5 rounded-full bg-rose-500" />
        </button>
        <div className="relative ml-1" ref={menuRef}>
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            className="flex items-center gap-1.5 pl-1 pr-2 py-1 rounded-full hover:bg-bg-elevated transition"
          >
            <span className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-400 to-fuchsia-500 grid place-items-center text-white text-[11px] font-bold">
              {initial}
            </span>
            <ChevronDown className={cn('w-3 h-3 text-ink-3 transition', menuOpen && 'rotate-180')} />
          </button>
          {menuOpen && (
            <div className="absolute right-0 mt-2 w-56 card overflow-hidden animate-fade-in">
              <div className="px-4 py-3 border-b border-line-subtle">
                <div className="flex items-center gap-2 mb-1">
                  <UserIcon className="w-3.5 h-3.5 text-ink-3" />
                  <span className="text-sm font-semibold text-ink-1 truncate">
                    {user?.username || 'guest'}
                  </span>
                </div>
                <span
                  className={cn(
                    'pill text-[10px] border',
                    isAdmin
                      ? 'bg-amber-50 text-amber-800 border-amber-200'
                      : 'bg-zinc-100 text-zinc-700 border-zinc-200',
                  )}
                >
                  {isAdmin ? 'admin' : 'user'}
                </span>
              </div>
              <button
                type="button"
                onClick={handleLogout}
                className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-ink-2 hover:bg-bg-elevated transition"
              >
                <LogOut className="w-4 h-4" />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
