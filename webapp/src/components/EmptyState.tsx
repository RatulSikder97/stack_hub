import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description?: string
  action?: ReactNode
}

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center text-center py-16 px-6">
      {Icon && (
        <div className="w-14 h-14 rounded-2xl bg-bg-elevated border border-line-subtle flex items-center justify-center mb-4">
          <Icon className="w-6 h-6 text-ink-3" />
        </div>
      )}
      <h3 className="text-base font-semibold text-ink-1">{title}</h3>
      {description && <p className="text-sm text-ink-3 mt-2 max-w-md">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
