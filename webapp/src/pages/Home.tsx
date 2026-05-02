import {
  Mic,
  Library as LibraryIcon,
  Languages,
  Wand2,
  Sparkles,
  ChevronRight,
  ArrowRight,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { StatusBadge } from '../components/Badge'
import { api } from '../lib/api'
import type { PostRecord, StatusInfo } from '../lib/types'
import { formatRelativeDate } from '../lib/utils'

interface Tile {
  to: string
  label: string
  hint: string
  icon: React.ComponentType<{ className?: string }>
  iconBg: string
  iconColor: string
}

const TILES: Tile[] = [
  {
    to: '/studio',
    label: 'Voice idea',
    hint: 'Speak your post in any language.',
    icon: Mic,
    iconBg: 'bg-violet-100',
    iconColor: 'text-violet-700',
  },
  {
    to: '/library',
    label: 'Library',
    hint: 'Every brief, draft, and published post.',
    icon: LibraryIcon,
    iconBg: 'bg-amber-100',
    iconColor: 'text-amber-700',
  },
  {
    to: '/translate',
    label: 'Translate',
    hint: 'Quick multilingual translator.',
    icon: Languages,
    iconBg: 'bg-emerald-100',
    iconColor: 'text-emerald-700',
  },
  {
    to: '/studio',
    label: 'Polish text',
    hint: 'Repunctuate dictated transcripts.',
    icon: Wand2,
    iconBg: 'bg-sky-100',
    iconColor: 'text-sky-700',
  },
  {
    to: '/settings',
    label: 'Voice setup',
    hint: 'Configure provider + brand voice.',
    icon: Sparkles,
    iconBg: 'bg-rose-100',
    iconColor: 'text-rose-700',
  },
]

function greeting(): string {
  const h = new Date().getHours()
  if (h < 5) return 'Working late'
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}

export function HomePage() {
  const navigate = useNavigate()
  const [posts, setPosts] = useState<PostRecord[] | null>(null)
  const [status, setStatus] = useState<StatusInfo | null>(null)

  useEffect(() => {
    api.posts().then((d) => setPosts(d.posts)).catch(() => setPosts([]))
    api.status().then(setStatus).catch(() => undefined)
  }, [])

  const recent = useMemo(
    () =>
      [...(posts ?? [])]
        .sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
        .slice(0, 5),
    [posts],
  )

  return (
    <div className="animate-fade-in">
      {/* Banner pill */}
      <div className="px-8 pt-7">
        <button
          type="button"
          className="inline-flex items-center gap-2 pl-1 pr-3 py-1 bg-bg-elevated border border-line-subtle rounded-full hover:bg-bg-hover transition"
        >
          <span className="px-2 py-0.5 rounded-full bg-ink-1 text-white text-[10px] font-bold uppercase tracking-wider">
            New
          </span>
          <span className="text-xs text-ink-2">
            Voice → Brief → Draft pipeline now in one panel
          </span>
          <ChevronRight className="w-3 h-3 text-ink-3" />
        </button>
      </div>

      {/* Greeting */}
      <section className="px-8 pt-6">
        <div className="text-xs text-ink-3 mb-1">My Workspace</div>
        <h1 className="text-3xl font-semibold tracking-tight text-ink-1">
          {greeting()}, Ratul
        </h1>
      </section>

      {/* Tile grid */}
      <section className="px-8 pt-7">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {TILES.map((tile) => (
            <button
              key={tile.label}
              type="button"
              onClick={() => navigate(tile.to)}
              className="tile text-left"
            >
              <div className={`tile-icon ${tile.iconBg}`}>
                <tile.icon className={`w-7 h-7 ${tile.iconColor}`} />
              </div>
              <div className="tile-label">{tile.label}</div>
              <div className="text-xs text-ink-3 mt-0.5 leading-snug">{tile.hint}</div>
            </button>
          ))}
        </div>
      </section>

      {/* Two-column: Library + System status */}
      <section className="px-8 pt-9 pb-12 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className="flex items-baseline justify-between mb-3">
            <h2 className="text-base font-semibold text-ink-1">Latest from the library</h2>
            <Link to="/library" className="btn-ghost text-xs">
              See all
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="card divide-y divide-line-subtle">
            {posts === null ? (
              <div className="p-5 text-sm text-ink-3 italic">Loading…</div>
            ) : recent.length === 0 ? (
              <div className="p-8 text-center">
                <div className="text-sm text-ink-2">No posts yet.</div>
                <button
                  type="button"
                  onClick={() => navigate('/studio')}
                  className="btn-primary mt-4"
                >
                  <Mic className="w-4 h-4" /> Record your first idea
                </button>
              </div>
            ) : (
              recent.map((p) => (
                <Link
                  key={p.post_id}
                  to={`/library/${p.post_id}`}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-bg-elevated transition"
                >
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-400 to-fuchsia-500 grid place-items-center text-white text-[11px] font-bold shrink-0">
                    {(p.working_title || p.post_id)[0].toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-ink-1 truncate">
                      {p.working_title || p.post_id}
                    </div>
                    <div className="text-xs text-ink-3 truncate">
                      {p.hook_pattern_used || 'no hook'}
                      {p.structural_framework_used && ` · ${p.structural_framework_used}`}
                      {' · '}
                      {formatRelativeDate(p.created_at)}
                    </div>
                  </div>
                  <StatusBadge status={p.status} />
                </Link>
              ))
            )}
          </div>
        </div>

        <aside>
          <h2 className="text-base font-semibold text-ink-1 mb-3">Voice + provider</h2>
          <div className="card p-5 space-y-3">
            <Row label="Provider" value={status?.provider ?? '…'} mono />
            <Row label="Model" value={status?.model ?? '…'} mono />
            <Row
              label="API key"
              value={
                status?.has_active_provider_key ? (
                  <span className="inline-flex items-center gap-1.5 text-emerald-600">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                    set
                  </span>
                ) : (
                  <span className="text-amber-600">missing</span>
                )
              }
            />
            <Row label="Brand" value={status?.brand_name ?? '…'} />
            <Row
              label="Cadence"
              value={status ? `${status.cadence_days} day${status.cadence_days === 1 ? '' : 's'}` : '…'}
            />
            <Link to="/settings" className="btn-secondary w-full mt-2">
              Open settings
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <h2 className="text-base font-semibold text-ink-1 mb-3 mt-7">Quick start</h2>
          <div className="card p-5 text-sm space-y-2.5 text-ink-2">
            <Step n={1} text="Record your idea in Studio (any language)." />
            <Step n={2} text="Compose a brief — auto-translated to English." />
            <Step n={3} text="Generate the draft, then run the detector." />
            <Step n={4} text="Hand-edit flagged spans, publish on Substack, log the URL." />
          </div>
        </aside>
      </section>
    </div>
  )
}

function Row({
  label,
  value,
  mono,
}: {
  label: string
  value: React.ReactNode
  mono?: boolean
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-xs text-ink-3">{label}</span>
      <span
        className={`text-sm text-ink-1 truncate text-right ${mono ? 'font-mono' : ''}`}
      >
        {value || '—'}
      </span>
    </div>
  )
}

function Step({ n, text }: { n: number; text: string }) {
  return (
    <div className="flex gap-2.5">
      <span className="w-5 h-5 rounded-full bg-bg-elevated border border-line-subtle text-[11px] font-mono grid place-items-center text-ink-3 shrink-0 mt-0.5">
        {n}
      </span>
      <span className="leading-snug">{text}</span>
    </div>
  )
}
