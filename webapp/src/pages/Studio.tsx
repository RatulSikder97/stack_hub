import {
  ArrowRight,
  ChevronRight,
  Files,
  History,
  Languages,
  Mic,
  Music,
  Search,
  Settings2,
  Sparkles,
  Trash2,
  Wand2,
  Waves,
} from 'lucide-react'
import { useEffect, useMemo, useState, type ComponentType } from 'react'
import { useNavigate } from 'react-router-dom'
import { Spinner } from '../components/Spinner'
import { useToast } from '../components/ToastProvider'
import { useVoiceRecorder } from '../hooks/useVoiceRecorder'
import { ApiError, RateLimitedError, api } from '../lib/api'
import type { BriefResult, PostRecord } from '../lib/types'
import { cn, formatRelativeDate } from '../lib/utils'

const LANGUAGE_OPTIONS = [
  { value: 'bn-BD', label: 'বাংলা (BD)' },
  { value: 'bn-IN', label: 'বাংলা (IN)' },
  { value: 'en-US', label: 'English (US)' },
  { value: 'hi-IN', label: 'हिन्दी' },
  { value: 'es-ES', label: 'Español' },
  { value: 'fr-FR', label: 'Français' },
]

const RAIL_ITEMS: Array<{
  id: string
  icon: ComponentType<{ className?: string }>
  label: string
  enabled: boolean
}> = [
  { id: 'voice', icon: Mic, label: 'Voice', enabled: true },
  { id: 'history', icon: History, label: 'History', enabled: true },
  { id: 'translate', icon: Languages, label: 'Translate', enabled: true },
  { id: 'detect', icon: Search, label: 'Detect', enabled: false },
  { id: 'files', icon: Files, label: 'Files', enabled: false },
  { id: 'sfx', icon: Music, label: 'Music', enabled: false },
]

function formatDuration(s: number): string {
  const mm = String(Math.floor(s / 60)).padStart(2, '0')
  const ss = String(s % 60).padStart(2, '0')
  return `${mm}:${ss}`
}

export function Studio() {
  const navigate = useNavigate()
  const toast = useToast()
  const [language, setLanguage] = useState('bn-BD')
  const recorder = useVoiceRecorder(language)
  const [composing, setComposing] = useState(false)
  const [polishing, setPolishing] = useState(false)
  const [translating, setTranslating] = useState(false)
  const [recent, setRecent] = useState<PostRecord[]>([])
  const [activeRail, setActiveRail] = useState<string>('voice')

  useEffect(() => {
    api.posts()
      .then((d) => {
        const sorted = [...d.posts]
          .sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
          .slice(0, 5)
        setRecent(sorted)
      })
      .catch(() => undefined)
  }, [])

  const wordCount = useMemo(
    () => recorder.transcript.trim().split(/\s+/).filter(Boolean).length,
    [recorder.transcript],
  )
  const charCount = recorder.transcript.length
  const recState = recorder.state
  const isLive = recState === 'live'
  const isPaused = recState === 'paused'

  const handleCompose = async () => {
    const idea = recorder.transcript.trim()
    if (!idea) {
      toast.error('Idea is empty.')
      return
    }
    setComposing(true)
    try {
      const result: BriefResult = await api.brief(idea, 'en')
      toast.success(`Brief ready: ${result.working_title}`)
      navigate(`/library/${result.post_id}`)
    } catch (e) {
      if (e instanceof RateLimitedError) toast.error(`Rate limited. Retry in ~${e.retryAfter}s.`)
      else if (e instanceof ApiError) toast.error(`Brief failed: ${e.message}`)
      else toast.error('Brief failed. Check the server.')
    } finally {
      setComposing(false)
    }
  }

  const handlePolish = async () => {
    const text = recorder.transcript.trim()
    if (!text) {
      toast.error('Nothing to polish.')
      return
    }
    setPolishing(true)
    try {
      const probe = await api.translate(text, 'en')
      let polished = text
      if (probe.source_language === 'en' || probe.source_language === 'unknown') {
        polished = probe.translated_text || text
      } else {
        const back = await api.translate(probe.translated_text, probe.source_language)
        polished = back.translated_text || text
      }
      recorder.setTranscript(polished)
      toast.success('Polished punctuation.')
    } catch (e) {
      if (e instanceof RateLimitedError) toast.error(`Rate limited. Retry in ~${e.retryAfter}s.`)
      else toast.error('Polish failed.')
    } finally {
      setPolishing(false)
    }
  }

  const handleTranslate = async () => {
    const text = recorder.transcript.trim()
    if (!text) {
      toast.error('Nothing to translate.')
      return
    }
    setTranslating(true)
    try {
      const result = await api.translate(text, 'en')
      if (result.needed_translation) {
        recorder.setTranscript(result.translated_text)
        toast.success(`Translated ${result.source_language} → en`)
      } else {
        toast.info('Already in English.')
      }
    } catch (e) {
      if (e instanceof RateLimitedError) toast.error(`Rate limited. Retry in ~${e.retryAfter}s.`)
      else toast.error('Translate failed.')
    } finally {
      setTranslating(false)
    }
  }

  return (
    <div className="animate-fade-in flex h-[calc(100vh-3.5rem)]">
      {/* Far-left icon rail */}
      <div className="w-[60px] shrink-0 border-r border-line-subtle bg-bg-subtle flex flex-col items-center py-3 gap-1">
        {RAIL_ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => item.enabled && setActiveRail(item.id)}
            disabled={!item.enabled}
            className={cn(
              'w-10 h-10 rounded-lg flex flex-col items-center justify-center transition relative group',
              activeRail === item.id && item.enabled
                ? 'bg-ink-1 text-white'
                : item.enabled
                  ? 'text-ink-3 hover:text-ink-1 hover:bg-bg-elevated'
                  : 'text-ink-5 cursor-not-allowed opacity-50',
            )}
            title={item.label}
          >
            <item.icon className="w-4 h-4" />
            <span className="text-[9px] mt-0.5 font-medium">{item.label}</span>
          </button>
        ))}
      </div>

      {/* Parameter panel */}
      <aside className="w-[320px] shrink-0 border-r border-line-subtle bg-bg-base overflow-y-auto">
        <div className="px-5 py-4 border-b border-line-subtle">
          <h2 className="text-sm font-semibold text-ink-1">Recording</h2>
          <p className="text-xs text-ink-3 mt-0.5">Configure capture + post-processing.</p>
        </div>

        <Section title="Input" icon={Settings2}>
          <Field label="Language">
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              disabled={isLive || isPaused}
              className="w-full bg-white border border-line rounded-lg px-3 py-2 text-sm text-ink-1 focus:outline-none focus:border-ink-1 transition disabled:opacity-50"
            >
              {LANGUAGE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Microphone" hint="System default">
            <ReadOnlyValue value="Default device" />
          </Field>
          <Field label="Sample rate" hint="Browser-managed">
            <ReadOnlyValue value="44.1 kHz" mono />
          </Field>
        </Section>

        <Section title="Punctuation" icon={Waves}>
          <Field label="Period after" hint="silence (ms)">
            <ReadOnlyValue value="700" mono />
          </Field>
          <Field label="Paragraph after" hint="silence (ms)">
            <ReadOnlyValue value="1800" mono />
          </Field>
          <Field label="Bengali · Hindi script">
            <span className="text-xs text-emerald-600 inline-flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              auto-detected
            </span>
          </Field>
        </Section>

        <Section title="AI Tools" icon={Sparkles}>
          <ToolButton
            icon={Wand2}
            iconBg="bg-violet-100"
            iconColor="text-violet-700"
            title="Polish punctuation"
            hint="LLM repunctuation pass"
            busy={polishing}
            onClick={handlePolish}
          />
          <ToolButton
            icon={Languages}
            iconBg="bg-emerald-100"
            iconColor="text-emerald-700"
            title="Translate to English"
            hint="In-place rewrite"
            busy={translating}
            onClick={handleTranslate}
          />
        </Section>

        <Section title="Recent" icon={History}>
          {recent.length === 0 ? (
            <p className="text-xs text-ink-4 italic px-1">No drafts yet.</p>
          ) : (
            <div className="space-y-1">
              {recent.map((p) => (
                <button
                  key={p.post_id}
                  type="button"
                  onClick={() => navigate(`/library/${p.post_id}`)}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-bg-elevated transition text-left"
                >
                  <span className="w-6 h-6 rounded bg-gradient-to-br from-violet-400 to-fuchsia-500 grid place-items-center text-[10px] text-white font-bold shrink-0">
                    {(p.working_title || p.post_id)[0].toUpperCase()}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs text-ink-1 font-medium truncate">
                      {p.working_title || p.post_id}
                    </div>
                    <div className="text-[10px] text-ink-3 truncate">
                      {formatRelativeDate(p.created_at)}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </Section>
      </aside>

      {/* Canvas */}
      <section className="flex-1 min-w-0 flex flex-col bg-bg-base">
        {/* Canvas header */}
        <div className="flex items-center justify-between px-8 py-4 border-b border-line-subtle">
          <div className="flex items-center gap-3">
            <span className={cn('rec-dot', isLive && 'live', isPaused && 'paused')} />
            <span
              className={cn(
                'text-xs uppercase tracking-widest font-semibold',
                isLive && 'text-red-500',
                isPaused && 'text-amber-600',
                !isLive && !isPaused && 'text-ink-3',
              )}
            >
              {isLive ? 'Recording' : isPaused ? 'Paused' : 'Ready'}
            </span>
            {!recorder.isSupported && (
              <span className="text-xs text-amber-600 ml-3">
                Voice input requires Chrome/Safari.
              </span>
            )}
          </div>
          <div className="flex items-center gap-3 text-xs text-ink-3">
            <span className="font-mono">{formatDuration(recorder.durationSec)}</span>
            <span className="text-ink-5">·</span>
            <span>
              {wordCount} word{wordCount === 1 ? '' : 's'}
            </span>
            <span className="text-ink-5">·</span>
            <span>{charCount} chars</span>
          </div>
        </div>

        {/* Canvas body */}
        <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[280px_1fr] overflow-hidden">
          {/* Mic side */}
          <div className="flex flex-col items-center justify-center px-6 py-10 border-b lg:border-b-0 lg:border-r border-line-subtle bg-bg-subtle/40 relative">
            <div className="mic-stage">
              <canvas
                ref={recorder.canvasRef}
                width={240}
                height={240}
                className="mic-canvas w-full h-full"
              />
              <button
                type="button"
                onClick={recorder.toggle}
                className={cn(
                  'mic-button',
                  isLive && 'recording',
                  isPaused && 'paused',
                )}
                title={isLive ? 'Stop recording' : 'Start recording'}
                disabled={!recorder.isSupported}
              >
                <Mic className="w-7 h-7" />
              </button>
            </div>
            <p className="text-xs text-ink-3 text-center mt-4 leading-relaxed max-w-[200px]">
              {isLive
                ? `Listening · ${language}`
                : isPaused
                  ? 'Paused — keep talking to continue'
                  : 'Click the mic, then speak. Pause for punctuation.'}
            </p>
          </div>

          {/* Transcript side */}
          <div className="flex flex-col min-h-0">
            <div className="flex items-center justify-between px-8 pt-6 pb-2">
              <span className="text-[10px] uppercase tracking-widest text-ink-3 font-semibold">
                Transcript
              </span>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => recorder.setTranscript('')}
                  className="btn-ghost"
                  title="Clear transcript"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Clear
                </button>
              </div>
            </div>
            <textarea
              value={recorder.transcript}
              onChange={(e) => recorder.setTranscript(e.target.value)}
              placeholder="তোমার ধারণা বাংলায় বলো বা টাইপ করো... auto-punctuation triggers when you pause."
              className="flex-1 mx-8 mb-6 bg-transparent border-0 resize-none focus:outline-none text-[16px] leading-7 text-ink-1 placeholder:text-ink-4 font-sans"
            />
          </div>
        </div>

        {/* Bottom action bar */}
        <div className="border-t border-line-subtle bg-bg-base px-8 py-3.5 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 text-xs text-ink-3">
            <span className="font-mono">{formatDuration(recorder.durationSec)}</span>
            <span className="hidden sm:inline">
              {wordCount} word{wordCount === 1 ? '' : 's'} ·{' '}
              {charCount} characters
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => recorder.setTranscript('')}
              disabled={!recorder.transcript.trim()}
              className="btn-secondary"
              title="Clear and start over"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Reset
            </button>
            <button
              type="button"
              onClick={handleCompose}
              disabled={composing || !recorder.transcript.trim()}
              className="btn-primary"
            >
              {composing ? (
                <>
                  <Spinner /> Composing…
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Compose Brief
                  <ChevronRight className="w-4 h-4 -mr-1" />
                </>
              )}
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}

// ---------- Internals ----------

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string
  icon: ComponentType<{ className?: string }>
  children: React.ReactNode
}) {
  return (
    <section className="px-5 py-4 border-b border-line-subtle">
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-3.5 h-3.5 text-ink-3" />
        <h3 className="text-[10px] uppercase tracking-widest text-ink-3 font-semibold">
          {title}
        </h3>
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  )
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <label className="text-xs text-ink-2 font-medium">{label}</label>
        {hint && <span className="text-[10px] text-ink-4">{hint}</span>}
      </div>
      {children}
    </div>
  )
}

function ReadOnlyValue({ value, mono }: { value: string; mono?: boolean }) {
  return (
    <div
      className={cn(
        'w-full bg-bg-elevated border border-line-subtle rounded-lg px-3 py-2 text-sm text-ink-2',
        mono && 'font-mono',
      )}
    >
      {value}
    </div>
  )
}

function ToolButton({
  icon: Icon,
  iconBg,
  iconColor,
  title,
  hint,
  busy,
  onClick,
}: {
  icon: ComponentType<{ className?: string }>
  iconBg: string
  iconColor: string
  title: string
  hint: string
  busy: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      className="w-full flex items-center gap-3 px-2.5 py-2.5 rounded-lg border border-line-subtle hover:bg-bg-elevated transition text-left disabled:opacity-50"
    >
      <span
        className={cn(
          'w-8 h-8 rounded-lg flex items-center justify-center shrink-0',
          iconBg,
        )}
      >
        {busy ? (
          <Spinner className={iconColor} />
        ) : (
          <Icon className={cn('w-4 h-4', iconColor)} />
        )}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium text-ink-1">{title}</span>
        <span className="block text-[11px] text-ink-3 truncate">{hint}</span>
      </span>
      <ArrowRight className="w-3.5 h-3.5 text-ink-4 shrink-0" />
    </button>
  )
}
