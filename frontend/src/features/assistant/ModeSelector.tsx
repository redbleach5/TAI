import type { AssistantMode } from './useAssistant'

interface Props {
  modes: AssistantMode[]
  currentMode: string
  onSelect: (modeId: string) => void
}

export function ModeSelector({ modes, currentMode, onSelect }: Props) {
  if (modes.length === 0) return null

  return (
    <div className="mode-selector">
      {modes.map((mode) => (
        <button
          key={mode.id}
          className={`mode-selector__btn ${currentMode === mode.id ? 'mode-selector__btn--active' : ''}`}
          onClick={() => onSelect(mode.id)}
          title={mode.description}
        >
          <span className="mode-selector__icon">{mode.icon}</span>
          <span className="mode-selector__name">{mode.name}</span>
        </button>
      ))}
    </div>
  )
}
