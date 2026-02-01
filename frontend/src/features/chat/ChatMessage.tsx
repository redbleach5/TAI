import { useState, useCallback } from 'react'
import { User, Bot, Wrench, CheckCircle, Copy, Check, FileText } from 'lucide-react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useOpenFilesContext } from '../editor/OpenFilesContext'
import type { ChatMessage as ChatMessageType } from '../../api/client'

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

interface Props {
  message: ChatMessageType
}

export function ChatMessage({ message }: Props) {
  const isUser = message.role === 'user'
  const openFilesCtx = useOpenFilesContext()
  const [showThinking, setShowThinking] = useState(false)
  const [showTools, setShowTools] = useState(true)
  const hasThinking = !isUser && message.thinking && message.thinking.length > 0
  const hasToolEvents = !isUser && message.toolEvents && message.toolEvents.length > 0
  const hasReportPath = !isUser && message.reportPath

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
        <div className="chat-message__content">
          {isUser ? (
            message.content
          ) : (
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
          )}
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
        {!isUser && message.model && (
          <span className="chat-message__watermark">Модель: {message.model}</span>
        )}
      </div>
    </div>
  )
}
