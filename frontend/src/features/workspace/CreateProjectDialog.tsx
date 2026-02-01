import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { FolderPlus } from 'lucide-react'

interface CreateProjectDialogProps {
  onCreate: (path: string, name?: string) => Promise<void>
  onCancel: () => void
}

export function CreateProjectDialog({ onCreate, onCancel }: CreateProjectDialogProps) {
  const [path, setPath] = useState('')
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [onCancel])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const p = path.trim()
    if (!p) {
      setError('Укажите путь')
      return
    }
    setError(null)
    setLoading(true)
    try {
      await onCreate(p, name.trim() || undefined)
      onCancel()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка создания')
    } finally {
      setLoading(false)
    }
  }

  return createPortal(
    <div className="folder-picker-overlay" onClick={onCancel}>
      <div className="folder-picker create-project-dialog" onClick={(e) => e.stopPropagation()}>
        <h3>
          <FolderPlus size={20} />
          Создать проект
        </h3>
        <p className="create-project-dialog__hint">
          Будет создана папка (если её нет) и она станет текущим проектом. Путь — под домашней директорией или текущей рабочей.
        </p>
        <form onSubmit={handleSubmit}>
          <label className="create-project-dialog__label">
            Путь к папке
            <input
              type="text"
              className="create-project-dialog__input"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/Users/you/Projects/my-bot или ~/Projects/my-bot"
              autoFocus
              disabled={loading}
            />
          </label>
          <label className="create-project-dialog__label">
            Имя проекта (необязательно)
            <input
              type="text"
              className="create-project-dialog__input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="По умолчанию — имя папки"
              disabled={loading}
            />
          </label>
          {error && <div className="create-project-dialog__error">{error}</div>}
          <div className="folder-picker__actions">
            <button type="button" onClick={onCancel} disabled={loading}>
              Отмена
            </button>
            <button type="submit" className="create-project-dialog__submit" disabled={loading}>
              {loading ? 'Создание…' : 'Создать'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  )
}
