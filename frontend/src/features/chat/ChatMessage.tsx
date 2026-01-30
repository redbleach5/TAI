import { useState } from 'react'
import Markdown from 'react-markdown'
import type { ChatMessage as ChatMessageType } from '../../api/client'

interface Props {
  message: ChatMessageType
}

export function ChatMessage({ message }: Props) {
  const isUser = message.role === 'user'
  const [showThinking, setShowThinking] = useState(false)
  const hasThinking = !isUser && message.thinking && message.thinking.length > 0

  return (
    <div className={`chat-message chat-message--${message.role}`}>
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
  )
}
