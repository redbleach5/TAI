import { useState, useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? '/api' : '')

export interface BrowseDir {
  path: string
  name: string
}

export interface BrowseResult {
  dirs: BrowseDir[]
  parent: string | null
  error?: string
}

export function useBrowse() {
  const [currentPath, setCurrentPath] = useState<string | null>(null)
  const [dirs, setDirs] = useState<BrowseDir[]>([])
  const [parent, setParent] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchDirs = useCallback(async (path: string = '') => {
    setLoading(true)
    setError(null)
    try {
      const url = path
        ? `${API_BASE}/files/browse?path=${encodeURIComponent(path)}`
        : `${API_BASE}/files/browse`
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 15000)
      const res = await fetch(url, { signal: controller.signal })
      clearTimeout(timeoutId)
      if (!res.ok) {
        throw new Error(res.statusText || `HTTP ${res.status}`)
      }
      const data = await res.json()
      setDirs(data.dirs || [])
      setParent(data.parent ?? null)
      setCurrentPath(path || null)
    } catch (e) {
      const isAbort = e instanceof Error && e.name === 'AbortError'
      const msg = isAbort ? 'Таймаут. Проверьте, что backend запущен.' : (e instanceof Error ? e.message : 'Failed to load')
      setError(msg)
      setDirs([])
      setParent(null)
    } finally {
      setLoading(false)
    }
  }, [])

  const selectDir = useCallback((path: string) => {
    fetchDirs(path)
  }, [fetchDirs])

  const goUp = useCallback(() => {
    if (parent) {
      fetchDirs(parent)
    }
  }, [parent, fetchDirs])

  return {
    dirs,
    parent,
    currentPath,
    loading,
    error,
    fetchDirs,
    selectDir,
    goUp,
  }
}
