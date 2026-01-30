import { useEffect, useState } from 'react'
import { getConfig, patchConfig, type ConfigPatch, type ConfigResponse } from '../../api/client'

export function SettingsPanel() {
  const [config, setConfig] = useState<ConfigResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getConfig()
      .then(setConfig)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

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

  if (loading) return <div className="settings-panel">Загрузка...</div>
  if (error && !config) return <div className="settings-panel settings-panel__error">{error}</div>
  if (!config) return null

  return (
    <div className="settings-panel">
      <h3>Настройки</h3>
      <p className="settings-panel__hint">
        Изменения сохраняются в config/development.toml. Перезапустите backend для применения.
      </p>

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
        <div className="settings-panel__fields">
          <label>
            Simple
            <input
              type="text"
              value={config.models.defaults.simple}
              onChange={(e) =>
                setConfig({
                  ...config,
                  models: {
                    ...config.models,
                    defaults: { ...config.models.defaults, simple: e.target.value },
                  },
                })
              }
            />
          </label>
          <label>
            Medium
            <input
              type="text"
              value={config.models.defaults.medium}
              onChange={(e) =>
                setConfig({
                  ...config,
                  models: {
                    ...config.models,
                    defaults: { ...config.models.defaults, medium: e.target.value },
                  },
                })
              }
            />
          </label>
          <label>
            Complex
            <input
              type="text"
              value={config.models.defaults.complex}
              onChange={(e) =>
                setConfig({
                  ...config,
                  models: {
                    ...config.models,
                    defaults: { ...config.models.defaults, complex: e.target.value },
                  },
                })
              }
            />
          </label>
          <label>
            Fallback
            <input
              type="text"
              value={config.models.defaults.fallback}
              onChange={(e) =>
                setConfig({
                  ...config,
                  models: {
                    ...config.models,
                    defaults: { ...config.models.defaults, fallback: e.target.value },
                  },
                })
              }
            />
          </label>
        </div>
      </div>

      <div className="settings-panel__section">
        <h4>Модели LM Studio</h4>
        <div className="settings-panel__fields">
          {config.models.lm_studio ? (
            <>
              <label>
                Simple
                <input
                  type="text"
                  value={config.models.lm_studio.simple}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      models: {
                        ...config.models,
                        lm_studio: {
                          ...config.models.lm_studio!,
                          simple: e.target.value,
                        },
                      },
                    })
                  }
                />
              </label>
              <label>
                Medium
                <input
                  type="text"
                  value={config.models.lm_studio.medium}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      models: {
                        ...config.models,
                        lm_studio: {
                          ...config.models.lm_studio!,
                          medium: e.target.value,
                        },
                      },
                    })
                  }
                />
              </label>
              <label>
                Complex
                <input
                  type="text"
                  value={config.models.lm_studio.complex}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      models: {
                        ...config.models,
                        lm_studio: {
                          ...config.models.lm_studio!,
                          complex: e.target.value,
                        },
                      },
                    })
                  }
                />
              </label>
              <label>
                Fallback
                <input
                  type="text"
                  value={config.models.lm_studio.fallback}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      models: {
                        ...config.models,
                        lm_studio: {
                          ...config.models.lm_studio!,
                          fallback: e.target.value,
                        },
                      },
                    })
                  }
                />
              </label>
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

      {message && <p className="settings-panel__success">{message}</p>}
      {error && <p className="settings-panel__error">{error}</p>}

      <button
        type="button"
        className="settings-panel__save"
        onClick={handleSave}
        disabled={saving}
      >
        {saving ? 'Сохранение...' : 'Сохранить'}
      </button>
    </div>
  )
}
