import { Bell, BookOpen, MessageSquare, PanelLeft, Sparkles } from 'lucide-react'
import { useLocation } from 'react-router-dom'

const ROUTE_TITLES: Array<[string, string]> = [
  ['/home', 'Home'],
  ['/studio', 'Studio'],
  ['/library', 'Library'],
  ['/translate', 'Translate'],
  ['/settings', 'Settings'],
]

function titleFor(pathname: string): string {
  if (pathname.startsWith('/library/')) return 'Post detail'
  for (const [prefix, label] of ROUTE_TITLES) {
    if (pathname.startsWith(prefix)) return label
  }
  return ''
}

export function TopBar() {
  const location = useLocation()
  const title = titleFor(location.pathname)

  return (
    <header className="h-14 sticky top-0 z-10 bg-bg-base/85 backdrop-blur border-b border-line-subtle flex items-center justify-between px-6">
      <div className="flex items-center gap-3 min-w-0">
        <button type="button" className="btn-ghost p-2" title="Toggle sidebar">
          <PanelLeft className="w-4 h-4" />
        </button>
        <h1 className="text-base font-semibold text-ink-1 truncate">{title}</h1>
      </div>

      <div className="flex items-center gap-1">
        <a
          href="https://github.com/anthropics/claude-code"
          target="_blank"
          rel="noreferrer"
          className="btn-secondary !py-1.5 !px-3 text-xs"
        >
          <MessageSquare className="w-3.5 h-3.5" />
          Feedback
        </a>
        <a
          href="/api/docs"
          target="_blank"
          rel="noreferrer"
          className="btn-secondary !py-1.5 !px-3 text-xs"
        >
          <BookOpen className="w-3.5 h-3.5" />
          API Docs
        </a>
        <button type="button" className="btn-ghost p-2" title="Tips">
          <Sparkles className="w-4 h-4" />
        </button>
        <button type="button" className="btn-ghost p-2 relative" title="Notifications">
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-2 w-1.5 h-1.5 rounded-full bg-rose-500" />
        </button>
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-400 to-fuchsia-500 grid place-items-center text-white text-xs font-bold ml-1">
          R
        </div>
      </div>
    </header>
  )
}
