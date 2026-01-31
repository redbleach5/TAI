import { useState } from 'react'
import { User, Bot, Wrench, CheckCircle } from 'lucide-react'
import Markdown from 'react-markdown'
import type { ChatMessage as ChatMessageType } from '../../api/client'

interface Props {
  message: ChatMessageType
}

export function ChatMessage({ message }: Props) {
  const isUser = message.role === 'user'
  const [showThinking, setShowThinking] = useState(false)
  const [showTools, setShowTools] = useState(true)
  const hasThinking = !isUser && message.thinking && message.thinking.length > 0
  const hasToolEvents = !isUser && message.toolEvents && message.toolEvents.length > 0

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
        {!isUser && message.model && (
          <span className="chat-message__watermark">{message.model}</span>
        )}
        <div className="chat-message__content">
          {isUser ? (
            message.content
          ) : (
            <Markdown
              components={{
                code({ className, children, ...props }) {
                  const match = /language-(\w+)/.exec(className || '')
                  const isBlock = match || (typeof children === 'string' && children.includes('\n'))
                  return isBlock ? (
                    <pre className="chat-message__code-block">
                      <code className={className} {...props}>
                        {children}
                      </code>
                    </pre>
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
      </div>
    </div>
  )
}
