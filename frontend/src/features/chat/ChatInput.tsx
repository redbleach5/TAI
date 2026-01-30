import { useState, type FormEvent } from 'react'

interface Props {
  onSend: (text: string, useStream?: boolean) => void
  disabled?: boolean
  useStream?: boolean
  onUseStreamChange?: (useStream: boolean) => void
}

export function ChatInput({ onSend, disabled, useStream = false, onUseStreamChange }: Props) {
  const [value, setValue] = useState('')

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (value.trim() && !disabled) {
      onSend(value, useStream)
      setValue('')
    }
  }

  return (
    <form className="chat-input" onSubmit={handleSubmit}>
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Введите сообщение..."
        disabled={disabled}
        className="chat-input__field"
      />
      <button type="submit" disabled={disabled || !value.trim()} className="chat-input__btn">
        Отправить
      </button>
      {onUseStreamChange && (
        <label className="chat-input__stream">
          <input
            type="checkbox"
            checked={useStream}
            onChange={(e) => onUseStreamChange(e.target.checked)}
            disabled={disabled}
          />
          Стриминг
        </label>
      )}
    </form>
  )
}
