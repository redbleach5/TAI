/**
 * Cursor-like: compact mode dropdown with keyboard navigation.
 */
import { useState, useRef, useEffect, useCallback } from 'react'
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
  const [focusIdx, setFocusIdx] = useState(-1)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        setOpen(true)
        setFocusIdx(modes.findIndex((m) => m.id === currentMode))
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
      setFocusIdx((i) => (i + 1) % modes.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setFocusIdx((i) => (i - 1 + modes.length) % modes.length)
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      if (focusIdx >= 0 && focusIdx < modes.length) {
        onSelect(modes[focusIdx].id)
        setOpen(false)
      }
    }
  }, [open, modes, focusIdx, currentMode, onSelect])

  if (modes.length === 0) return null

  const current = modes.find((m) => m.id === currentMode) ?? modes[0]

  return (
    <div
      className={`mode-selector mode-selector--${compact ? 'compact' : 'default'}`}
      ref={ref}
      onKeyDown={handleKeyDown}
    >
      <button
        type="button"
        className="mode-selector__trigger"
        onClick={() => setOpen(!open)}
        title={current.description || current.name}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="mode-selector__icon">{current.icon}</span>
        <span className="mode-selector__name" title={current.name}>{current.name}</span>
        <ChevronDown size={12} className={`mode-selector__chevron ${open ? 'mode-selector__chevron--open' : ''}`} />
      </button>
      {open && (
        <div className="mode-selector__dropdown" role="listbox" aria-label="Режим ассистента">
          {modes.map((mode, i) => (
            <button
              key={mode.id}
              type="button"
              className={`mode-selector__item ${currentMode === mode.id ? 'mode-selector__item--active' : ''} ${i === focusIdx ? 'mode-selector__item--focused' : ''}`}
              onClick={() => {
                onSelect(mode.id)
                setOpen(false)
              }}
              onMouseEnter={() => setFocusIdx(i)}
              title={mode.description}
              role="option"
              aria-selected={currentMode === mode.id}
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
