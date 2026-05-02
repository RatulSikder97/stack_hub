import { ArrowLeft, FileText, Search, Share2, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { PageHeader } from '../components/PageHeader'
import { Spinner } from '../components/Spinner'
import { StatusBadge } from '../components/Badge'
import { Tabs } from '../components/Tabs'
import { useToast } from '../components/ToastProvider'
import { ApiError, RateLimitedError, api } from '../lib/api'
import type { DetectionFlag, DetectionResult, PostDetail } from '../lib/types'
import { cn, formatRelativeDate } from '../lib/utils'

export function PostDetailPage() {
  const { postId } = useParams<{ postId: string }>()
  const toast = useToast()
  const [detail, setDetail] = useState<PostDetail | null>(null)
  const [drafting, setDrafting] = useState(false)
  const [detecting, setDetecting] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [flags, setFlags] = useState<DetectionFlag[]>([])
  const [detection, setDetection] = useState<DetectionResult | null>(null)
  const [activeTab, setActiveTab] = useState<string>('brief')

  const load = async () => {
    if (!postId) return
    try {
      const data = await api.postDetail(postId)
      setDetail(data)
    } catch {
      toast.error('Could not load post detail.')
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [postId])

  const post = detail?.post
  const draftText = detail?.draft_text ?? detail?.published_text ?? ''

  const handleDraft = async () => {
    if (!postId) return
    setDrafting(true)
    try {
      const result = await api.draft(postId)
      await load()
      setActiveTab('draft')
      toast.success(`Draft ready · ${result.word_count} words`)
    } catch (e) {
      if (e instanceof RateLimitedError) {
        toast.error(`Rate limited. Retry in ~${e.retryAfter}s.`)
      } else if (e instanceof ApiError) {
        toast.error(`Draft failed: ${e.message}`)
      }
    } finally {
      setDrafting(false)
    }
  }

  const handleDetect = async () => {
    if (!postId) return
    setDetecting(true)
    try {
      const result = await api.detect(postId)
      setDetection(result)
      setFlags(result.flags)
      await load()
      setActiveTab('detector')
      toast.success(
        result.passed
          ? `PASS (${result.detector})`
          : `FAIL · ${result.flags.length} flag${result.flags.length === 1 ? '' : 's'}`,
      )
    } catch (e) {
      if (e instanceof RateLimitedError) {
        toast.error(`Rate limited. Retry in ~${e.retryAfter}s.`)
      } else if (e instanceof ApiError) {
        toast.error(`Detector failed: ${e.message}`)
      }
    } finally {
      setDetecting(false)
    }
  }

  const handlePublish = async () => {
    if (!postId) return
    const url = window.prompt('Substack URL for the published post:')
    if (!url) return
    setPublishing(true)
    try {
      await api.publish(postId, url)
      toast.success('Published — record updated.')
      await load()
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message)
    } finally {
      setPublishing(false)
    }
  }

  const renderedDraftHtml = useMemo(() => {
    if (!draftText) return ''
    if (!flags.length) return escapeHtml(draftText).replace(/\n/g, '<br/>')
    return wrapFlagsInHtml(draftText, flags)
  }, [draftText, flags])

  if (!postId) return null

  return (
    <div className="animate-fade-in">
      <div className="px-8 pt-6 -mb-2">
        <Link to="/library" className="btn-ghost text-xs">
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Library
        </Link>
      </div>
      <PageHeader
        title={post?.working_title || 'Loading…'}
        subtitle={post ? `${post.post_id} · ${formatRelativeDate(post.created_at)}` : undefined}
        actions={post ? <StatusBadge status={post.status} /> : undefined}
      />

      <div className="px-8 pb-12">
        <div className="grid grid-cols-1 xl:grid-cols-5 gap-5">
          <aside className="xl:col-span-2 space-y-4">
            <section className="card p-5">
              <div className="text-[10px] uppercase tracking-widest text-ink-3 font-semibold mb-3">
                Pipeline
              </div>
              <div className="space-y-2">
                <ActionRow
                  icon={FileText}
                  label="Generate Draft"
                  busy={drafting}
                  done={!!detail?.draft_text}
                  disabled={!post || post.status === 'idea'}
                  onClick={handleDraft}
                />
                <ActionRow
                  icon={Search}
                  label="Run Detector"
                  busy={detecting}
                  done={post?.ai_tells_check_passed ?? false}
                  disabled={!detail?.draft_text}
                  onClick={handleDetect}
                />
                <ActionRow
                  icon={Share2}
                  label="Log Publish"
                  busy={publishing}
                  done={post?.status === 'published'}
                  disabled={
                    !post ||
                    !post.ai_tells_check_passed ||
                    !post.human_edit_completed ||
                    post.status === 'published'
                  }
                  onClick={handlePublish}
                />
              </div>
              <p className="text-[11px] text-ink-4 mt-3 leading-relaxed">
                Publish requires both AI-tells and retention checks to pass. The retention check is
                done via the CLI script (<code className="font-mono">retention_check.py</code>) —
                it lives outside the panel by design.
              </p>
            </section>

            {post && (
              <section className="card p-5 text-sm">
                <div className="text-[10px] uppercase tracking-widest text-ink-3 font-semibold mb-3">
                  Metadata
                </div>
                <Field label="Hook pattern" value={post.hook_pattern_used} />
                <Field label="Framework" value={post.structural_framework_used} />
                <Field label="AI tells passed" value={post.ai_tells_check_passed ? 'yes' : 'no'} />
                <Field label="Retention passed" value={post.human_edit_completed ? 'yes' : 'no'} />
                <Field label="Open rate" value={post.open_rate ? `${post.open_rate}%` : '—'} />
                <Field label="Shares" value={String(post.share_count || '—')} />
                {post.substack_url && (
                  <Field
                    label="URL"
                    value={
                      <a
                        href={post.substack_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-brand hover:underline break-all"
                      >
                        {post.substack_url}
                      </a>
                    }
                  />
                )}
              </section>
            )}
          </aside>

          <section className="xl:col-span-3 card min-h-[640px] flex flex-col">
            <Tabs
              controlledTab={activeTab}
              onTabChange={setActiveTab}
              tabs={[
                {
                  id: 'brief',
                  label: 'Brief',
                  content: (
                    <div className="p-6 prose prose-stack max-w-none">
                      {detail?.brief_text ? (
                        <pre className="whitespace-pre-wrap font-sans text-[15px] leading-7 m-0 bg-transparent border-0 p-0 text-ink-2">
                          {detail.brief_text}
                        </pre>
                      ) : (
                        <p className="text-ink-3 italic">Brief will appear here.</p>
                      )}
                    </div>
                  ),
                },
                {
                  id: 'draft',
                  label: 'Draft',
                  content: (
                    <div className="p-6">
                      {draftText ? (
                        <>
                          <div className="text-xs text-ink-3 mb-3">
                            {draftText.split(/\s+/).filter(Boolean).length} words
                          </div>
                          <div
                            className="prose prose-stack max-w-none whitespace-pre-wrap text-[15px] leading-7"
                            dangerouslySetInnerHTML={{ __html: renderedDraftHtml }}
                          />
                        </>
                      ) : (
                        <p className="text-ink-3 italic">Generate a draft to see it here.</p>
                      )}
                    </div>
                  ),
                },
                {
                  id: 'detector',
                  label: 'Detector',
                  content: (
                    <div className="p-6">
                      {detection ? (
                        <DetectorView
                          detection={detection}
                          onJump={(idx) => {
                            setActiveTab('draft')
                            requestAnimationFrame(() => {
                              const el = document.getElementById(`flag-${idx}`)
                              if (el) {
                                el.scrollIntoView({ behavior: 'smooth', block: 'center' })
                                el.classList.add('flag-flash')
                                setTimeout(() => el.classList.remove('flag-flash'), 1500)
                              }
                            })
                          }}
                        />
                      ) : (
                        <p className="text-ink-3 italic">Run the detector to see flags here.</p>
                      )}
                    </div>
                  ),
                },
              ]}
            />
          </section>
        </div>
      </div>
    </div>
  )
}

function ActionRow({
  icon: Icon,
  label,
  busy,
  done,
  disabled,
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  busy: boolean
  done: boolean
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      disabled={busy || disabled}
      className={cn(
        'w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg border text-sm font-medium transition',
        done
          ? 'bg-emerald-500/8 border-emerald-500/30 text-emerald-300'
          : 'bg-bg-elevated border-line-subtle text-ink-1 hover:bg-bg-hover',
        (busy || disabled) && 'opacity-50 cursor-not-allowed',
      )}
    >
      <span className="flex items-center gap-2">
        <Icon className="w-4 h-4" />
        {label}
      </span>
      {busy ? <Spinner /> : done ? '✓' : <Sparkles className="w-3.5 h-3.5 opacity-50" />}
    </button>
  )
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5 first:pt-0">
      <span className="text-xs text-ink-3 shrink-0">{label}</span>
      <span className="text-sm text-ink-1 text-right truncate">{value || '—'}</span>
    </div>
  )
}

function DetectorView({
  detection,
  onJump,
}: {
  detection: DetectionResult
  onJump: (idx: number) => void
}) {
  return (
    <>
      <div className="flex items-center justify-between mb-4">
        <h3
          className={cn(
            'text-base font-semibold',
            detection.passed ? 'text-emerald-400' : 'text-red-400',
          )}
        >
          {detection.passed ? 'PASS' : 'FAIL'} — {detection.flags.length} flag
          {detection.flags.length === 1 ? '' : 's'}
        </h3>
        <span className="text-xs text-ink-3 font-mono">{detection.detector}</span>
      </div>
      {detection.flags.length === 0 ? (
        <p className="text-ink-3 text-sm italic">
          No AI tells found. The draft is clear of the kill-list patterns.
        </p>
      ) : (
        <>
          <p className="text-xs text-ink-3 mb-3">
            Click a flag to jump to its highlighted location in the draft.
          </p>
          {detection.flags.map((f, idx) => (
            <button
              key={idx}
              onClick={() => onJump(idx)}
              className="flag-row w-full text-left"
            >
              <div className="flex items-center justify-between">
                <span className="flag-pattern">{f.pattern}</span>
                <span className="flag-line">~line {f.line_approx}</span>
              </div>
              <div className="flag-snippet">{f.snippet}</div>
            </button>
          ))}
        </>
      )}
    </>
  )
}

function escapeHtml(s: string): string {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[c]!)
}

function wrapFlagsInHtml(text: string, flags: DetectionFlag[]): string {
  const sorted = flags
    .map((f, idx) => ({ ...f, idx }))
    .sort((a, b) => b.snippet.length - a.snippet.length)
  let working = text
  sorted.forEach((flag) => {
    const lower = working.toLowerCase()
    const pos = lower.indexOf(flag.snippet.toLowerCase())
    if (pos < 0) return
    working =
      working.slice(0, pos) +
      `__FLAGOPEN${flag.idx}__` +
      working.slice(pos, pos + flag.snippet.length) +
      `__FLAGCLOSE${flag.idx}__` +
      working.slice(pos + flag.snippet.length)
  })
  let html = escapeHtml(working).replace(/\n/g, '<br/>')
  sorted.forEach((flag) => {
    const open = `<mark class="flag-highlight" id="flag-${flag.idx}" title="${escapeHtml(flag.pattern)} (~line ${flag.line_approx})">`
    html = html
      .split(`__FLAGOPEN${flag.idx}__`)
      .join(open)
      .split(`__FLAGCLOSE${flag.idx}__`)
      .join('</mark>')
  })
  return html
}
