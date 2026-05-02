import { NavLink } from 'react-router-dom'
import {
  Mic,
  Library,
  Languages,
  Settings as SettingsIcon,
  Activity,
  Sparkles,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { StatusInfo } from '../lib/types'
import { cn } from '../lib/utils'

const navItems = [
  { to: '/studio', label: 'Studio', icon: Mic },
  { to: '/library', label: 'Library', icon: Library },
  { to: '/translate', label: 'Translate', icon: Languages },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
]

export function Sidebar() {
  const [status, setStatus] = useState<StatusInfo | null>(null)
  useEffect(() => {
    api.status().then(setStatus).catch(() => undefined)
  }, [])

  const brand = status?.brand_name ?? 'Stack Hub'
  const initial = brand[0]?.toUpperCase() ?? 'S'

  return (
    <aside className="w-60 shrink-0 bg-bg-sidebar border-r border-line-subtle flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-line-subtle">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-brand grid place-items-center text-white font-bold shadow-glow">
            {initial}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold text-ink-1 truncate">{brand}</div>
            <div className="text-[10px] uppercase tracking-widest text-ink-4">Studio</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="px-3 mb-2 text-[10px] uppercase tracking-widest text-ink-4 font-semibold">
          Workspace
        </div>
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => cn('nav-item', isActive && 'active')}
          >
            <Icon className="w-4 h-4 shrink-0 text-ink-3" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Status footer */}
      <div className="px-3 py-3 border-t border-line-subtle">
        <div className="px-3 py-2.5 rounded-lg bg-bg-elevated/60 border border-line-subtle">
          <div className="flex items-center gap-2 mb-1.5">
            <Activity className="w-3.5 h-3.5 text-ink-3" />
            <span className="text-[10px] uppercase tracking-widest text-ink-3 font-semibold">
              Provider
            </span>
            <span
              className={cn(
                'ml-auto w-1.5 h-1.5 rounded-full',
                status?.has_active_provider_key ? 'bg-emerald-500' : 'bg-amber-500',
              )}
            />
          </div>
          <div className="font-mono text-xs text-ink-2 truncate">
            {status ? `${status.provider} / ${status.model}` : '…'}
          </div>
        </div>
        <a
          href="https://github.com/anthropics/claude-code"
          target="_blank"
          rel="noreferrer"
          className="mt-2 flex items-center gap-2 px-3 py-2 text-xs text-ink-4 hover:text-ink-2 transition"
        >
          <Sparkles className="w-3 h-3" />
          <span>Local · v1</span>
        </a>
      </div>
    </aside>
  )
}
