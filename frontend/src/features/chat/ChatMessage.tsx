import { useState, useCallback } from 'react'
import { User, Bot, Wrench, CheckCircle, Copy, Check, FileText, CheckCircle2, XCircle } from 'lucide-react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useOpenFilesContext } from '../editor/OpenFilesContext'
import type { ChatMessage as ChatMessageType, ProposedEdit } from '../../api/client'

function CodeBlockWithCopy({ children, className }: { children: React.ReactNode; className?: string }) {
  const [copied, setCopied] = useState(false)
  const text = typeof children === 'string' ? children : String(children ?? '')
  const copy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }, [text])
  return (
    <div className="chat-message__code-wrapper">
      <pre className="chat-message__code-block">
        <code className={className}>{children}</code>
      </pre>
      <button
        type="button"
        className="chat-message__copy-btn"
        onClick={copy}
        title={copied ? 'Скопировано' : 'Копировать'}
      >
        {copied ? <Check size={14} /> : <Copy size={14} />}
        <span>{copied ? 'Скопировано' : 'Копировать'}</span>
      </button>
    </div>
  )
}

function PendingEditBlock({
  edit,
  messageIndex,
  applying,
  onApplyingChange,
  onApply,
  onReject,
  onOpenFile,
}: {
  edit: ProposedEdit
  messageIndex: number
  applying: boolean
  onApplyingChange: (path: string, v: boolean) => void
  onApply?: (messageIndex: number, path: string, content: string) => void | Promise<unknown>
  onReject?: (messageIndex: number, path: string) => void
  onOpenFile?: (path: string) => void
}) {
  const [showDiff, setShowDiff] = useState(false)
  const handleApply = useCallback(async () => {
    if (!onApply) return
    onApplyingChange(edit.path, true)
    try {
      await onApply(messageIndex, edit.path, edit.content)
    } finally {
      onApplyingChange(edit.path, false)
    }
  }, [edit.path, edit.content, messageIndex, onApply, onApplyingChange])
  const handleReject = useCallback(() => {
    onReject?.(messageIndex, edit.path)
  }, [edit.path, messageIndex, onReject])
  const hasOld = edit.old_content != null && edit.old_content !== ''
  return (
    <div className="chat-message__edit-block">
      <div className="chat-message__edit-path">
        <FileText size={14} />
        <span>{edit.path}</span>
        {onOpenFile && (
          <button
            type="button"
            className="chat-message__edit-open"
            onClick={() => onOpenFile(edit.path)}
            title="Открыть в редакторе"
          >
            Открыть
          </button>
        )}
      </div>
      {hasOld && (
        <button
          type="button"
          className="chat-message__edit-toggle-diff"
          onClick={() => setShowDiff((v) => !v)}
        >
          {showDiff ? 'Скрыть diff' : 'Показать diff'}
        </button>
      )}
      {showDiff && hasOld && (
        <div className="chat-message__edit-diff">
          <div className="chat-message__edit-old">
            <span className="chat-message__edit-label">Было:</span>
            <pre>{edit.old_content}</pre>
          </div>
          <div className="chat-message__edit-new">
            <span className="chat-message__edit-label">Стало:</span>
            <pre>{edit.content}</pre>
          </div>
        </div>
      )}
      {!showDiff && (
        <pre className="chat-message__edit-preview">{edit.content.slice(0, 500)}{edit.content.length > 500 ? '…' : ''}</pre>
      )}
      <div className="chat-message__edit-actions">
        <button
          type="button"
          className="chat-message__edit-apply"
          onClick={handleApply}
          disabled={applying}
          title="Применить изменения к файлу (как в Cursor)"
        >
          {applying ? <Check size={14} className="icon-spin" /> : <CheckCircle2 size={14} />}
          <span>{applying ? 'Применяю…' : 'Применить'}</span>
        </button>
        <button
          type="button"
          className="chat-message__edit-reject"
          onClick={handleReject}
          disabled={applying}
          title="Отклонить изменения"
        >
          <XCircle size={14} />
          <span>Отклонить</span>
        </button>
      </div>
    </div>
  )
}

interface Props {
  message: ChatMessageType
  /** Index of message in the list (for apply/reject callbacks). */
  messageIndex?: number
  /** Callback when user applies a proposed edit (Cursor-like). */
  onApplyEdit?: (messageIndex: number, path: string, content: string) => void | Promise<unknown>
  /** Callback when user rejects a proposed edit (Cursor-like). */
  onRejectEdit?: (messageIndex: number, path: string) => void
}

export function ChatMessage({ message, messageIndex = 0, onApplyEdit, onRejectEdit }: Props) {
  const isUser = message.role === 'user'
  const openFilesCtx = useOpenFilesContext()
  const [showThinking, setShowThinking] = useState(false)
  const [showTools, setShowTools] = useState(true)
  const [showEdits, setShowEdits] = useState(true)
  const [applying, setApplying] = useState<string | null>(null)
  const hasThinking = !isUser && message.thinking && message.thinking.length > 0
  const hasToolEvents = !isUser && message.toolEvents && message.toolEvents.length > 0
  const hasReportPath = !isUser && message.reportPath
  const hasPendingEdits = !isUser && message.pendingEdits && message.pendingEdits.length > 0

  return (
    <div className={`chat-message chat-message--${message.role}`}>
      <div className="chat-message__avatar">
        {isUser ? <User size={12} /> : <Bot size={12} />}
      </div>
      <div className="chat-message__body">
        <span className="chat-message__role">{isUser ? 'Вы' : 'AI'}</span>
        {hasThinking && (
          <details
            className="chat-message__thinking"
            open={showThinking}
            onToggle={(e) => setShowThinking((e.target as HTMLDetailsElement).open)}
          >
            <summary>Рассуждения ({message.thinking!.length} символов)</summary>
            <pre className="chat-message__thinking-content">{message.thinking}</pre>
          </details>
        )}
        {hasToolEvents && (
          <details
            className="chat-message__tools"
            open={showTools}
            onToggle={(e) => setShowTools((e.target as HTMLDetailsElement).open)}
          >
            <summary>Инструменты ({message.toolEvents!.length})</summary>
            <div className="chat-message__tools-list">
              {message.toolEvents!.map((evt, i) => (
                <div key={i} className={`chat-message__tool-event chat-message__tool-event--${evt.type}`}>
                  {evt.type === 'tool_call' ? <Wrench size={12} /> : <CheckCircle size={12} />}
                  <pre>{evt.data.length > 300 ? evt.data.slice(0, 300) + '…' : evt.data}</pre>
                </div>
              ))}
            </div>
          </details>
        )}
        {!isUser && hasToolEvents && message.toolEvents!.length > 0 && (() => {
          const lastResult = [...message.toolEvents!].reverse().find((e) => e.type === 'tool_result')
          const contentEmpty = !message.content || !message.content.trim()
          const looksLikeToolCall = typeof message.content === 'string' && (
            message.content.includes('<tool_call>') ||
            (message.content.includes('"name"') && message.content.includes('"arguments"')) ||
            (message.content.includes('"tool"') && /"path"|"command"|"query"|"content"|"incremental"|"question"/.test(message.content))
          )
          if (lastResult && (contentEmpty || looksLikeToolCall)) {
            return (
              <div className="chat-message__content chat-message__content--tool-result">
                <p className="chat-message__result-label">Результат выполнения:</p>
                <pre className="chat-message__result-output">{lastResult.data}</pre>
              </div>
            )
          }
          return null
        })()}
        <div className="chat-message__content">
          {isUser ? (
            message.content
          ) : (() => {
            const contentEmpty = !message.content || !message.content.trim()
            const looksLikeToolCall = typeof message.content === 'string' && (
              message.content.includes('<tool_call>') ||
              (message.content.includes('"name"') && message.content.includes('"arguments"')) ||
              (message.content.includes('"tool"') && /"path"|"command"|"query"|"content"|"incremental"|"question"/.test(message.content))
            )
            const hasResultBlock = hasToolEvents && message.toolEvents!.some((e) => e.type === 'tool_result') && (contentEmpty || looksLikeToolCall)
            if (hasResultBlock) return <span className="chat-message__content-placeholder">Вызов инструмента (результат выше)</span>
            return (
            <Markdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || '')
                  const isBlock = match || (typeof children === 'string' && children.includes('\n'))
                  return isBlock ? (
                    <CodeBlockWithCopy className={className}>
                      {children}
                    </CodeBlockWithCopy>
                  ) : (
                    <code className="chat-message__inline-code" {...props}>
                      {children}
                    </code>
                  )
                },
              }}
            >
              {message.content}
            </Markdown>
            )
          })()}
        </div>
        {hasReportPath && (
          <div className="chat-message__report-actions">
            <button
              type="button"
              className="chat-message__open-report-btn"
              onClick={() => openFilesCtx?.openFile(message.reportPath!)}
              title="Открыть полный отчёт в редакторе"
            >
              <FileText size={14} />
              <span>Открыть отчёт</span>
            </button>
          </div>
        )}
        {hasPendingEdits && (
          <details
            className="chat-message__pending-edits"
            open={showEdits}
            onToggle={(e) => setShowEdits((e.target as HTMLDetailsElement).open)}
          >
            <summary>Предложенные изменения ({message.pendingEdits!.length} файл(ов))</summary>
            <div className="chat-message__edits-list">
              {message.pendingEdits!.map((edit: ProposedEdit) => (
                <PendingEditBlock
                  key={edit.path}
                  edit={edit}
                  messageIndex={messageIndex}
                  applying={applying === edit.path}
                  onApplyingChange={(path, v) => setApplying(v ? path : null)}
                  onApply={onApplyEdit}
                  onReject={onRejectEdit}
                  onOpenFile={openFilesCtx?.openFile}
                />
              ))}
            </div>
          </details>
        )}
        {!isUser && message.model && (
          <span className="chat-message__watermark">Модель: {message.model}</span>
        )}
      </div>
    </div>
  )
}
