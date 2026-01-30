import { useState, useCallback, useEffect } from 'react'

export interface GitFile {
  path: string
  status: string
  staged: boolean
}

export interface GitLogEntry {
  hash: string
  short_hash: string
  author: string
  date: string
  message: string
}

interface GitStatusData {
  branch: string | null
  files: GitFile[]
  ahead: number
  behind: number
}

export function useGitStatus(pollInterval: number = 5000) {
  const [status, setStatus] = useState<GitStatusData | null>(null)
  const [log, setLog] = useState<GitLogEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/git/status')
      const data = await res.json()
      if (data.success) {
        setStatus({
          branch: data.branch,
          files: data.files,
          ahead: data.ahead,
          behind: data.behind,
        })
        setError(null)
      } else {
        setError(data.error || 'Failed to get git status')
        setStatus(null)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed')
    }
  }, [])

  const fetchLog = useCallback(async (limit: number = 20) => {
    try {
      const res = await fetch(`/api/git/log?limit=${limit}`)
      const data = await res.json()
      if (data.success) {
        setLog(data.entries)
      }
    } catch (e) {
      console.error('Failed to fetch git log:', e)
    }
  }, [])

  const getDiff = useCallback(async (path?: string, staged: boolean = false) => {
    try {
      let url = '/api/git/diff'
      const params = new URLSearchParams()
      if (path) params.set('path', path)
      if (staged) params.set('staged', 'true')
      if (params.toString()) url += '?' + params.toString()
      
      const res = await fetch(url)
      const data = await res.json()
      return data.success ? data.diff : null
    } catch {
      return null
    }
  }, [])

  const commit = useCallback(async (message: string, files?: string[]) => {
    setLoading(true)
    try {
      const res = await fetch('/api/git/commit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, files }),
      })
      const data = await res.json()
      if (data.success) {
        await fetchStatus()
        await fetchLog()
        return { success: true, hash: data.hash }
      }
      return { success: false, error: data.error }
    } catch (e) {
      return { success: false, error: e instanceof Error ? e.message : 'Commit failed' }
    } finally {
      setLoading(false)
    }
  }, [fetchStatus, fetchLog])

  // Initial fetch
  useEffect(() => {
    fetchStatus()
    fetchLog()
  }, [fetchStatus, fetchLog])

  // Polling
  useEffect(() => {
    const interval = setInterval(fetchStatus, pollInterval)
    return () => clearInterval(interval)
  }, [fetchStatus, pollInterval])

  // Build a map for file browser
  const fileStatusMap = useCallback(() => {
    const map: Record<string, string> = {}
    status?.files.forEach((f) => {
      map[f.path] = f.status
    })
    return map
  }, [status])

  return {
    status,
    log,
    loading,
    error,
    fetchStatus,
    fetchLog,
    getDiff,
    commit,
    fileStatusMap,
  }
}
