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
    const ollama = config.ollama
      ? {
          host: config.ollama.host,
          timeout: config.ollama.timeout,
          ...(config.ollama.num_ctx != null && { num_ctx: config.ollama.num_ctx }),
          ...(config.ollama.num_predict != null && { num_predict: config.ollama.num_predict }),
        }
      : undefined
    const openai_compatible = config.openai_compatible
      ? {
          base_url: config.openai_compatible.base_url,
          timeout: config.openai_compatible.timeout,
          ...(config.openai_compatible.max_tokens != null && {
            max_tokens: config.openai_compatible.max_tokens,
          }),
        }
      : undefined
    const updates: ConfigPatch = {
      llm: { provider: config.llm.provider },
      models: {
        defaults: config.models.defaults,
        lm_studio: config.models.lm_studio ?? undefined,
      },
      ...(ollama && { ollama }),
      ...(openai_compatible && { openai_compatible }),
      embeddings: { model: config.embeddings.model },
      ...(config.persistence != null && {
        persistence: { max_context_messages: config.persistence.max_context_messages },
      }),
      ...(config.web_search != null && {
        web_search: {
          searxng_url: config.web_search.searxng_url ?? '',
          brave_api_key: config.web_search.brave_api_key ?? '',
          tavily_api_key: config.web_search.tavily_api_key ?? '',
          google_api_key: config.web_search.google_api_key ?? '',
          google_cx: config.web_search.google_cx ?? '',
        },
      }),
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
        <h4>Ollama (хост и производительность)</h4>
        <div className="settings-panel__fields">
          <label>
            Host (URL)
            <input
              type="text"
              value={config.ollama?.host ?? 'http://localhost:11434'}
              onChange={(e) =>
                setConfig({
                  ...config,
                  ollama: { ...(config.ollama ?? {}), host: e.target.value, timeout: config.ollama?.timeout ?? 120 } as ConfigResponse['ollama'],
                })
              }
            />
          </label>
          <label>
            Timeout (сек)
            <input
              type="number"
              min={30}
              max={600}
              value={config.ollama?.timeout ?? 120}
              onChange={(e) =>
                setConfig({
                  ...config,
                  ollama: { ...(config.ollama ?? {}), host: config.ollama?.host ?? 'http://localhost:11434', timeout: parseInt(e.target.value, 10) || 120 } as ConfigResponse['ollama'],
                })
              }
            />
          </label>
          <label>
            num_ctx (контекст, пусто = по умолчанию)
            <input
              type="number"
              min={0}
              placeholder="4096, 32768, 131072"
              value={config.ollama?.num_ctx ?? ''}
              onChange={(e) => {
                const v = e.target.value
                const n = v === '' ? undefined : parseInt(v, 10)
                setConfig({
                  ...config,
                  ollama: { ...(config.ollama ?? {}), num_ctx: n === undefined || Number.isNaN(n) ? undefined : n } as ConfigResponse['ollama'],
                })
              }}
            />
          </label>
          <label>
            num_predict (макс. токенов, −1 = без лимита)
            <input
              type="number"
              min={-1}
              placeholder="пусто = по умолчанию"
              value={config.ollama?.num_predict ?? ''}
              onChange={(e) => {
                const v = e.target.value
                const n = v === '' ? undefined : parseInt(v, 10)
                setConfig({
                  ...config,
                  ollama: { ...(config.ollama ?? {}), num_predict: n === undefined || Number.isNaN(n) ? undefined : n } as ConfigResponse['ollama'],
                })
              }}
            />
          </label>
        </div>
      </div>

      <div className="settings-panel__section">
        <h4>LM Studio / OpenAI-совместимый</h4>
        <div className="settings-panel__fields">
          <label>
            Base URL
            <input
              type="text"
              value={config.openai_compatible?.base_url ?? 'http://localhost:1234/v1'}
              onChange={(e) =>
                setConfig({
                  ...config,
                  openai_compatible: { ...(config.openai_compatible ?? {}), base_url: e.target.value, timeout: config.openai_compatible?.timeout ?? 120 } as ConfigResponse['openai_compatible'],
                })
              }
            />
          </label>
          <label>
            Timeout (сек)
            <input
              type="number"
              min={30}
              max={600}
              value={config.openai_compatible?.timeout ?? 120}
              onChange={(e) =>
                setConfig({
                  ...config,
                  openai_compatible: { ...(config.openai_compatible ?? {}), base_url: config.openai_compatible?.base_url ?? 'http://localhost:1234/v1', timeout: parseInt(e.target.value, 10) || 120 } as ConfigResponse['openai_compatible'],
                })
              }
            />
          </label>
          <label>
            max_tokens (пусто = по умолчанию)
            <input
              type="number"
              min={1}
              placeholder="8192, 16384"
              value={config.openai_compatible?.max_tokens ?? ''}
              onChange={(e) => {
                const v = e.target.value
                const n = v === '' ? undefined : parseInt(v, 10)
                setConfig({
                  ...config,
                  openai_compatible: { ...(config.openai_compatible ?? {}), max_tokens: n === undefined || Number.isNaN(n) ? undefined : n } as ConfigResponse['openai_compatible'],
                })
              }}
            />
          </label>
        </div>
      </div>

      <div className="settings-panel__section">
        <h4>Веб-поиск (@web)</h4>
        <p className="settings-panel__muted">
          SearXNG (свой URL или публичные), Brave, Tavily — по образцу Cherry Studio.
        </p>
        <div className="settings-panel__fields">
          <label>
            SearXNG URL (пусто = публичные инстансы)
            <input
              type="text"
              placeholder="http://localhost:8080"
              value={config.web_search?.searxng_url ?? ''}
              onChange={(e) =>
                setConfig({
                  ...config,
                  web_search: {
                    searxng_url: e.target.value,
                    brave_api_key: config.web_search?.brave_api_key ?? '',
                    tavily_api_key: config.web_search?.tavily_api_key ?? '',
                    google_api_key: config.web_search?.google_api_key ?? '',
                    google_cx: config.web_search?.google_cx ?? '',
                  },
                })
              }
            />
          </label>
          <label>
            Brave API Key (2000 бесплатно/мес)
            <input
              type="password"
              autoComplete="off"
              placeholder="опционально"
              value={config.web_search?.brave_api_key ?? ''}
              onChange={(e) =>
                setConfig({
                  ...config,
                  web_search: {
                    searxng_url: config.web_search?.searxng_url ?? '',
                    brave_api_key: e.target.value,
                    tavily_api_key: config.web_search?.tavily_api_key ?? '',
                    google_api_key: config.web_search?.google_api_key ?? '',
                    google_cx: config.web_search?.google_cx ?? '',
                  },
                })
              }
            />
          </label>
          <label>
            Tavily API Key (app.tavily.com)
            <input
              type="password"
              autoComplete="off"
              placeholder="опционально"
              value={config.web_search?.tavily_api_key ?? ''}
              onChange={(e) =>
                setConfig({
                  ...config,
                  web_search: {
                    searxng_url: config.web_search?.searxng_url ?? '',
                    brave_api_key: config.web_search?.brave_api_key ?? '',
                    tavily_api_key: e.target.value,
                    google_api_key: config.web_search?.google_api_key ?? '',
                    google_cx: config.web_search?.google_cx ?? '',
                  },
                })
              }
            />
          </label>
          <label>
            Google API Key (Custom Search, 100 бесплатно/день)
            <input
              type="password"
              autoComplete="off"
              placeholder="опционально"
              value={config.web_search?.google_api_key ?? ''}
              onChange={(e) =>
                setConfig({
                  ...config,
                  web_search: {
                    searxng_url: config.web_search?.searxng_url ?? '',
                    brave_api_key: config.web_search?.brave_api_key ?? '',
                    tavily_api_key: config.web_search?.tavily_api_key ?? '',
                    google_api_key: e.target.value,
                    google_cx: config.web_search?.google_cx ?? '',
                  },
                })
              }
            />
          </label>
          <label>
            Google Search Engine ID (cx, programmablesearchengine.google.com)
            <input
              type="text"
              placeholder="опционально, нужен вместе с Google API Key"
              value={config.web_search?.google_cx ?? ''}
              onChange={(e) =>
                setConfig({
                  ...config,
                  web_search: {
                    searxng_url: config.web_search?.searxng_url ?? '',
                    brave_api_key: config.web_search?.brave_api_key ?? '',
                    tavily_api_key: config.web_search?.tavily_api_key ?? '',
                    google_api_key: config.web_search?.google_api_key ?? '',
                    google_cx: e.target.value,
                  },
                })
              }
            />
          </label>
        </div>
      </div>

      <div className="settings-panel__section">
        <h4>Контекст чата</h4>
        <label>
          Макс. сообщений в контексте (история для модели)
          <input
            type="number"
            min={5}
            max={200}
            value={config.persistence?.max_context_messages ?? 20}
            onChange={(e) =>
              setConfig({
                ...config,
                persistence: { max_context_messages: parseInt(e.target.value, 10) || 20 },
              })
            }
          />
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
