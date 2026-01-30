import { useEffect, useState, useCallback } from 'react'
import { getHealth, type HealthResponse } from '../../api/client'

export function HealthStatus() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(() => {
    setLoading(true)
    setError(null)
    getHealth()
      .then(setHealth)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  if (loading) return <span className="health-loading">Проверка...</span>
  if (error) {
    return (
      <span className="health-error">
        Сервер: {error}{' '}
        <button type="button" className="health-retry" onClick={refresh}>
          ↻
        </button>
      </span>
    )
  }
  if (!health) return null

  return (
    <span className={`health health-${health.llm_available ? 'available' : 'unavailable'}`}>
      {health.llm_provider}: {health.llm_available ? 'работает' : 'недоступен'}
      <button type="button" className="health-refresh" onClick={refresh} title="Обновить статус">
        ↻
      </button>
    </span>
  )
}
