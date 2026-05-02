import { useEffect, useState } from 'react'
import { PageHeader } from '../components/PageHeader'
import type { StatusInfo } from '../lib/types'
import { api } from '../lib/api'
import { CheckCircle2, Cpu, KeyRound, Clock, Building2 } from 'lucide-react'

export function SettingsPage() {
  const [status, setStatus] = useState<StatusInfo | null>(null)
  useEffect(() => {
    api.status().then(setStatus).catch(() => undefined)
  }, [])

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Settings"
        subtitle="Server-side configuration. Edit `.env` and restart the server to change provider, model, or brand."
      />
      <div className="px-8 pb-12 max-w-4xl space-y-5">
        <section className="card p-6">
          <h3 className="text-sm font-semibold text-ink-1 mb-4">Provider</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
            <Field
              icon={Cpu}
              label="Provider"
              value={status?.provider ?? '…'}
              mono
            />
            <Field
              icon={Cpu}
              label="Model"
              value={status?.model ?? '…'}
              mono
            />
            <Field
              icon={KeyRound}
              label="API key"
              value={
                status?.has_active_provider_key ? (
                  <span className="inline-flex items-center gap-1.5 text-emerald-400">
                    <CheckCircle2 className="w-3.5 h-3.5" /> set
                  </span>
                ) : (
                  <span className="text-amber-400">missing</span>
                )
              }
            />
            <Field
              icon={Building2}
              label="Brand"
              value={status?.brand_name ?? '…'}
            />
            <Field
              icon={Clock}
              label="Cadence"
              value={status ? `${status.cadence_days} days` : '…'}
            />
          </div>
        </section>

        <section className="card p-6 text-sm">
          <h3 className="text-sm font-semibold text-ink-1 mb-3">How to change settings</h3>
          <ol className="space-y-2 text-ink-2 list-decimal list-inside">
            <li>
              Edit <code className="font-mono bg-bg-elevated px-1.5 py-0.5 rounded text-pink-300">.env</code> in the project root.
            </li>
            <li>
              Set <code className="font-mono">LLM_PROVIDER</code> to <code>openai</code>, <code>gemini</code>, <code>anthropic</code>, or <code>novita</code>.
            </li>
            <li>
              Set the corresponding <code className="font-mono">*_API_KEY</code> and <code className="font-mono">*_MODEL</code>.
            </li>
            <li>
              Brand and cadence live in <code className="font-mono">data/config.json</code>.
            </li>
            <li>
              Restart the server: <code className="font-mono bg-bg-elevated px-1.5 py-0.5 rounded text-pink-300">python scripts/serve.py</code>.
            </li>
          </ol>
        </section>

        <section className="card p-6 text-sm">
          <h3 className="text-sm font-semibold text-ink-1 mb-3">Model recommendations</h3>
          <div className="space-y-2 text-ink-2">
            <div>
              <span className="text-ink-1 font-medium">Gemini free tier:</span>{' '}
              <code className="font-mono">gemini-2.5-flash-lite</code> for highest RPM,{' '}
              <code className="font-mono">gemini-2.5-flash</code> for better quality.
            </div>
            <div>
              <span className="text-ink-1 font-medium">OpenAI:</span>{' '}
              <code className="font-mono">gpt-4.1</code> via Responses API.
            </div>
            <div>
              <span className="text-ink-1 font-medium">Anthropic:</span>{' '}
              <code className="font-mono">claude-opus-4-7</code> for voice-heavy work.
            </div>
            <div>
              <span className="text-ink-1 font-medium">Novita:</span>{' '}
              <code className="font-mono">meta-llama/llama-3.3-70b-instruct</code> via OpenAI-compatible API.
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}

function Field({
  icon: Icon,
  label,
  value,
  mono,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: React.ReactNode
  mono?: boolean
}) {
  return (
    <div className="flex items-center gap-3 px-3.5 py-3 rounded-xl bg-bg-elevated border border-line-subtle">
      <Icon className="w-4 h-4 text-ink-3" />
      <div className="flex-1 min-w-0">
        <div className="text-[10px] uppercase tracking-widest text-ink-3 font-semibold">
          {label}
        </div>
        <div
          className={`text-sm text-ink-1 truncate ${mono ? 'font-mono' : ''}`}
        >
          {value}
        </div>
      </div>
    </div>
  )
}
