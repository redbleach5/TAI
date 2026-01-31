import { useEffect, useState, useCallback } from 'react'
import { Loader2, CheckCircle2, XCircle, RefreshCw } from 'lucide-react'
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

  if (loading) {
    return (
      <span className="health-loading">
        <Loader2 size={14} className="icon-spin" />
        <span>Проверка...</span>
      </span>
    )
  }
  
  if (error) {
    return (
      <span className="health-error">
        <XCircle size={14} />
        <span>Сервер: {error}</span>
        <button type="button" className="health-retry" onClick={refresh}>
          <RefreshCw size={12} />
        </button>
      </span>
    )
  }
  
  if (!health) return null

  return (
    <span className={`health health-${health.llm_available ? 'available' : 'unavailable'}`}>
      {health.llm_available ? (
        <CheckCircle2 size={14} className="health__icon health__icon--success" />
      ) : (
        <XCircle size={14} className="health__icon health__icon--error" />
      )}
      <span>{health.llm_provider}: {health.llm_available ? 'работает' : 'недоступен'}</span>
      <button type="button" className="health-refresh" onClick={refresh} title="Обновить статус">
        <RefreshCw size={12} />
      </button>
    </span>
  )
}
