import { useRef, useEffect, useState } from 'react'
import { useChat } from './useChat'
import { ChatMessage } from './ChatMessage'
import { ChatInput } from './ChatInput'

export function ChatPanel() {
  const { messages, loading, streaming, error, send, clear } = useChat()
  const [useStream, setUseStream] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  return (
    <div className="chat-panel">
      <div className="chat-panel__header">
        <span className="chat-panel__title">Чат</span>
        {messages.length > 0 && (
          <button
            type="button"
            className="chat-panel__new-btn"
            onClick={clear}
            title="Начать новый чат"
          >
            + Новый чат
          </button>
        )}
      </div>
      <div className="chat-panel__messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="chat-panel__empty">
            <p className="chat-panel__empty-title">Начните разговор</p>
            <p className="chat-panel__empty-hint">
              Попробуйте: «привет», «помощь» или задайте вопрос о коде
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <ChatMessage key={i} message={msg} />
        ))}
        {loading && !streaming && (
          <div className="chat-message chat-message--assistant">
            <span className="chat-message__role">AI</span>
            <div className="chat-message__content chat-message__content--loading">
              <span className="chat-loading-dots">
                <span></span><span></span><span></span>
              </span>
            </div>
          </div>
        )}
      </div>
      {error && <p className="chat-panel__error">{error}</p>}
      <ChatInput
        onSend={send}
        disabled={loading}
        useStream={useStream}
        onUseStreamChange={setUseStream}
      />
    </div>
  )
}
