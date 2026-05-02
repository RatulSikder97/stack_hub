import { cn } from '../lib/utils'

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'inline-block w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin align-[-2px]',
        className,
      )}
    />
  )
}
