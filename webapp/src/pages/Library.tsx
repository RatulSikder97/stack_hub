import { Library as LibraryIcon, Mic, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { StatusBadge } from '../components/Badge'
import { useToast } from '../components/ToastProvider'
import { api } from '../lib/api'
import type { PostRecord } from '../lib/types'
import { formatRelativeDate } from '../lib/utils'

export function LibraryPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const [posts, setPosts] = useState<PostRecord[] | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const load = async () => {
    setRefreshing(true)
    try {
      const data = await api.posts()
      // Most recent first.
      const sorted = [...data.posts].sort((a, b) =>
        (b.created_at || '').localeCompare(a.created_at || ''),
      )
      setPosts(sorted)
    } catch {
      toast.error('Failed to load posts.')
    } finally {
      setRefreshing(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Library"
        subtitle={`${posts?.length ?? 0} post${posts?.length === 1 ? '' : 's'} · click any row to open`}
        actions={
          <>
            <button onClick={load} className="btn-secondary" disabled={refreshing}>
              {refreshing ? 'Refreshing…' : 'Refresh'}
            </button>
            <button onClick={() => navigate('/studio')} className="btn-primary">
              <Plus className="w-4 h-4" />
              New post
            </button>
          </>
        }
      />

      <div className="px-8 pb-12">
        {posts === null ? (
          <div className="card p-8 text-sm text-ink-3 italic">Loading…</div>
        ) : posts.length === 0 ? (
          <div className="card">
            <EmptyState
              icon={LibraryIcon}
              title="No posts yet"
              description="Head to the Studio to record your first idea and compose a brief."
              action={
                <button onClick={() => navigate('/studio')} className="btn-primary">
                  <Mic className="w-4 h-4" />
                  Open Studio
                </button>
              }
            />
          </div>
        ) : (
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[10px] uppercase tracking-widest text-ink-3 border-b border-line-subtle">
                  <th className="px-5 py-3 font-semibold">Title</th>
                  <th className="px-5 py-3 font-semibold">Status</th>
                  <th className="px-5 py-3 font-semibold">Hook</th>
                  <th className="px-5 py-3 font-semibold">Framework</th>
                  <th className="px-5 py-3 font-semibold">Created</th>
                </tr>
              </thead>
              <tbody>
                {posts.map((p) => (
                  <tr
                    key={p.post_id}
                    className="border-b border-line-subtle last:border-0 hover:bg-bg-elevated/50 transition cursor-pointer"
                    onClick={() => navigate(`/library/${p.post_id}`)}
                  >
                    <td className="px-5 py-3.5">
                      <Link
                        to={`/library/${p.post_id}`}
                        className="text-ink-1 hover:text-brand transition font-medium"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {p.working_title || p.post_id}
                      </Link>
                      <div className="text-[11px] font-mono text-ink-4 mt-0.5">{p.post_id}</div>
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge status={p.status} />
                    </td>
                    <td className="px-5 py-3.5 text-ink-2">{p.hook_pattern_used || '—'}</td>
                    <td className="px-5 py-3.5 text-ink-2">{p.structural_framework_used || '—'}</td>
                    <td className="px-5 py-3.5 text-ink-3">{formatRelativeDate(p.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
