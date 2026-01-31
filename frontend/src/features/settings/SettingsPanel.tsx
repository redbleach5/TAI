import { useCallback, useEffect, useState } from 'react'
import { Settings, Save, Loader2, Plus, CheckCircle2, AlertCircle, RefreshCw, X } from 'lucide-react'
import { getConfig, getModels, patchConfig, type ConfigPatch, type ConfigResponse } from '../../api/client'

interface SettingsPanelProps {
  onClose?: () => void
}

export function SettingsPanel({ onClose }: SettingsPanelProps) {
  const [config, setConfig] = useState<ConfigResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [modelsOllama, setModelsOllama] = useState<string[]>([])
  const [modelsLmStudio, setModelsLmStudio] = useState<string[]>([])
  const [modelsLoading, setModelsLoading] = useState(false)

  const fetchModels = useCallback(async () => {
    setModelsLoading(true)
    try {
      const [ollama, lmStudio] = await Promise.all([
        getModels('ollama').catch(() => []),
        getModels('lm_studio').catch(() => []),
      ])
      setModelsOllama(ollama)
      setModelsLmStudio(lmStudio)
    } finally {
      setModelsLoading(false)
    }
  }, [])

  useEffect(() => {
    getConfig()
      .then(setConfig)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (config) fetchModels()
  }, [config, fetchModels])

  const handleSave = async () => {
    if (!config) return
    setSaving(true)
    setMessage(null)
    setError(null)
    const updates: ConfigPatch = {
      llm: { provider: config.llm.provider },
      models: {
        defaults: config.models.defaults,
        lm_studio: config.models.lm_studio ?? undefined,
      },
      embeddings: { model: config.embeddings.model },
      logging: { level: config.logging.level },
    }
    try {
      const res = await patchConfig(updates)
      setMessage(res.message)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return (
    <div className="settings-panel">
      <Loader2 size={20} className="icon-spin" />
      Загрузка...
    </div>
  )
  if (error && !config) return <div className="settings-panel settings-panel__error">{error}</div>
  if (!config) return null

  return (
    <div className="settings-panel">
      <div className="settings-panel__header">
        <h3>
          <Settings size={20} />
          Настройки
        </h3>
        {onClose && (
          <button type="button" className="settings-panel__close" onClick={onClose} title="Закрыть">
            <X size={18} />
          </button>
        )}
      </div>

      <h4>Конфигурация LLM</h4>

      <div className="settings-panel__section">
        <label>
          LLM Provider
          <select
            value={config.llm.provider}
            onChange={(e) =>
              setConfig({
                ...config,
                llm: { provider: e.target.value },
              })
            }
          >
            <option value="ollama">Ollama</option>
            <option value="lm_studio">LM Studio</option>
          </select>
        </label>
      </div>

      <div className="settings-panel__section">
        <h4>Модели (Ollama / defaults)</h4>
        {modelsLoading && (
          <p className="settings-panel__muted">
            <Loader2 size={14} className="icon-spin" /> Загрузка моделей...
          </p>
        )}
        <div className="settings-panel__fields">
          {(['simple', 'medium', 'complex', 'fallback'] as const).map((key) => {
            const value = config.models.defaults[key]
            const options = modelsOllama.length
              ? [...new Set([value, ...modelsOllama])].filter(Boolean)
              : []
            return (
              <label key={key}>
                {key.charAt(0).toUpperCase() + key.slice(1)}
                {options.length > 0 ? (
                  <select
                    value={value}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        models: {
                          ...config.models,
                          defaults: { ...config.models.defaults, [key]: e.target.value },
                        },
                      })
                    }
                  >
                    {options.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={value}
                    onChange={(e) =>
                      setConfig({
                        ...config,
                        models: {
                          ...config.models,
                          defaults: { ...config.models.defaults, [key]: e.target.value },
                        },
                      })
                    }
                  />
                )}
              </label>
            )
          })}
        </div>
        {(modelsOllama.length > 0 || modelsLmStudio.length > 0) && (
          <button
            type="button"
            className="settings-panel__refresh"
            onClick={fetchModels}
            disabled={modelsLoading}
            title="Обновить список моделей с Ollama и LM Studio"
          >
            {modelsLoading ? (
              <Loader2 size={14} className="icon-spin" />
            ) : (
              <RefreshCw size={14} />
            )}
            Обновить модели
          </button>
        )}
      </div>

      <div className="settings-panel__section">
        <h4>Модели LM Studio</h4>
        <div className="settings-panel__fields">
          {config.models.lm_studio ? (
            <>
              {(['simple', 'medium', 'complex', 'fallback'] as const).map((key) => {
                const value = config.models.lm_studio![key]
                const options = modelsLmStudio.length
                  ? [...new Set([value, ...modelsLmStudio])].filter(Boolean)
                  : []
                return (
                  <label key={key}>
                    {key.charAt(0).toUpperCase() + key.slice(1)}
                    {options.length > 0 ? (
                      <select
                        value={value}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            models: {
                              ...config.models,
                              lm_studio: {
                                ...config.models.lm_studio!,
                                [key]: e.target.value,
                              },
                            },
                          })
                        }
                      >
                        {options.map((m) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type="text"
                        value={value}
                        onChange={(e) =>
                          setConfig({
                            ...config,
                            models: {
                              ...config.models,
                              lm_studio: {
                                ...config.models.lm_studio!,
                                [key]: e.target.value,
                              },
                            },
                          })
                        }
                      />
                    )}
                  </label>
                )
              })}
            </>
          ) : (
            <div>
              <p className="settings-panel__muted">
                LM Studio использует defaults.
              </p>
              <button
                type="button"
                className="settings-panel__add"
                onClick={() =>
                  setConfig({
                    ...config,
                    models: {
                      ...config.models,
                      lm_studio: { ...config.models.defaults },
                    },
                  })
                }
              >
                <Plus size={14} />
                Добавить LM Studio overrides
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="settings-panel__section">
        <label>
          Embeddings модель (RAG)
          <input
            type="text"
            value={config.embeddings.model}
            onChange={(e) =>
              setConfig({
                ...config,
                embeddings: { model: e.target.value },
              })
            }
          />
        </label>
      </div>

      <div className="settings-panel__section">
        <label>
          Уровень логирования
          <select
            value={config.logging.level}
            onChange={(e) =>
              setConfig({
                ...config,
                logging: { level: e.target.value },
              })
            }
          >
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
          </select>
        </label>
      </div>

      {message && (
        <p className="settings-panel__success">
          <CheckCircle2 size={14} />
          {message}
        </p>
      )}
      {error && (
        <p className="settings-panel__error">
          <AlertCircle size={14} />
          {error}
        </p>
      )}

      <button
        type="button"
        className="settings-panel__save"
        onClick={handleSave}
        disabled={saving}
      >
        {saving ? (
          <>
            <Loader2 size={14} className="icon-spin" />
            <span>Сохранение...</span>
          </>
        ) : (
          <>
            <Save size={14} />
            <span>Сохранить</span>
          </>
        )}
      </button>
    </div>
  )
}
