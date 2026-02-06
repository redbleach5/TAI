/**
 * Cursor-like: model selector dropdown with keyboard navigation.
 */
import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { ChevronDown, Loader2 } from 'lucide-react'
import { getConfig, getModels } from '../../api/client'

interface Props {
  value: string
  onChange: (model: string) => void
  provider?: 'ollama' | 'lm_studio'
}

export function ModelSelector({ value, onChange, provider }: Props) {
  const [open, setOpen] = useState(false)
  const [models, setModels] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [focusIdx, setFocusIdx] = useState(-1)
  const ref = useRef<HTMLDivElement>(null)

  const fetchModels = useCallback(async () => {
    setLoading(true)
    try {
      let p: 'ollama' | 'lm_studio' | undefined = provider
      if (p == null) {
        try {
          const config = await getConfig()
          p = (config?.llm?.provider as 'ollama' | 'lm_studio') ?? undefined
        } catch {
          // use current provider from backend (no query param)
        }
      }
      const list = await getModels(p ?? undefined)
      setModels(Array.isArray(list) ? list : [])
    } catch {
      setModels([])
    } finally {
      setLoading(false)
    }
  }, [provider])

  useEffect(() => {
    fetchModels()
  }, [fetchModels])

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const displayValue = value || 'Auto'
  const uniqueOptions = useMemo(() => {
    const allOptions = ['', ...models]
    return value && !models.includes(value) ? [value, ...allOptions] : allOptions
  }, [value, models])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        setOpen(true)
        setFocusIdx(uniqueOptions.indexOf(value))
      }
      return
    }
    if (e.key === 'Escape') {
      e.preventDefault()
      setOpen(false)
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setFocusIdx((i) => (i + 1) % uniqueOptions.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setFocusIdx((i) => (i - 1 + uniqueOptions.length) % uniqueOptions.length)
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      if (focusIdx >= 0 && focusIdx < uniqueOptions.length) {
        onChange(uniqueOptions[focusIdx])
        setOpen(false)
      }
    }
  }, [open, uniqueOptions, value, focusIdx, onChange])

  return (
    <div className="model-selector" ref={ref} onKeyDown={handleKeyDown}>
      <button
        type="button"
        className="model-selector__trigger"
        onClick={() => !loading && setOpen(!open)}
        disabled={loading}
        title="Выбрать модель"
        aria-label={`Model: ${displayValue}`}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {loading ? (
          <Loader2 size={12} className="icon-spin" />
        ) : (
          <>
            <span className="model-selector__value">{displayValue}</span>
            <ChevronDown size={12} className={`model-selector__chevron ${open ? 'model-selector__chevron--open' : ''}`} />
          </>
        )}
      </button>
      {open && !loading && (
        <div className="model-selector__dropdown" role="listbox" aria-label="Выбор модели">
          {uniqueOptions.map((m, i) => (
            <button
              key={m || '__auto__'}
              type="button"
              className={`model-selector__item ${value === m ? 'model-selector__item--active' : ''} ${i === focusIdx ? 'model-selector__item--focused' : ''}`}
              onClick={() => {
                onChange(m)
                setOpen(false)
              }}
              onMouseEnter={() => setFocusIdx(i)}
              role="option"
              aria-selected={value === m}
            >
              {m || 'Auto'}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
