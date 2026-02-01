/**
 * Cursor-like: compact mode dropdown.
 */
import { useState, useRef, useEffect } from 'react'
import { ChevronDown } from 'lucide-react'
import type { AssistantMode } from './useAssistant'

interface Props {
  modes: AssistantMode[]
  currentMode: string
  onSelect: (modeId: string) => void
  /** Compact inline style (Cursor-like) */
  compact?: boolean
}

export function ModeSelector({ modes, currentMode, onSelect, compact }: Props) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  if (modes.length === 0) return null

  const current = modes.find((m) => m.id === currentMode) ?? modes[0]

  return (
    <div className={`mode-selector mode-selector--${compact ? 'compact' : 'default'}`} ref={ref}>
      <button
        type="button"
        className="mode-selector__trigger"
        onClick={() => setOpen(!open)}
        title={current.description || current.name}
      >
        <span className="mode-selector__icon">{current.icon}</span>
        <span className="mode-selector__name" title={current.name}>{current.name}</span>
        <ChevronDown size={12} className={`mode-selector__chevron ${open ? 'mode-selector__chevron--open' : ''}`} />
      </button>
      {open && (
        <div className="mode-selector__dropdown">
          {modes.map((mode) => (
            <button
              key={mode.id}
              type="button"
              className={`mode-selector__item ${currentMode === mode.id ? 'mode-selector__item--active' : ''}`}
              onClick={() => {
                onSelect(mode.id)
                setOpen(false)
              }}
              title={mode.description}
            >
              <span className="mode-selector__icon">{mode.icon}</span>
              <span>{mode.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
