import {
  ArrowRight,
  CheckCircle2,
  FileAudio,
  FileText,
  Sparkles,
  Trash2,
  Upload,
  Users,
} from 'lucide-react'
import { useState, type ChangeEvent, type DragEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { PageHeader } from '../components/PageHeader'
import { Spinner } from '../components/Spinner'
import { useToast } from '../components/ToastProvider'
import { ApiError, RateLimitedError, api, type TranscriptParseResult } from '../lib/api'
import { cn } from '../lib/utils'

const ACCEPTED_EXTENSIONS = ['.vtt', '.srt', '.txt', '.md']

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
                  Coming next
                </div>
                <p className="text-xs text-ink-3 leading-relaxed">
                  Real-time bot integration via Recall.ai (paste meeting URL,
                  bot joins and returns a transcript when it ends) is the
                  next iteration on top of this same composer.
                </p>
              </div>
            </div>
          )}
        </aside>
      </div>
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
