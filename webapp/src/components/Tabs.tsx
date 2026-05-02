import { useState, type ReactNode } from 'react'
import { cn } from '../lib/utils'

export interface TabDef {
  id: string
  label: string
  content: ReactNode
}

interface TabsProps {
  tabs: TabDef[]
  defaultTab?: string
  controlledTab?: string
  onTabChange?: (id: string) => void
}

export function Tabs({ tabs, defaultTab, controlledTab, onTabChange }: TabsProps) {
  const [internal, setInternal] = useState(defaultTab ?? tabs[0]?.id)
  const active = controlledTab ?? internal
  const handle = (id: string) => {
    if (controlledTab === undefined) setInternal(id)
    onTabChange?.(id)
  }
  const activeTab = tabs.find((t) => t.id === active) ?? tabs[0]
  return (
    <div className="flex flex-col h-full">
      <div className="border-b border-line-subtle px-2 flex items-center gap-1 overflow-x-auto">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => handle(t.id)}
            className={cn('tab-trigger', t.id === active && 'active')}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="flex-1 min-h-0">{activeTab?.content}</div>
    </div>
  )
}
