import { Mic, Sparkles, Trash2, Wand2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PageHeader } from '../components/PageHeader'
import { Spinner } from '../components/Spinner'
import { useToast } from '../components/ToastProvider'
import { useVoiceRecorder } from '../hooks/useVoiceRecorder'
import { ApiError, RateLimitedError, api } from '../lib/api'
import type { BriefResult } from '../lib/types'
import { cn } from '../lib/utils'

const LANGUAGE_OPTIONS = [
  { value: 'bn-BD', label: 'বাংলা (BD)' },
  { value: 'bn-IN', label: 'বাংলা (IN)' },
  { value: 'en-US', label: 'English (US)' },
  { value: 'hi-IN', label: 'हिन्दी' },
  { value: 'es-ES', label: 'Español' },
  { value: 'fr-FR', label: 'Français' },
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
  const [retryAt, setRetryAt] = useState<number | null>(null)

  const recState = recorder.state
  const ready = recState === 'ready'
  const live = recState === 'live'
  const paused = recState === 'paused'

  // Countdown for rate limits.
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (retryAt === null) return
    const handle = setInterval(() => setNow(Date.now()), 500)
    return () => clearInterval(handle)
  }, [retryAt])
  const retrySecondsLeft = useMemo(() => {
    if (retryAt === null) return 0
    return Math.max(0, Math.ceil((retryAt - now) / 1000))
  }, [now, retryAt])
  useEffect(() => {
    if (retryAt !== null && retrySecondsLeft === 0) setRetryAt(null)
  }, [retryAt, retrySecondsLeft])

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
      navigate(`/library/${result.post_id}`, { state: { result } })
    } catch (e) {
      if (e instanceof RateLimitedError) {
        toast.error(`Rate limited. Try again in ~${e.retryAfter}s.`)
        setRetryAt(Date.now() + e.retryAfter * 1000)
      } else if (e instanceof ApiError) {
        toast.error(`Brief failed: ${e.message}`)
      } else {
        toast.error('Brief failed. Check the server.')
      }
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
      if (e instanceof RateLimitedError) {
        toast.error(`Rate limited. Try again in ~${e.retryAfter}s.`)
        setRetryAt(Date.now() + e.retryAfter * 1000)
      } else {
        toast.error('Polish failed.')
      }
    } finally {
      setPolishing(false)
    }
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Studio"
        subtitle="Speak or type your idea. Pause for punctuation. Compose a brief in seconds."
      />

      <div className="px-8 pb-12">
        <div className="grid grid-cols-1 xl:grid-cols-5 gap-5">
          {/* Recorder */}
          <section className="xl:col-span-3 card p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className={cn('rec-dot', live && 'live', paused && 'paused')} />
                <span
                  className={cn(
                    'text-xs uppercase tracking-widest font-semibold',
                    live && 'text-red-400',
                    paused && 'text-amber-400',
                    ready && 'text-ink-3',
                  )}
                >
                  {live ? 'Live' : paused ? 'Paused' : 'Ready'}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-ink-3">
                  {formatDuration(recorder.durationSec)}
                </span>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  disabled={!ready}
                  className="text-xs bg-bg-elevated border border-line-subtle rounded-md px-2 py-1 text-ink-1 focus:outline-none focus:border-brand"
                >
                  {LANGUAGE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex flex-col items-center justify-center py-8">
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
                    live && 'recording',
                    paused && 'paused',
                  )}
                  title="Click to record"
                  disabled={!recorder.isSupported}
                >
                  <Mic className="w-8 h-8" />
                </button>
              </div>
              <p className="text-xs text-ink-3 mt-3 h-4">
                {!recorder.isSupported
                  ? 'Voice input requires Chrome or Safari. You can still type.'
                  : live
                    ? `Listening (${language}) · pause for punctuation`
                    : paused
                      ? 'Paused — keep talking to continue'
                      : 'Click the mic, then speak'}
              </p>
            </div>

            <div className="mt-4">
              <div className="flex items-center justify-between mb-2">
                <label
                  htmlFor="ideaText"
                  className="text-[10px] uppercase tracking-widest text-ink-3 font-semibold"
                >
                  Transcript
                </label>
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
                  <button
                    type="button"
                    onClick={handlePolish}
                    disabled={polishing || retrySecondsLeft > 0}
                    className="btn-ghost text-brand disabled:opacity-40"
                    title="LLM repunctuation pass"
                  >
                    {polishing ? <Spinner /> : <Wand2 className="w-3.5 h-3.5" />}
                    Polish
                  </button>
                </div>
              </div>
              <textarea
                id="ideaText"
                rows={6}
                value={recorder.transcript}
                onChange={(e) => recorder.setTranscript(e.target.value)}
                placeholder="তোমার ধারণা বাংলায় বলো বা টাইপ করো... auto-punctuation triggers when you pause."
                className="input"
              />
            </div>

            <button
              type="button"
              onClick={handleCompose}
              disabled={composing || retrySecondsLeft > 0}
              className="btn-primary w-full mt-4"
            >
              {composing ? (
                <>
                  <Spinner /> Composing…
                </>
              ) : retrySecondsLeft > 0 ? (
                <>⏳ wait {retrySecondsLeft}s</>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  Compose Brief
                </>
              )}
            </button>
          </section>

          {/* Side panel — workflow guidance */}
          <aside className="xl:col-span-2 card p-6 self-start">
            <h3 className="text-sm font-semibold text-ink-1">How this works</h3>
            <ol className="mt-4 space-y-3 text-sm text-ink-2">
              <li className="flex gap-3">
                <span className="w-5 h-5 rounded-full bg-bg-elevated border border-line-subtle text-[11px] font-mono grid place-items-center text-ink-3 shrink-0 mt-0.5">
                  1
                </span>
                <span>
                  Speak in any supported language or type directly. Pause for ~700ms to drop a
                  period; pause longer for a paragraph break.
                </span>
              </li>
              <li className="flex gap-3">
                <span className="w-5 h-5 rounded-full bg-bg-elevated border border-line-subtle text-[11px] font-mono grid place-items-center text-ink-3 shrink-0 mt-0.5">
                  2
                </span>
                <span>
                  Compose Brief — your idea is translated to English, then a 6-section brief is
                  generated, anchored on the brand voice.
                </span>
              </li>
              <li className="flex gap-3">
                <span className="w-5 h-5 rounded-full bg-bg-elevated border border-line-subtle text-[11px] font-mono grid place-items-center text-ink-3 shrink-0 mt-0.5">
                  3
                </span>
                <span>
                  You land on the post detail page where you can generate a draft, run the AI-tells
                  detector, and finally publish.
                </span>
              </li>
            </ol>
            <div className="mt-6 pt-4 border-t border-line-subtle">
              <div className="text-[10px] uppercase tracking-widest text-ink-3 font-semibold mb-2">
                Tip
              </div>
              <p className="text-sm text-ink-2 leading-relaxed">
                The detector hand-edit loop teaches your eye over time. Treat the first 3 posts as
                practice runs; expect 4–6 flags per draft until the brand voice tightens.
              </p>
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}
