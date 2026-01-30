import { useState, useRef, useEffect, type FormEvent, type KeyboardEvent } from 'react'

interface Props {
  onSend: (text: string, useStream?: boolean, modeId?: string) => void
  disabled?: boolean
  useStream?: boolean
  onUseStreamChange?: (useStream: boolean) => void
  modeId?: string
  onInsertTemplate?: () => void
}

// Quick command suggestions
const QUICK_COMMANDS = [
  { cmd: '@web', desc: 'Search the web', example: '@web python async tutorial' },
  { cmd: '@code', desc: 'Include code file', example: '@code src/main.py' },
  { cmd: '@file', desc: 'Read any file', example: '@file README.md' },
  { cmd: '@rag', desc: 'Search codebase', example: '@rag how auth works' },
  { cmd: '@help', desc: 'Show commands', example: '@help' },
]

export function ChatInput({ 
  onSend, 
  disabled, 
  useStream = false, 
  onUseStreamChange,
  modeId,
  onInsertTemplate,
}: Props) {
  const [value, setValue] = useState('')
  const [showCommands, setShowCommands] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (value.trim() && !disabled) {
      onSend(value, useStream, modeId)
      setValue('')
      setShowCommands(false)
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e as unknown as FormEvent)
    }
  }

  const handleChange = (newValue: string) => {
    setValue(newValue)
    // Show commands popup when typing @
    const lastAt = newValue.lastIndexOf('@')
    if (lastAt >= 0 && lastAt === newValue.length - 1) {
      setShowCommands(true)
    } else if (!newValue.includes('@') || newValue.endsWith(' ')) {
      setShowCommands(false)
    }
  }

  const insertCommand = (cmd: string) => {
    setValue((prev) => {
      const lastAt = prev.lastIndexOf('@')
      if (lastAt >= 0) {
        return prev.slice(0, lastAt) + cmd + ' '
      }
      return prev + cmd + ' '
    })
    setShowCommands(false)
    inputRef.current?.focus()
  }

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 120) + 'px'
    }
  }, [value])

  return (
    <div className="chat-input-wrapper">
      {showCommands && (
        <div className="chat-input__commands">
          {QUICK_COMMANDS.map((c) => (
            <button
              key={c.cmd}
              className="chat-input__command"
              onClick={() => insertCommand(c.cmd)}
              type="button"
            >
              <span className="chat-input__command-name">{c.cmd}</span>
              <span className="chat-input__command-desc">{c.desc}</span>
            </button>
          ))}
        </div>
      )}

      <form className="chat-input" onSubmit={handleSubmit}>
        <div className="chat-input__toolbar">
          {onInsertTemplate && (
            <button
              type="button"
              className="chat-input__tool"
              onClick={onInsertTemplate}
              title="Insert template"
            >
              📝
            </button>
          )}
          <span className="chat-input__hint">
            Type @ for commands • Shift+Enter for newline
          </span>
        </div>
        
        <div className="chat-input__main">
          <textarea
            ref={inputRef}
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message... (@web, @code, @rag for commands)"
            disabled={disabled}
            className="chat-input__field"
            rows={1}
          />
          <button 
            type="submit" 
            disabled={disabled || !value.trim()} 
            className="chat-input__btn"
          >
            ↑
          </button>
        </div>

        <div className="chat-input__footer">
          {onUseStreamChange && (
            <label className="chat-input__stream">
              <input
                type="checkbox"
                checked={useStream}
                onChange={(e) => onUseStreamChange(e.target.checked)}
                disabled={disabled}
              />
              Stream
            </label>
          )}
        </div>
      </form>
    </div>
  )
}
