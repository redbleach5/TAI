/**
 * Cursor-like: model selector dropdown.
 */
import { useState, useRef, useEffect, useCallback } from 'react'
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
  const options = ['', ...models]
  const uniqueOptions = value && !models.includes(value) ? [value, ...options] : options

  return (
    <div className="model-selector" ref={ref}>
      <button
        type="button"
        className="model-selector__trigger"
        onClick={() => !loading && setOpen(!open)}
        disabled={loading}
        title="Выбрать модель"
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
        <div className="model-selector__dropdown">
          <button
            type="button"
            className={`model-selector__item ${!value ? 'model-selector__item--active' : ''}`}
            onClick={() => {
              onChange('')
              setOpen(false)
            }}
          >
            Auto
          </button>
          {uniqueOptions.filter(Boolean).map((m) => (
            <button
              key={m}
              type="button"
              className={`model-selector__item ${value === m ? 'model-selector__item--active' : ''}`}
              onClick={() => {
                onChange(m)
                setOpen(false)
              }}
            >
              {m}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
