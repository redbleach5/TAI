import { useState, useRef, useEffect } from 'react'
import { Terminal, Trash2, ChevronUp, ChevronDown } from 'lucide-react'
import { useTerminal } from './useTerminal'

interface TerminalPanelProps {
  collapsed?: boolean
  onToggle?: () => void
}

export function TerminalPanel({ collapsed = false, onToggle }: TerminalPanelProps) {
  const { output, running, clearOutput, executeCommand, getPrevCommand, getNextCommand } = useTerminal()
  const [input, setInput] = useState('')
  const outputRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-scroll to bottom
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight
    }
  }, [output])

  // Focus input when expanded
  useEffect(() => {
    if (!collapsed && inputRef.current) {
      inputRef.current.focus()
    }
  }, [collapsed])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || running) return
    executeCommand(input)
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setInput(getPrevCommand())
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setInput(getNextCommand())
    }
  }

  if (collapsed) {
    return (
      <div className="terminal-panel terminal-panel--collapsed" onClick={onToggle}>
        <Terminal size={14} />
        <span className="terminal-panel__collapsed-label">Terminal</span>
        <ChevronUp size={14} className="terminal-panel__expand" />
      </div>
    )
  }

  return (
    <div className="terminal-panel">
      <div className="terminal-panel__header">
        <span className="terminal-panel__title">
          <Terminal size={14} />
          Terminal
        </span>
        <div className="terminal-panel__actions">
          <button 
            className="terminal-panel__btn"
            onClick={clearOutput}
            title="Clear"
          >
            <Trash2 size={14} />
          </button>
          {onToggle && (
            <button 
              className="terminal-panel__btn"
              onClick={onToggle}
              title="Collapse"
            >
              <ChevronDown size={14} />
            </button>
          )}
        </div>
      </div>
      
      <div className="terminal-panel__output" ref={outputRef}>
        {output.map((line, i) => (
          <div key={i} className={`terminal-line terminal-line--${line.type}`}>
            {line.text}
          </div>
        ))}
        {running && (
          <div className="terminal-line terminal-line--info">Running...</div>
        )}
      </div>

      <form className="terminal-panel__input-form" onSubmit={handleSubmit}>
        <span className="terminal-panel__prompt">$</span>
        <input
          ref={inputRef}
          type="text"
          className="terminal-panel__input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter command..."
          disabled={running}
          spellCheck={false}
          autoComplete="off"
        />
      </form>
    </div>
  )
}
