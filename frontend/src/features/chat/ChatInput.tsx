import { useState, useRef, useEffect, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'
import { Send, FileText, Globe, Code, Search, HelpCircle } from 'lucide-react'

interface Props {
  onSend: (text: string, useStream?: boolean, modeId?: string, modelId?: string) => void
  disabled?: boolean
  useStream?: boolean
  onUseStreamChange?: (useStream: boolean) => void
  modeId?: string
  modelId?: string
  searchWeb?: boolean
  onSearchWebChange?: (v: boolean) => void
  onInsertTemplate?: () => void
  /** Cursor-like: Mode + Model + Web inline in toolbar */
  modeSelector?: ReactNode
  modelSelector?: ReactNode
  /** When true, show hint that AI sees open files (no @ needed) */
  hasEditorContext?: boolean
}

// Quick command suggestions — @ optional: open files already visible (Cursor-like)
const QUICK_COMMANDS = [
  { cmd: '@web', desc: 'Поиск в интернете', example: '@web python async tutorial', Icon: Globe },
  { cmd: '@code', desc: 'Добавить ещё файл по пути', example: '@code src/other.py', Icon: Code },
  { cmd: '@file', desc: 'Прочитать файл по пути', example: '@file README.md', Icon: FileText },
  { cmd: '@rag', desc: 'Поиск по кодовой базе', example: '@rag how auth works', Icon: Search },
  { cmd: '@help', desc: 'Показать команды', example: '@help', Icon: HelpCircle },
]

export function ChatInput({ 
  onSend, 
  disabled, 
  useStream = false, 
  onUseStreamChange,
  modeId,
  modelId,
  searchWeb = false,
  onSearchWebChange,
  onInsertTemplate,
  modeSelector,
  modelSelector,
  hasEditorContext,
}: Props) {
  const [value, setValue] = useState('')
  const [showCommands, setShowCommands] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (value.trim() && !disabled) {
      let text = value.trim()
      if (searchWeb && !text.startsWith('@web')) {
        text = `@web ${text}`
      }
      onSend(text, useStream, modeId, modelId)
      setValue('')
      setShowCommands(false)
      setTimeout(() => inputRef.current?.focus(), 0)
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
              <c.Icon size={14} className="chat-input__command-icon" />
              <span className="chat-input__command-name">{c.cmd}</span>
              <span className="chat-input__command-desc">{c.desc}</span>
            </button>
          ))}
        </div>
      )}

      <form className="chat-input" onSubmit={handleSubmit}>
        <div className="chat-input__box">
          <div className="chat-input__controls">
            {modeSelector && <div className="chat-input__control">{modeSelector}</div>}
            {modelSelector && <div className="chat-input__control">{modelSelector}</div>}
            {onSearchWebChange && (
              <button
                type="button"
                className={`chat-input__icon ${searchWeb ? 'chat-input__icon--active' : ''}`}
                onClick={() => onSearchWebChange(!searchWeb)}
                title={searchWeb ? 'Веб-поиск включён' : 'Веб-поиск'}
              >
                <Globe size={14} />
              </button>
            )}
            {onInsertTemplate && (
              <button
                type="button"
                className="chat-input__icon"
                onClick={onInsertTemplate}
                title="Шаблон"
              >
                <FileText size={14} />
              </button>
            )}
          </div>
          <div className="chat-input__row">
            <textarea
              ref={inputRef}
              value={value}
              onChange={(e) => handleChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={hasEditorContext ? 'Чем помочь? AI видит открытые файлы.' : 'Чем помочь?'}
              title="Enter — отправить, Shift+Enter — новая строка"
              disabled={disabled}
              className="chat-input__field"
              rows={1}
            />
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
            <button
              type="submit"
              disabled={disabled || !value.trim()}
              className="chat-input__btn"
              title="Отправить (Enter)"
            >
              <Send size={14} />
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}
