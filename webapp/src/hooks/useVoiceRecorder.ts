import { useCallback, useEffect, useRef, useState } from 'react'

type StudioState = 'ready' | 'live' | 'paused'

interface VoiceRecorderApi {
  state: StudioState
  transcript: string
  setTranscript: (value: string) => void
  durationSec: number
  start: () => Promise<void>
  stop: () => void
  toggle: () => Promise<void>
  isSupported: boolean
  canvasRef: React.RefObject<HTMLCanvasElement | null>
}

const PERIOD_PAUSE_MS = 700
const PARAGRAPH_PAUSE_MS = 1800

/**
 * Wires the Web Speech API + Web Audio API into a single hook that:
 *
 * - transcribes speech in the configured language
 * - inserts a period (or । for Bengali/Hindi) after a short pause
 * - inserts a paragraph break after a longer pause
 * - drives a canvas-based level meter when canvasRef is attached
 * - exposes a single live `transcript` string callers can edit
 */
export function useVoiceRecorder(lang: string): VoiceRecorderApi {
  const [state, setState] = useState<StudioState>('ready')
  const [transcript, setTranscriptState] = useState('')
  const [durationSec, setDurationSec] = useState(0)

  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const finalTextRef = useRef('')
  const interimTextRef = useRef('')
  const pausePeriodRef = useRef<number | null>(null)
  const pauseParagraphRef = useRef<number | null>(null)

  const audioCtxRef = useRef<AudioContext | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const visualizerRef = useRef<number | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

  const startedAtRef = useRef(0)
  const timerRef = useRef<number | null>(null)
  const langRef = useRef(lang)
  langRef.current = lang
  const stateRef = useRef<StudioState>('ready')
  stateRef.current = state

  const setTranscript = useCallback((value: string) => {
    finalTextRef.current = value
    interimTextRef.current = ''
    setTranscriptState(value)
  }, [])

  const renderTranscript = useCallback(() => {
    const sep =
      finalTextRef.current.endsWith(' ') || finalTextRef.current.endsWith('\n') ? '' : ' '
    const next =
      finalTextRef.current + (interimTextRef.current ? sep + interimTextRef.current : '')
    setTranscriptState(next)
  }, [])

  const clearPauseTimers = useCallback(() => {
    if (pausePeriodRef.current) clearTimeout(pausePeriodRef.current)
    if (pauseParagraphRef.current) clearTimeout(pauseParagraphRef.current)
    pausePeriodRef.current = null
    pauseParagraphRef.current = null
  }, [])

  const appendPeriod = useCallback((text: string): string => {
    const trimmed = text.replace(/\s+$/, '')
    if (!trimmed) return text
    if (/[.!?।॥]\s*$/.test(trimmed)) return trimmed + ' '
    const lower = (langRef.current || '').toLowerCase()
    const punct = lower.startsWith('bn') || lower.startsWith('hi') ? '।' : '.'
    return trimmed + punct + ' '
  }, [])

  const appendParagraphBreak = useCallback((text: string): string => {
    const trimmed = text.replace(/\s+$/, '')
    if (!trimmed) return text
    if (trimmed.endsWith('\n\n')) return trimmed
    return trimmed + '\n\n'
  }, [])

  const schedulePauseHandlers = useCallback(() => {
    clearPauseTimers()
    pausePeriodRef.current = window.setTimeout(() => {
      finalTextRef.current = appendPeriod(finalTextRef.current)
      renderTranscript()
      setState('paused')
    }, PERIOD_PAUSE_MS)
    pauseParagraphRef.current = window.setTimeout(() => {
      finalTextRef.current = appendParagraphBreak(finalTextRef.current)
      renderTranscript()
    }, PARAGRAPH_PAUSE_MS)
  }, [appendPeriod, appendParagraphBreak, clearPauseTimers, renderTranscript])

  // ---- Visualizer ----
  const drawVisualizer = useCallback(() => {
    const canvas = canvasRef.current
    const analyser = analyserRef.current
    if (!canvas || !analyser) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const W = canvas.width
    const H = canvas.height
    const cx = W / 2
    const cy = H / 2
    const buf = new Uint8Array(analyser.frequencyBinCount)

    const tick = () => {
      visualizerRef.current = requestAnimationFrame(tick)
      const a = analyserRef.current
      if (!a) return
      a.getByteFrequencyData(buf)
      let sum = 0
      for (let i = 0; i < buf.length; i++) sum += buf[i]
      const avg = sum / buf.length / 255

      ctx.clearRect(0, 0, W, H)
      const isLive = stateRef.current === 'live'
      const color = isLive ? '239, 68, 68' : '167, 139, 250'

      // Breathing rings
      for (let i = 0; i < 4; i++) {
        const t = (Date.now() / 1000 + i * 0.4) % 1
        const radius = 56 + t * 60 + avg * 28
        const alpha = (1 - t) * (0.18 + avg * 0.5)
        ctx.beginPath()
        ctx.arc(cx, cy, radius, 0, Math.PI * 2)
        ctx.strokeStyle = `rgba(${color}, ${alpha.toFixed(3)})`
        ctx.lineWidth = 1.5
        ctx.stroke()
      }
      // Frequency bars in a circle
      const bars = 56
      for (let i = 0; i < bars; i++) {
        const angle = (i / bars) * Math.PI * 2 - Math.PI / 2
        const v = buf[Math.floor((i / bars) * buf.length)] / 255
        const inner = 50
        const outer = inner + 4 + v * 30
        const x1 = cx + Math.cos(angle) * inner
        const y1 = cy + Math.sin(angle) * inner
        const x2 = cx + Math.cos(angle) * outer
        const y2 = cy + Math.sin(angle) * outer
        ctx.beginPath()
        ctx.moveTo(x1, y1)
        ctx.lineTo(x2, y2)
        ctx.strokeStyle = `rgba(${color}, ${(0.2 + v * 0.7).toFixed(3)})`
        ctx.lineWidth = 2
        ctx.lineCap = 'round'
        ctx.stroke()
      }
    }
    tick()
  }, [])

  const startVisualizer = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
      audioCtxRef.current = ctx
      const source = ctx.createMediaStreamSource(stream)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      source.connect(analyser)
      analyserRef.current = analyser
      drawVisualizer()
    } catch {
      /* mic not granted — silent, visualizer just won't run */
    }
  }, [drawVisualizer])

  const stopVisualizer = useCallback(() => {
    if (visualizerRef.current) cancelAnimationFrame(visualizerRef.current)
    visualizerRef.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    audioCtxRef.current?.close().catch(() => undefined)
    audioCtxRef.current = null
    analyserRef.current = null
    const canvas = canvasRef.current
    if (canvas) {
      const ctx = canvas.getContext('2d')
      ctx?.clearRect(0, 0, canvas.width, canvas.height)
    }
  }, [])

  // ---- Timer ----
  const startTimer = useCallback(() => {
    startedAtRef.current = Date.now()
    setDurationSec(0)
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = window.setInterval(() => {
      setDurationSec(Math.floor((Date.now() - startedAtRef.current) / 1000))
    }, 250)
  }, [])
  const stopTimer = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = null
  }, [])

  const stop = useCallback(() => {
    recognitionRef.current?.stop()
  }, [])

  const start = useCallback(async () => {
    const SR =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition
    if (!SR) return
    if (recognitionRef.current) return

    const recognition: SpeechRecognition = new SR()
    recognition.lang = lang === 'auto' ? 'bn-BD' : lang
    recognition.continuous = true
    recognition.interimResults = true

    recognitionRef.current = recognition

    recognition.onstart = () => {
      setState('live')
      startTimer()
      startVisualizer()
    }
    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript
        if (event.results[i].isFinal) {
          finalTextRef.current += transcript
        } else {
          interim += transcript
        }
      }
      interimTextRef.current = interim
      renderTranscript()
      setState('live')
      schedulePauseHandlers()
    }
    recognition.onerror = () => {
      /* ignore — onend will tidy up */
    }
    recognition.onend = () => {
      clearPauseTimers()
      stopTimer()
      stopVisualizer()
      setState('ready')
      recognitionRef.current = null
    }

    try {
      recognition.start()
    } catch {
      recognitionRef.current = null
    }
  }, [
    clearPauseTimers,
    lang,
    renderTranscript,
    schedulePauseHandlers,
    startTimer,
    startVisualizer,
    stopTimer,
    stopVisualizer,
  ])

  const toggle = useCallback(async () => {
    if (recognitionRef.current) stop()
    else await start()
  }, [start, stop])

  useEffect(
    () => () => {
      stop()
      stopVisualizer()
      stopTimer()
    },
    [stop, stopTimer, stopVisualizer],
  )

  const isSupported = !!(
    (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
  )

  return {
    state,
    transcript,
    setTranscript,
    durationSec,
    start,
    stop,
    toggle,
    isSupported,
    canvasRef,
  }
}
