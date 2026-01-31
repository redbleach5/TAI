import { useState, useCallback, useEffect } from 'react'

const API_BASE = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? '/api' : '')

export interface Workspace {
  path: string
  name: string
}

export function useWorkspace() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchWorkspace = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/workspace`)
      const data = await res.json()
      setWorkspace({ path: data.path, name: data.name })
    } catch {
      setWorkspace(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchWorkspace()
  }, [fetchWorkspace])

  const openFolder = useCallback(async (path: string) => {
    const res = await fetch(`${API_BASE}/workspace`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'Failed to open folder')
    }
    const data = await res.json()
    setWorkspace({ path: data.path, name: data.name })
    return data
  }, [])

  const indexWorkspace = useCallback(async (incremental = true) => {
    const res = await fetch(
      `${API_BASE}/workspace/index?incremental=${incremental}`,
      { method: 'POST' }
    )
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'Indexing failed')
    }
    return res.json()
  }, [])

  const clearIndex = useCallback(async () => {
    const res = await fetch(`${API_BASE}/rag/clear`, { method: 'POST' })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'Failed to clear index')
    }
    return res.json()
  }, [])

  const indexWorkspaceStream = useCallback(
    async (
      onProgress: (progress: number, batch: number, total: number) => void,
      incremental = true
    ) => {
      const res = await fetch(
        `${API_BASE}/workspace/index/stream?incremental=${incremental}`,
        { method: 'POST' }
      )
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Indexing failed')
      }
      const reader = res.body?.getReader()
      if (!reader) throw new Error('No response body')
      const decoder = new TextDecoder()
      let buffer = ''
      let result: {
        stats?: {
          files_found?: number
          total_chunks?: number
          incremental?: boolean
          files_added?: number
          files_updated?: number
          files_deleted?: number
        }
      } = {}

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        // sse-starlette uses \r\n as separator; split by double newline in any form
        const blocks = buffer.split(/\r?\n\r?\n/)
        buffer = blocks.pop() ?? ''
        for (const block of blocks) {
          let eventType = ''
          let data = ''
          for (const line of block.split(/\r?\n/)) {
            if (line.startsWith('event: ')) eventType = line.slice(7).trim()
            if (line.startsWith('data: ')) data = line.slice(6).trim()
          }
          if (data) {
            try {
              const parsed = JSON.parse(data)
              if (eventType === 'progress') {
                onProgress(parsed.progress ?? 0, parsed.batch ?? 0, parsed.total ?? 0)
              } else if (eventType === 'done') {
                result = parsed
              } else if (eventType === 'error') {
                throw new Error(parsed.detail || 'Indexing failed')
              }
            } catch (e) {
              if (e instanceof SyntaxError) continue
              throw e
            }
          }
        }
      }

      return result
    },
    []
  )

  return {
    workspace,
    loading,
    fetchWorkspace,
    openFolder,
    indexWorkspace,
    indexWorkspaceStream,
    clearIndex,
  }
}
