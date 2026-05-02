import {
  AlertCircle,
  FileText,
  Mic,
  Save,
  Search,
  Settings as SettingsIcon,
  Sparkles,
  Trash2,
  Wand2,
} from 'lucide-react'
import { useEffect, useMemo, useState, type ComponentType } from 'react'
import { PageHeader } from '../components/PageHeader'
import { Spinner } from '../components/Spinner'
import { useToast } from '../components/ToastProvider'
import { ApiError, api, type AdminFile, type AdminFileContent } from '../lib/api'
import { cn, formatRelativeDate } from '../lib/utils'

interface CategoryDef {
  id: string
  label: string
  icon: ComponentType<{ className?: string }>
  description: string
}

const CATEGORIES: CategoryDef[] = [
  { id: 'voice', label: 'Voice', icon: Mic, description: 'Brand voice, promise, and AI tells.' },
  { id: 'prompts', label: 'Prompts', icon: Sparkles, description: 'Master + detector prompts.' },
  { id: 'libraries', label: 'Libraries', icon: Wand2, description: 'Hook + structure menus.' },
  { id: 'briefs', label: 'Briefs', icon: FileText, description: 'Brief template.' },
  { id: 'corpus', label: 'Corpus', icon: Search, description: 'Source posts per writer.' },
  { id: 'config', label: 'Config', icon: SettingsIcon, description: 'Brand + cadence (JSON).' },
]

export function AdminPage() {
  const toast = useToast()
  const [files, setFiles] = useState<AdminFile[] | null>(null)
  const [activeCategory, setActiveCategory] = useState<string>('voice')
  const [activePath, setActivePath] = useState<string | null>(null)
  const [openFile, setOpenFile] = useState<AdminFileContent | null>(null)
  const [draft, setDraft] = useState<string>('')
  const [loadingFile, setLoadingFile] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const refreshList = async () => {
    try {
      const list = await api.adminListFiles()
      setFiles(list)
      // Auto-pick the first item in the active category if none selected.
      if (!activePath) {
        const first = list.find((f) => f.category === activeCategory)
        if (first) loadFile(first.path)
      }
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message)
      else toast.error('Failed to load admin files.')
    }
  }

  const loadFile = async (path: string) => {
    setLoadingFile(true)
    setActivePath(path)
    try {
      const file = await api.adminReadFile(path)
      setOpenFile(file)
      setDraft(file.content)
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message)
      else toast.error('Failed to load file.')
    } finally {
      setLoadingFile(false)
    }
  }

  useEffect(() => {
    refreshList()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const filesByCategory = useMemo(() => {
    const map = new Map<string, AdminFile[]>()
    ;(files || []).forEach((f) => {
      const arr = map.get(f.category) ?? []
      arr.push(f)
      map.set(f.category, arr)
    })
    return map
  }, [files])

  const dirty = openFile !== null && draft !== openFile.content

  const handleSave = async () => {
    if (!openFile) return
    setSaving(true)
    try {
      await api.adminWriteFile(openFile.path, draft)
      const refreshed = await api.adminReadFile(openFile.path)
      setOpenFile(refreshed)
      setDraft(refreshed.content)
      // Refresh list (sizes/timestamps changed).
      const list = await api.adminListFiles()
      setFiles(list)
      toast.success(`Saved ${openFile.path}`)
    } catch (e) {
      if (e instanceof ApiError) toast.error(`Save failed: ${e.message}`)
      else toast.error('Save failed.')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    if (!openFile) return
    setDraft(openFile.content)
  }

  const handleDelete = async () => {
    if (!openFile || !openFile.deletable) return
    if (!confirm(`Delete ${openFile.path}? This cannot be undone.`)) return
    setDeleting(true)
    try {
      await api.adminDeleteFile(openFile.path)
      setOpenFile(null)
      setActivePath(null)
      setDraft('')
      const list = await api.adminListFiles()
      setFiles(list)
      toast.success('File deleted.')
    } catch (e) {
      if (e instanceof ApiError) toast.error(`Delete failed: ${e.message}`)
    } finally {
      setDeleting(false)
    }
  }

  const isJson = openFile?.path.endsWith('.json')

  return (
    <div className="animate-fade-in">
      <PageHeader
        title="Admin"
        subtitle="Edit voice, prompts, libraries, brief template, corpus, and config."
        actions={
          <div className="flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 px-3 py-1.5 rounded-lg">
            <AlertCircle className="w-3.5 h-3.5" />
            Admin role · changes take effect immediately
          </div>
        }
      />

      <div className="px-8 pb-12 grid grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)] gap-5">
        {/* File browser */}
        <aside className="card p-2 self-start">
          {CATEGORIES.map((cat) => {
            const list = filesByCategory.get(cat.id) || []
            const expanded = activeCategory === cat.id || list.length > 0
            return (
              <div key={cat.id} className="mb-1">
                <button
                  type="button"
                  onClick={() => setActiveCategory(cat.id)}
                  className={cn(
                    'w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition',
                    activeCategory === cat.id
                      ? 'bg-bg-active text-ink-1'
                      : 'text-ink-2 hover:bg-bg-hover',
                  )}
                >
                  <cat.icon className="w-4 h-4" />
                  <span>{cat.label}</span>
                  <span className="ml-auto text-[10px] text-ink-4 font-mono">
                    {list.length}
                  </span>
                </button>
                {expanded && list.length > 0 && (
                  <div className="mt-0.5 mb-2 ml-2 pl-3 border-l border-line-subtle space-y-0.5">
                    {list.map((f) => (
                      <button
                        key={f.path}
                        type="button"
                        onClick={() => loadFile(f.path)}
                        className={cn(
                          'w-full text-left px-2.5 py-1.5 rounded-md text-xs transition',
                          activePath === f.path
                            ? 'bg-ink-1 text-white'
                            : 'text-ink-2 hover:bg-bg-elevated',
                        )}
                        title={f.path}
                      >
                        <div className="font-medium truncate">{f.label}</div>
                        <div
                          className={cn(
                            'text-[10px] font-mono truncate mt-0.5',
                            activePath === f.path ? 'text-white/70' : 'text-ink-4',
                          )}
                        >
                          {f.path}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </aside>

        {/* Editor */}
        <section className="card flex flex-col min-h-[640px]">
          {!openFile ? (
            <div className="flex-1 grid place-items-center text-sm text-ink-3 italic">
              {loadingFile ? 'Loading…' : 'Select a file from the left.'}
            </div>
          ) : (
            <>
              <div className="border-b border-line-subtle px-5 py-3.5 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-ink-1 truncate">
                    {openFile.path}
                  </div>
                  <div className="text-xs text-ink-3 mt-0.5 flex items-center gap-2">
                    <span className="capitalize">{openFile.category}</span>
                    <span className="text-ink-5">·</span>
                    <span>{openFile.size} bytes</span>
                    <span className="text-ink-5">·</span>
                    <span>updated {formatRelativeDate(openFile.modified_at)}</span>
                    {dirty && (
                      <span className="ml-1 inline-flex items-center gap-1 text-amber-600">
                        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                        unsaved
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  {openFile.deletable && (
                    <button
                      type="button"
                      onClick={handleDelete}
                      disabled={deleting}
                      className="btn-ghost text-red-600 hover:bg-red-50"
                      title="Delete file"
                    >
                      {deleting ? <Spinner /> : <Trash2 className="w-3.5 h-3.5" />}
                      Delete
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={handleReset}
                    disabled={!dirty}
                    className="btn-secondary !py-1.5 !px-3"
                  >
                    Reset
                  </button>
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={!dirty || saving}
                    className="btn-primary !py-1.5 !px-3"
                  >
                    {saving ? <Spinner /> : <Save className="w-3.5 h-3.5" />}
                    Save
                  </button>
                </div>
              </div>

              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                spellCheck={false}
                className={cn(
                  'flex-1 px-5 py-4 bg-transparent border-0 resize-none focus:outline-none leading-6',
                  isJson
                    ? 'font-mono text-[13px] text-ink-1'
                    : 'font-mono text-[13px] text-ink-1',
                )}
                style={{ tabSize: 2 }}
              />
            </>
          )}
        </section>
      </div>
    </div>
  )
}
