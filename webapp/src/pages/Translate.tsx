import { Languages } from 'lucide-react'
import { useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import { Spinner } from '../components/Spinner'
import { useToast } from '../components/ToastProvider'
import { ApiError, RateLimitedError, api } from '../lib/api'
import type { TranslationResult } from '../lib/types'

const TARGETS = [
  { value: 'en', label: 'English' },
  { value: 'bn', label: 'বাংলা' },
  { value: 'hi', label: 'हिन्दी' },
  { value: 'es', label: 'Español' },
  { value: 'fr', label: 'Français' },
]

export function TranslatePage() {
  const toast = useToast()
  const [text, setText] = useState('')
  const [target, setTarget] = useState('en')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<TranslationResult | null>(null)

  const handleTranslate = async () => {
    const value = text.trim()
    if (!value) {
      toast.error('Enter some text first.')
      return
    }
    setBusy(true)
    try {
      const data = await api.translate(value, target)
      setResult(data)
    } catch (e) {
      if (e instanceof RateLimitedError) {
        toast.error(`Rate limited. Retry in ~${e.retryAfter}s.`)
      } else if (e instanceof ApiError) {
        toast.error(e.message)
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Translate"
        subtitle="Quick multilingual translator over the same provider as the rest of the pipeline."
      />
      <div className="px-8 pb-12 space-y-5 max-w-4xl">
        <section className="card p-6">
          <div className="flex items-center justify-between mb-3">
            <label className="text-[10px] uppercase tracking-widest text-ink-3 font-semibold">
              Source
            </label>
            <div className="flex items-center gap-2">
              <select
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                className="text-xs bg-bg-elevated border border-line-subtle rounded-md px-2 py-1 text-ink-1 focus:outline-none focus:border-brand"
              >
                {TARGETS.map((t) => (
                  <option key={t.value} value={t.value}>
                    → {t.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={handleTranslate}
                disabled={busy}
                className="btn-primary"
              >
                {busy ? (
                  <>
                    <Spinner /> Translating…
                  </>
                ) : (
                  <>
                    <Languages className="w-4 h-4" />
                    Translate
                  </>
                )}
              </button>
            </div>
          </div>
          <textarea
            rows={5}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="যে কোন ভাষায় টেক্সট লিখুন — translation appears below."
            className="input"
          />
        </section>

        {result && (
          <section className="card p-6 animate-slide-up">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-ink-1">
                {result.needed_translation
                  ? `${result.source_language} → ${result.target_language}`
                  : `Already in ${result.target_language}`}
              </h3>
              <span className="text-[10px] uppercase tracking-widest text-ink-3 font-semibold font-mono">
                {result.needed_translation ? 'translated' : 'no translation needed'}
              </span>
            </div>
            {result.needed_translation ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-ink-3 font-semibold mb-1.5">
                    Original ({result.source_language})
                  </div>
                  <div className="rounded-xl border border-line-subtle bg-bg-elevated/60 p-4 text-sm whitespace-pre-wrap leading-relaxed text-ink-1">
                    {result.original_text}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-brand font-semibold mb-1.5">
                    {result.target_language}
                  </div>
                  <div className="rounded-xl border border-brand/30 bg-brand/8 p-4 text-sm whitespace-pre-wrap leading-relaxed text-ink-1">
                    {result.translated_text}
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-line-subtle bg-bg-elevated/60 p-4 text-sm whitespace-pre-wrap leading-relaxed text-ink-1">
                {result.original_text}
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  )
}
