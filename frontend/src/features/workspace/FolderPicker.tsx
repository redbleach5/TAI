import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { FolderOpen, ChevronUp, Loader2 } from 'lucide-react'
import { useBrowse } from './useBrowse'

interface FolderPickerProps {
  onSelect: (path: string) => void
  onCancel: () => void
}

export function FolderPicker({ onSelect, onCancel }: FolderPickerProps) {
  const { dirs, parent, currentPath, loading, error, fetchDirs, selectDir, goUp } = useBrowse()

  useEffect(() => {
    fetchDirs('')
  }, [fetchDirs])

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [onCancel])

  return createPortal(
    <div className="folder-picker-overlay" onClick={onCancel}>
      <div className="folder-picker" onClick={(e) => e.stopPropagation()}>
        <h3>Выберите папку</h3>
        <div className="folder-picker__breadcrumb">
          {parent && (
            <button
              type="button"
              className="folder-picker__up"
              onClick={goUp}
              title="Вверх"
            >
              <ChevronUp size={18} />
            </button>
          )}
          <span className="folder-picker__path">
            {currentPath || 'Home'}
          </span>
        </div>
        <div className="folder-picker__list">
          {loading ? (
            <div className="folder-picker__loading">
              <Loader2 size={24} className="icon-spin" />
            </div>
          ) : error ? (
            <div className="folder-picker__error">{error}</div>
          ) : (
            dirs.map((dir) => (
              <div key={dir.path} className="folder-picker__row">
                <button
                  type="button"
                  className="folder-picker__item"
                  onClick={() => selectDir(dir.path)}
                >
                  <FolderOpen size={20} />
                  <span>{dir.name}</span>
                </button>
                <button
                  type="button"
                  className="folder-picker__select-btn"
                  onClick={() => onSelect(dir.path)}
                >
                  Выбрать
                </button>
              </div>
            ))
          )}
        </div>
        <div className="folder-picker__actions">
          <button type="button" onClick={onCancel}>
            Отмена
          </button>
          {currentPath && (
            <button
              type="button"
              className="folder-picker__select-current"
              onClick={() => onSelect(currentPath)}
            >
              Выбрать эту папку
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body
  )
}
