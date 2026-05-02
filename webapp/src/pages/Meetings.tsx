import {
  ArrowRight,
  CheckCircle2,
  FileAudio,
  FileText,
  Radio,
  Sparkles,
  Square,
  Trash2,
  Upload,
  Users,
  Video,
} from 'lucide-react'
import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from 'react'
import { useNavigate } from 'react-router-dom'
import { PageHeader } from '../components/PageHeader'
import { Spinner } from '../components/Spinner'
import { useToast } from '../components/ToastProvider'
import {
  ApiError,
  RateLimitedError,
  api,
  type BotState,
  type BotStatus,
  type TranscriptParseResult,
} from '../lib/api'
import { cn } from '../lib/utils'

const ACCEPTED_EXTENSIONS = ['.vtt', '.srt', '.txt', '.md']
const POLL_INTERVAL_MS = 7000

export function MeetingsPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const [content, setContent] = useState('')
  const [filename, setFilename] = useState<string | null>(null)
  const [parsing, setParsing] = useState(false)
  const [composing, setComposing] = useState(false)
  const [parsed, setParsed] = useState<TranscriptParseResult | null>(null)
  const [editedText, setEditedText] = useState('')
  const [dragOver, setDragOver] = useState(false)

  // Real-time bot state
  const [meetingUrl, setMeetingUrl] = useState('')
  const [bot, setBot] = useState<BotStatus | null>(null)
  const [dispatching, setDispatching] = useState(false)
  const [leaving, setLeaving] = useState(false)
  const [recallReady, setRecallReady] = useState<boolean | null>(null)
  const pollRef = useRef<number | null>(null)

  const handleFile = async (file: File) => {
    if (file.size > 5 * 1024 * 1024) {
      toast.error('File too large (limit 5 MB).')
      return
    }
    const text = await file.text()
    setContent(text)
    setFilename(file.name)
    setParsed(null)
    setEditedText('')
  }

  const handleFileInput = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }

  const handleParse = async () => {
    if (!content.trim()) {
      toast.error('Paste a transcript or drop a file first.')
      return
    }
    setParsing(true)
    try {
      const result = await api.parseTranscript(content, filename ?? undefined)
      setParsed(result)
      setEditedText(result.text)
      toast.success(
        `Parsed ${result.detected_format.toUpperCase()} transcript · ${result.word_count} words`,
      )
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message)
    } finally {
      setParsing(false)
    }
  }

  const handleCompose = async () => {
    const idea = (editedText || parsed?.text || content).trim()
    if (!idea) {
      toast.error('No text to compose from.')
      return
    }
    setComposing(true)
    try {
      const result = await api.brief(idea, 'en')
      toast.success(`Brief ready: ${result.working_title}`)
      navigate(`/library/${result.post_id}`)
    } catch (e) {
      if (e instanceof RateLimitedError) toast.error(`Rate limited. Retry in ~${e.retryAfter}s.`)
      else if (e instanceof ApiError) toast.error(e.message)
    } finally {
      setComposing(false)
    }
  }

  // ----- Real-time bot lifecycle -----
  const stopPolling = () => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  useEffect(() => {
    return () => stopPolling()
  }, [])

  const pollBot = async (botId: string) => {
    try {
      const status = await api.getMeetingBot(botId)
      setBot(status)
      if (status.state === 'done') {
        stopPolling()
        if (status.transcript_text) {
          setContent(status.transcript_text)
          setFilename(`recall-bot-${botId.slice(0, 8)}.txt`)
          setParsed(null)
          setEditedText('')
          toast.success('Bot left the meeting · transcript ready')
        } else {
          toast.info('Bot finished but no transcript was returned.')
        }
      } else if (status.state === 'error') {
        stopPolling()
        toast.error(status.error || 'Bot failed.')
      }
    } catch (e) {
      if (e instanceof ApiError) toast.error(`Bot poll failed: ${e.message}`)
      stopPolling()
    }
  }

  const handleDispatchBot = async () => {
    const url = meetingUrl.trim()
    if (!url) {
      toast.error('Paste a Zoom or Meet URL first.')
      return
    }
    if (!/^https?:\/\//.test(url)) {
      toast.error('Meeting URL must start with https://')
      return
    }
    setDispatching(true)
    try {
      const result = await api.createMeetingBot(url)
      const initial: BotStatus = {
        bot_id: result.bot_id,
        state: 'queued',
        raw_status_codes: [],
        transcript_text: null,
        error: null,
      }
      setBot(initial)
      setRecallReady(true)
      toast.success(`Bot dispatched · id ${result.bot_id.slice(0, 8)}…`)
      stopPolling()
      pollRef.current = window.setInterval(() => pollBot(result.bot_id), POLL_INTERVAL_MS)
      // Kick off a first poll immediately so the user sees the state.
      pollBot(result.bot_id)
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 503) setRecallReady(false)
        toast.error(e.message)
      }
    } finally {
      setDispatching(false)
    }
  }

  const handleLeaveBot = async () => {
    if (!bot) return
    setLeaving(true)
    try {
      await api.leaveMeetingBot(bot.bot_id)
      toast.success('Asked the bot to leave.')
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message)
    } finally {
      setLeaving(false)
    }
  }

  const handleResetBot = () => {
    stopPolling()
    setBot(null)
    setMeetingUrl('')
  }

  const handleClear = () => {
    setContent('')
    setFilename(null)
    setParsed(null)
    setEditedText('')
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Meetings"
        subtitle="Drop a Zoom or Google Meet transcript and turn it into a Substack brief."
      />

      <div className="px-8 pb-12 grid grid-cols-1 xl:grid-cols-5 gap-5">
        {/* Source */}
        <section className="xl:col-span-3 space-y-4">
          {/* Real-time bot card */}
          <div className="card p-5">
            <div className="flex items-center gap-2 mb-3">
              <span className="w-7 h-7 rounded-md bg-rose-50 border border-rose-200 grid place-items-center">
                <Radio className="w-3.5 h-3.5 text-rose-600" />
              </span>
              <h3 className="text-sm font-semibold text-ink-1">Real-time bot</h3>
              <span className="ml-auto text-[10px] uppercase tracking-widest text-ink-3 font-semibold font-mono">
                Recall.ai
              </span>
            </div>

            {!bot ? (
              <>
                <p className="text-xs text-ink-3 mb-3 leading-relaxed">
                  Paste a Zoom or Google Meet URL. A bot joins, records, and
                  returns a transcript when the call ends.{' '}
                  <span className="text-ink-2 font-medium">
                    Cost: ~$0.50/meeting hour
                  </span>{' '}
                  ·{' '}
                  <span className="text-ink-3">
                    needs <code className="font-mono">RECALL_API_KEY</code> in <code className="font-mono">.env</code>
                  </span>
                </p>
                <div className="flex gap-2">
                  <input
                    type="url"
                    value={meetingUrl}
                    onChange={(e) => setMeetingUrl(e.target.value)}
                    placeholder="https://us02web.zoom.us/j/123456 — or Meet link"
                    className="input flex-1"
                  />
                  <button
                    type="button"
                    onClick={handleDispatchBot}
                    disabled={dispatching || !meetingUrl.trim()}
                    className="btn-primary shrink-0"
                  >
                    {dispatching ? (
                      <>
                        <Spinner /> Dispatching…
                      </>
                    ) : (
                      <>
                        <Video className="w-4 h-4" />
                        Dispatch bot
                      </>
                    )}
                  </button>
                </div>
                {recallReady === false && (
                  <p className="mt-3 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                    Recall.ai not configured. Add{' '}
                    <code className="font-mono">RECALL_API_KEY</code> to{' '}
                    <code className="font-mono">.env</code> and restart the
                    server. Sign up at{' '}
                    <a
                      href="https://www.recall.ai/"
                      className="underline"
                      target="_blank"
                      rel="noreferrer"
                    >
                      recall.ai
                    </a>{' '}
                    (free trial covers a few meetings).
                  </p>
                )}
              </>
            ) : (
              <BotStatusCard
                status={bot}
                leaving={leaving}
                onLeave={handleLeaveBot}
                onReset={handleResetBot}
              />
            )}
          </div>

          {/* Drop zone */}
          <div
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={cn(
              'card p-8 text-center border-2 border-dashed transition',
              dragOver
                ? 'border-ink-1 bg-bg-elevated'
                : 'border-line hover:border-line-strong',
            )}
          >
            <div className="w-12 h-12 mx-auto rounded-xl bg-bg-elevated grid place-items-center mb-3">
              <Upload className="w-5 h-5 text-ink-2" />
            </div>
            <p className="text-sm text-ink-1 font-medium">
              Drop a transcript file
            </p>
            <p className="text-xs text-ink-3 mt-1">
              .vtt (Zoom Cloud) · .srt · .txt (Google Meet copy/paste)
            </p>
            <label className="mt-4 inline-block">
              <input
                type="file"
                accept={ACCEPTED_EXTENSIONS.join(',')}
                onChange={handleFileInput}
                className="hidden"
              />
              <span className="btn-secondary cursor-pointer">
                Choose file
              </span>
            </label>
          </div>

          {/* Paste area */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs uppercase tracking-widest text-ink-3 font-semibold">
                {filename ? `From file · ${filename}` : 'Or paste transcript'}
              </label>
              {(content || filename) && (
                <button onClick={handleClear} className="btn-ghost">
                  <Trash2 className="w-3.5 h-3.5" />
                  Clear
                </button>
              )}
            </div>
            <textarea
              value={content}
              onChange={(e) => {
                setContent(e.target.value)
                setParsed(null)
                setEditedText('')
              }}
              rows={10}
              spellCheck={false}
              placeholder={`Paste a transcript here. Examples:

WEBVTT
00:00:01.000 --> 00:00:05.000
<v Speaker> Welcome to the meeting.

— or —

Speaker Name (00:00)
What they said in the meeting.

— or just plain text dialog.`}
              className="input font-mono text-[13px] leading-6"
              style={{ tabSize: 2 }}
            />
            <button
              type="button"
              onClick={handleParse}
              disabled={parsing || !content.trim()}
              className="btn-primary w-full mt-4"
            >
              {parsing ? (
                <>
                  <Spinner /> Parsing…
                </>
              ) : (
                <>
                  <FileText className="w-4 h-4" />
                  Parse transcript
                </>
              )}
            </button>
          </div>
        </section>

        {/* Result + compose */}
        <aside className="xl:col-span-2 space-y-4">
          {parsed ? (
            <>
              <div className="card p-5">
                <div className="flex items-center gap-2 mb-3">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  <h3 className="text-sm font-semibold text-ink-1">Parsed</h3>
                  <span className="ml-auto text-[10px] uppercase tracking-widest text-ink-3 font-mono">
                    {parsed.detected_format}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-3 text-center">
                  <Stat label="Lines" value={parsed.line_count.toString()} />
                  <Stat label="Words" value={parsed.word_count.toString()} />
                  <Stat
                    label="Speakers"
                    value={parsed.speakers.length.toString()}
                  />
                </div>
                {parsed.speakers.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-line-subtle">
                    <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-ink-3 font-semibold mb-2">
                      <Users className="w-3 h-3" />
                      Speakers
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {parsed.speakers.map((s: string) => (
                        <span
                          key={s}
                          className="pill bg-bg-elevated border border-line-subtle text-ink-2"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="card p-5">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs uppercase tracking-widest text-ink-3 font-semibold">
                    Cleaned transcript
                  </label>
                  <span className="text-[10px] text-ink-4">
                    edit before composing
                  </span>
                </div>
                <textarea
                  value={editedText}
                  onChange={(e) => setEditedText(e.target.value)}
                  rows={10}
                  className="input text-[13px] leading-6"
                />
                <button
                  type="button"
                  onClick={handleCompose}
                  disabled={composing || !editedText.trim()}
                  className="btn-primary w-full mt-4"
                >
                  {composing ? (
                    <>
                      <Spinner /> Composing brief…
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      Compose Brief
                      <ArrowRight className="w-4 h-4 -mr-1" />
                    </>
                  )}
                </button>
              </div>
            </>
          ) : (
            <div className="card p-6">
              <h3 className="text-sm font-semibold text-ink-1 mb-3">
                How this works
              </h3>
              <ol className="space-y-3 text-sm text-ink-2">
                <Step
                  n={1}
                  text="Drop your meeting transcript or paste it directly. Zoom exports .vtt; Google Meet lets you copy from the transcript panel."
                />
                <Step
                  n={2}
                  text="We auto-detect the format, strip timestamps and cue numbers, and preserve speaker names where present."
                />
                <Step
                  n={3}
                  text="Review the cleaned text, edit if needed, then Compose Brief — the same composer used in Studio runs against it."
                />
              </ol>

              <div className="mt-5 pt-4 border-t border-line-subtle">
                <div className="text-[10px] uppercase tracking-widest text-ink-3 font-semibold mb-2 inline-flex items-center gap-1.5">
                  <FileAudio className="w-3 h-3" />
                  Real-time path
                </div>
                <p className="text-xs text-ink-3 leading-relaxed">
                  Or use the Real-time bot card on the left to dispatch a
                  Recall.ai bot to a Zoom or Meet URL — the transcript flows
                  back here automatically when the call ends.
                </p>
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}

const STATE_META: Record<
  BotState,
  { label: string; tone: string; description: string }
> = {
  queued: {
    label: 'Queued',
    tone: 'bg-zinc-100 text-zinc-700 border-zinc-200',
    description: 'Bot accepted. Waiting for it to start joining the call.',
  },
  joining: {
    label: 'Joining call',
    tone: 'bg-amber-50 text-amber-800 border-amber-200',
    description:
      'Bot is connecting to the meeting (or stuck in the waiting room — admit it).',
  },
  in_call: {
    label: 'In call · recording',
    tone: 'bg-rose-50 text-rose-700 border-rose-200',
    description: 'Bot is recording. Press Leave call when the meeting ends.',
  },
  done: {
    label: 'Done',
    tone: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    description: 'Bot left the meeting. Transcript loaded into the editor below.',
  },
  error: {
    label: 'Error',
    tone: 'bg-red-50 text-red-700 border-red-200',
    description: 'Recall.ai reported an error. See the message below.',
  },
}

function BotStatusCard({
  status,
  leaving,
  onLeave,
  onReset,
}: {
  status: BotStatus
  leaving: boolean
  onLeave: () => void
  onReset: () => void
}) {
  const meta = STATE_META[status.state]
  const showLeave =
    status.state === 'queued' || status.state === 'joining' || status.state === 'in_call'
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className={cn('pill border', meta.tone)}>
          {(status.state === 'in_call' || status.state === 'joining') && (
            <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
          )}
          {meta.label}
        </span>
        <span className="text-[10px] font-mono text-ink-4 truncate">
          id {status.bot_id.slice(0, 8)}…
        </span>
        <div className="ml-auto flex items-center gap-1">
          {showLeave && (
            <button
              type="button"
              onClick={onLeave}
              disabled={leaving}
              className="btn-ghost text-rose-600"
              title="Ask the bot to leave the call now"
            >
              {leaving ? <Spinner /> : <Square className="w-3.5 h-3.5" />}
              Leave call
            </button>
          )}
          <button type="button" onClick={onReset} className="btn-ghost">
            Reset
          </button>
        </div>
      </div>
      <p className="text-xs text-ink-3 leading-relaxed">{meta.description}</p>
      {status.error && (
        <p className="mt-3 text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2 font-mono break-words">
          {status.error}
        </p>
      )}
      {status.raw_status_codes.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {status.raw_status_codes.slice(-5).map((code, i) => (
            <span
              key={`${code}-${i}`}
              className="pill bg-bg-elevated border border-line-subtle text-ink-3 text-[10px] font-mono"
            >
              {code}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-line-subtle bg-bg-elevated/40 px-2 py-3">
      <div className="text-base font-semibold text-ink-1">{value}</div>
      <div className="text-[10px] uppercase tracking-widest text-ink-3 font-semibold">
        {label}
      </div>
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
