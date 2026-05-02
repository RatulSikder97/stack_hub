import type { PostStatus } from '../lib/types'
import { cn } from '../lib/utils'

const statusStyles: Record<PostStatus, string> = {
  idea: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
  brief: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  drafting: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  ai_tells_pass: 'bg-violet-500/10 text-violet-400 border-violet-500/20',
  editing: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  retention_check: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
  scheduled: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
  published: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
}

export function StatusBadge({ status }: { status: PostStatus }) {
  return (
    <span className={cn('pill border', statusStyles[status])}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}
