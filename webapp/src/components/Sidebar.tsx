import { NavLink } from 'react-router-dom'
import {
  Home,
  Mic,
  Library,
  Languages,
  Settings as SettingsIcon,
  ChevronsUpDown,
  Plus,
  Send,
  Code2,
  Sparkles,
  ShieldCheck,
  Video,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useAuth } from './AuthProvider'
import { api } from '../lib/api'
import type { StatusInfo } from '../lib/types'
import { cn } from '../lib/utils'

interface NavSpec {
  to: string
  label: string
  icon: LucideIcon
}

const primaryNav: NavSpec[] = [
  { to: '/home', label: 'Home', icon: Home },
  { to: '/studio', label: 'Studio', icon: Mic },
  { to: '/meetings', label: 'Meetings', icon: Video },
  { to: '/library', label: 'Library', icon: Library },
  { to: '/translate', label: 'Translate', icon: Languages },
]

const pinnedNav: NavSpec[] = [
  { to: '/studio', label: 'Voice → Brief', icon: Mic },
  { to: '/meetings', label: 'Meeting → Brief', icon: Video },
  { to: '/translate', label: 'Quick translate', icon: Languages },
  { to: '/library', label: 'All posts', icon: Library },
]

export function Sidebar() {
  const [status, setStatus] = useState<StatusInfo | null>(null)
  const { user } = useAuth()
  useEffect(() => {
    api.status().then(setStatus).catch(() => undefined)
  }, [])

  const brand = status?.brand_name ?? 'Stack Hub'
  const initial = brand[0]?.toUpperCase() ?? 'S'
  const isAdmin = user?.role === 'admin'

  return (
    <aside className="w-60 shrink-0 bg-bg-sidebar border-r border-line-subtle flex flex-col h-screen sticky top-0">
      {/* Workspace switcher */}
      <div className="px-3 pt-3 pb-2">
        <button
          type="button"
          className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg hover:bg-bg-hover transition"
        >
          <div className="w-7 h-7 rounded-md bg-gradient-to-br from-orange-400 to-rose-500 grid place-items-center text-white text-xs font-bold shrink-0">
            {initial}
          </div>
          <span className="flex-1 text-left text-sm font-medium text-ink-1 truncate">
            {brand}
          </span>
          <ChevronsUpDown className="w-3.5 h-3.5 text-ink-3 shrink-0" />
        </button>
      </div>

      {/* Primary nav */}
      <nav className="px-2 space-y-0.5">
        {primaryNav.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === '/home'}
            className={({ isActive }) => cn('nav-item', isActive && 'active')}
          >
            <n.icon className="w-4 h-4 shrink-0" />
            <span>{n.label}</span>
            {n.label === 'Studio' && (
              <span className="ml-auto text-ink-4 hover:text-ink-1">
                <Plus className="w-3.5 h-3.5" />
              </span>
            )}
          </NavLink>
        ))}
        {isAdmin && (
          <NavLink
            to="/admin"
            className={({ isActive }) => cn('nav-item', isActive && 'active')}
          >
            <ShieldCheck className="w-4 h-4 shrink-0" />
            <span>Admin</span>
            <span className="ml-auto pill bg-amber-100 text-amber-800 border border-amber-200 text-[10px]">
              admin
            </span>
          </NavLink>
        )}
      </nav>

      {/* Pinned */}
      <div className="px-5 mt-6 mb-2 text-[11px] uppercase tracking-wider text-ink-3 font-semibold">
        Pinned
      </div>
      <nav className="px-2 space-y-0.5 flex-1 overflow-y-auto">
        {pinnedNav.map((n) => (
          <NavLink
            key={`${n.label}-${n.to}`}
            to={n.to}
            className={({ isActive }) => cn('nav-item', isActive && 'active')}
          >
            <n.icon className="w-4 h-4 shrink-0" />
            <span>{n.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Bottom card */}
      <div className="px-3 pb-3">
        <div className="card p-3.5 mb-3">
          <div className="flex items-start gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-bg-elevated border border-line-subtle grid place-items-center shrink-0 mt-0.5">
              <Send className="w-4 h-4 text-ink-2" />
            </div>
            <div className="min-w-0">
              <div className="text-xs font-semibold text-ink-1">Connect a real corpus</div>
              <div className="text-[11px] text-ink-3 mt-0.5 leading-snug">
                Drop authentic posts into <code className="font-mono text-[10px] text-ink-2">corpus/</code>
                {' '}and re-run extract_voice for production-grade output.
              </div>
            </div>
          </div>
        </div>

        <NavLink
          to="/settings"
          className={({ isActive }) => cn('nav-item w-full', isActive && 'active')}
        >
          <SettingsIcon className="w-4 h-4 shrink-0" />
          <span>Settings</span>
        </NavLink>
        <a
          href="/api/docs"
          target="_blank"
          rel="noreferrer"
          className="nav-item w-full"
        >
          <Code2 className="w-4 h-4 shrink-0" />
          <span>API docs</span>
        </a>

        <div className="mt-2 px-2 pt-2 border-t border-line-subtle">
          <div className="flex items-center gap-2 text-[11px] text-ink-3">
            <span
              className={cn(
                'w-1.5 h-1.5 rounded-full shrink-0',
                status?.has_active_provider_key ? 'bg-emerald-500' : 'bg-amber-500',
              )}
            />
            <span className="font-mono truncate">
              {status ? `${status.provider} / ${status.model}` : '…'}
            </span>
            <Sparkles className="w-3 h-3 text-ink-4 ml-auto shrink-0" />
          </div>
        </div>
      </div>
    </aside>
  )
}
