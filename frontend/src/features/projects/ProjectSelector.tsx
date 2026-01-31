import { useState, useRef, useEffect } from 'react'
import { FolderOpen, Loader2, Database, ChevronDown, RotateCcw, Trash2 } from 'lucide-react'
import { useWorkspace } from '../workspace/useWorkspace'
import { FolderPicker } from '../workspace/FolderPicker'
import { useToast } from '../toast/ToastContext'

export function ProjectSelector() {
  const { show: showToast } = useToast()
  const {
    workspace,
    loading,
    fetchWorkspace,
    openFolder,
    indexWorkspaceStream,
    clearIndex,
  } = useWorkspace()

  const [showPicker, setShowPicker] = useState(false)
  const [showIndexMenu, setShowIndexMenu] = useState(false)
  const [indexing, setIndexing] = useState(false)
  const [indexProgress, setIndexProgress] = useState<number | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!showIndexMenu) return
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowIndexMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showIndexMenu])

  const handleOpenFolder = async (path: string) => {
    setShowPicker(false)
    try {
      await openFolder(path)
      showToast(`Открыта папка: ${path.split('/').pop() || path}`, 'success')
      fetchWorkspace()
      window.dispatchEvent(new CustomEvent('workspace-changed'))
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Что-то пошло не так', 'error')
    }
  }

  const runIndex = async (incremental: boolean) => {
    setShowIndexMenu(false)
    setIndexing(true)
    setIndexProgress(0)
    try {
      const result = await indexWorkspaceStream((progress) => {
        setIndexProgress(progress)
      }, incremental)
      setIndexProgress(100)
      const stats = result?.stats ?? {}
      const inc = stats?.incremental
      const msg = inc
        ? `Индекс: +${stats?.files_added ?? 0} новых, ~${stats?.files_updated ?? 0} изменённых, -${stats?.files_deleted ?? 0} удалённых. Всего: ${stats?.total_chunks ?? 0} чанков`
        : `Полная переиндексация: ${stats?.files_found ?? 0} файлов, ${stats?.total_chunks ?? 0} чанков`
      showToast(msg, 'success')
      fetchWorkspace()
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Что-то пошло не так', 'error')
    } finally {
      setIndexing(false)
      setIndexProgress(null)
    }
  }

  const handleIndex = () => runIndex(true)

  const handleFullReindex = () => runIndex(false)

  const handleClear = async () => {
    setShowIndexMenu(false)
    try {
      await clearIndex()
      showToast('Индекс очищен', 'success')
      fetchWorkspace()
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Что-то пошло не так', 'error')
    }
  }

  return (
    <div className="project-selector">
      <div className="project-selector__header">
        <span className="project-selector__title">Index</span>
        <div className="project-selector__actions" ref={menuRef}>
          <button
            type="button"
            className="project-selector__action"
            onClick={() => {
              setShowIndexMenu(false)
              setShowPicker(true)
            }}
            title="Открыть папку"
          >
            <FolderOpen size={14} />
          </button>
          <button
            type="button"
            className="project-selector__action"
            onClick={handleIndex}
            disabled={indexing}
            title="Обновить индекс (инкрементально)"
          >
            {indexing ? (
              <Loader2 size={14} className="icon-spin" />
            ) : (
              <Database size={14} />
            )}
          </button>
          <button
            type="button"
            className="project-selector__action project-selector__action--menu"
            onClick={() => setShowIndexMenu((v) => !v)}
            disabled={indexing}
            title="Дополнительные действия"
          >
            <ChevronDown size={14} />
          </button>
          {showIndexMenu && (
            <div className="project-selector__dropdown">
              <button
                type="button"
                className="project-selector__dropdown-item"
                onClick={handleFullReindex}
              >
                <RotateCcw size={14} />
                Полная переиндексация
              </button>
              <button
                type="button"
                className="project-selector__dropdown-item project-selector__dropdown-item--danger"
                onClick={handleClear}
              >
                <Trash2 size={14} />
                Очистить индекс
              </button>
            </div>
          )}
        </div>
      </div>

      {indexing && indexProgress !== null && (
        <div className="project-selector__progress">
          <div className="project-selector__progress-bar">
            <div
              className="project-selector__progress-fill"
              style={{ width: `${indexProgress}%` }}
            />
          </div>
          <span className="project-selector__progress-text">{indexProgress}%</span>
        </div>
      )}
      <div className="project-selector__content">
        {loading ? (
          <div className="project-selector__loading">Загрузка...</div>
        ) : workspace ? (
          <div className="project-selector__workspace">
            <div className="project-selector__name">{workspace.name}</div>
            <div className="project-selector__path">{workspace.path}</div>
          </div>
        ) : (
          <div className="project-selector__empty">
            Откройте папку для индексации RAG
          </div>
        )}
      </div>

      {showPicker && (
        <FolderPicker
          onSelect={handleOpenFolder}
          onCancel={() => setShowPicker(false)}
        />
      )}
    </div>
  )
}
