import { useState, useCallback } from 'react'

export interface FileNode {
  name: string
  path: string
  type: 'file' | 'directory'
  children: FileNode[] | null
  size: number | null
  extension: string | null
}

interface TreeResponse {
  success: boolean
  tree: FileNode | null
  error: string | null
}

export function useFileTree() {
  const [tree, setTree] = useState<FileNode | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchTree = useCallback(async (path: string = '.') => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/files/tree?path=${encodeURIComponent(path)}`)
      const data: TreeResponse = await res.json()
      if (data.success && data.tree) {
        setTree(data.tree)
      } else {
        setError(data.error || 'Failed to load file tree')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load file tree')
    } finally {
      setLoading(false)
    }
  }, [])

  const createFile = useCallback(async (path: string, isDirectory: boolean = false) => {
    try {
      const res = await fetch('/api/files/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, is_directory: isDirectory }),
      })
      const data = await res.json()
      if (data.success) {
        await fetchTree()
        return { success: true }
      }
      return { success: false, error: data.error || data.detail }
    } catch (e) {
      return { success: false, error: e instanceof Error ? e.message : 'Failed' }
    }
  }, [fetchTree])

  const deleteFile = useCallback(async (path: string) => {
    try {
      const res = await fetch(`/api/files/delete?path=${encodeURIComponent(path)}`, {
        method: 'DELETE',
      })
      const data = await res.json()
      if (data.success) {
        await fetchTree()
        return { success: true }
      }
      return { success: false, error: data.error || data.detail }
    } catch (e) {
      return { success: false, error: e instanceof Error ? e.message : 'Failed' }
    }
  }, [fetchTree])

  const renameFile = useCallback(async (oldPath: string, newPath: string) => {
    try {
      const res = await fetch('/api/files/rename', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_path: oldPath, new_path: newPath }),
      })
      const data = await res.json()
      if (data.success) {
        await fetchTree()
        return { success: true }
      }
      return { success: false, error: data.error || data.detail }
    } catch (e) {
      return { success: false, error: e instanceof Error ? e.message : 'Failed' }
    }
  }, [fetchTree])

  return {
    tree,
    loading,
    error,
    fetchTree,
    createFile,
    deleteFile,
    renameFile,
  }
}
