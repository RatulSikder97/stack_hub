import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { CheckCircle2, AlertTriangle, Info, X } from 'lucide-react'
import { cn } from '../lib/utils'

type ToastKind = 'success' | 'error' | 'info'

interface Toast {
  id: number
  kind: ToastKind
  message: string
  ttl?: number
}

interface ToastApi {
  push: (kind: ToastKind, message: string, ttlMs?: number) => void
  success: (message: string) => void
  error: (message: string) => void
  info: (message: string) => void
}

const ToastContext = createContext<ToastApi | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const idRef = useRef(0)

  const push = useCallback((kind: ToastKind, message: string, ttlMs = 4500) => {
    const id = ++idRef.current
    setToasts((prev) => [...prev, { id, kind, message, ttl: ttlMs }])
  }, [])

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const api = useMemo<ToastApi>(
    () => ({
      push,
      success: (m) => push('success', m),
      error: (m) => push('error', m, 6500),
      info: (m) => push('info', m),
    }),
    [push],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
        {toasts.map((t) => (
          <ToastView key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

function ToastView({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  useEffect(() => {
    if (!toast.ttl) return
    const handle = setTimeout(onDismiss, toast.ttl)
    return () => clearTimeout(handle)
  }, [toast, onDismiss])

  const Icon = toast.kind === 'success' ? CheckCircle2 : toast.kind === 'error' ? AlertTriangle : Info
  const accent =
    toast.kind === 'success'
      ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/8'
      : toast.kind === 'error'
        ? 'text-red-400 border-red-500/30 bg-red-500/8'
        : 'text-violet-400 border-violet-500/30 bg-violet-500/8'

  return (
    <div
      className={cn(
        'card flex items-start gap-3 px-4 py-3 animate-slide-up min-w-[280px]',
        accent,
      )}
    >
      <Icon className="w-4 h-4 mt-0.5 shrink-0" />
      <div className="flex-1 text-sm text-ink-1 leading-snug">{toast.message}</div>
      <button onClick={onDismiss} className="text-ink-3 hover:text-ink-1 transition shrink-0">
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
