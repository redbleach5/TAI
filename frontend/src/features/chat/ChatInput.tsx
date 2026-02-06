import { useState, useRef, useEffect, useCallback, useMemo, type FormEvent, type KeyboardEvent, type ReactNode } from 'react'
import { Send, FileText, Globe, Code, Search, HelpCircle, FolderOpen, GitBranch, FileSearch, TerminalSquare, GitCompare } from 'lucide-react'

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
  { cmd: '@web', desc: 'Поиск в интернете', Icon: Globe },
  { cmd: '@code', desc: 'Добавить файл по пути', Icon: Code },
  { cmd: '@file', desc: 'Прочитать файл', Icon: FileText },
  { cmd: '@folder', desc: 'Содержимое каталога', Icon: FolderOpen },
  { cmd: '@rag', desc: 'Семантический поиск', Icon: Search },
  { cmd: '@grep', desc: 'Поиск по тексту', Icon: FileSearch },
  { cmd: '@git', desc: 'Git статус и лог', Icon: GitBranch },
  { cmd: '@diff', desc: 'Git diff', Icon: GitCompare },
  { cmd: '@run', desc: 'Выполнить команду', Icon: TerminalSquare },
  { cmd: '@help', desc: 'Показать команды', Icon: HelpCircle },
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
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [filter, setFilter] = useState('')
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const commandsRef = useRef<HTMLDivElement>(null)

  // Filtered commands based on what user typed after @
  const filtered = useMemo(
    () => filter
      ? QUICK_COMMANDS.filter((c) => c.cmd.toLowerCase().includes(`@${filter.toLowerCase()}`))
      : QUICK_COMMANDS,
    [filter],
  )

  const handleSubmit = useCallback((e: FormEvent) => {
    e.preventDefault()
    if (value.trim() && !disabled) {
      let text = value.trim()
      if (searchWeb && !text.startsWith('@web')) {
        text = `@web ${text}`
      }
      onSend(text, useStream, modeId, modelId)
      setValue('')
      setShowCommands(false)
      setFilter('')
      setSelectedIdx(0)
      setTimeout(() => inputRef.current?.focus(), 0)
    }
  }, [value, disabled, searchWeb, onSend, useStream, modeId, modelId])

  const insertCommand = useCallback((cmd: string) => {
    setValue((prev) => {
      const lastAt = prev.lastIndexOf('@')
      if (lastAt >= 0) {
        return prev.slice(0, lastAt) + cmd + ' '
      }
      return prev + cmd + ' '
    })
    setShowCommands(false)
    setFilter('')
    setSelectedIdx(0)
    inputRef.current?.focus()
  }, [])

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Command popup keyboard navigation
    if (showCommands && filtered.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIdx((i) => (i + 1) % filtered.length)
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIdx((i) => (i - 1 + filtered.length) % filtered.length)
        return
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault()
        insertCommand(filtered[selectedIdx].cmd)
        return
      }
      if (e.key === 'Escape') {
        e.preventDefault()
        setShowCommands(false)
        setFilter('')
        setSelectedIdx(0)
        return
      }
    }
    // Normal Enter to send
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e as unknown as FormEvent)
    }
  }

  const handleChange = (newValue: string) => {
    setValue(newValue)
    // Show commands popup when typing @, filter as user types
    const lastAt = newValue.lastIndexOf('@')
    if (lastAt >= 0) {
      const afterAt = newValue.slice(lastAt + 1)
      // Show popup when @ is at end or user is still typing command name (no space yet)
      if (!afterAt.includes(' ') && !afterAt.includes('\n')) {
        setShowCommands(true)
        setFilter(afterAt)
        setSelectedIdx(0)
        return
      }
    }
    setShowCommands(false)
    setFilter('')
  }

  // Scroll selected item into view
  useEffect(() => {
    if (showCommands && commandsRef.current) {
      const active = commandsRef.current.querySelector('.chat-input__command--active')
      active?.scrollIntoView({ block: 'nearest' })
    }
  }, [selectedIdx, showCommands])

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 120) + 'px'
    }
  }, [value])

  return (
    <div className="chat-input-wrapper">
      {showCommands && filtered.length > 0 && (
        <div className="chat-input__commands" ref={commandsRef} role="listbox" aria-label="Команды" id="chat-commands-listbox">
          {filtered.map((c, i) => (
            <button
              key={c.cmd}
              className={`chat-input__command ${i === selectedIdx ? 'chat-input__command--active' : ''}`}
              onClick={() => insertCommand(c.cmd)}
              onMouseEnter={() => setSelectedIdx(i)}
              type="button"
              role="option"
              aria-selected={i === selectedIdx}
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
                aria-pressed={searchWeb}
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
              placeholder={hasEditorContext ? 'Чем помочь? AI видит открытые файлы.' : 'Чем помочь? Напишите @ для списка команд'}
              title="Enter — отправить, Shift+Enter — новая строка, @ — список команд"
              disabled={disabled}
              className="chat-input__field"
              rows={1}
              role="combobox"
              aria-expanded={showCommands}
              aria-autocomplete="list"
              aria-haspopup="listbox"
              aria-controls="chat-commands-listbox"
            />
            {onUseStreamChange && (
              <label className="chat-input__stream" title="Включить потоковую передачу">
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
              aria-label="Отправить сообщение"
            >
              <Send size={14} />
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}
