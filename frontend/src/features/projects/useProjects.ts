import { useState, useCallback, useEffect } from 'react'
import { API_BASE } from '../../api/client'

export interface Project {
  id: string
  name: string
  path: string
  indexed: boolean
  files_count: number
  last_indexed: string | null
}

export function useProjects() {
  const [projects, setProjects] = useState<Project[]>([])
  const [currentProject, setCurrentProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchProjects = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/projects`)
      const data = await res.json()
      setProjects(data.projects || [])
      setCurrentProject(data.current || null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load projects')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchProjects()
  }, [fetchProjects])

  const addProject = useCallback(async (name: string, path: string) => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, path }),
      })
      const data = await res.json()
      if (res.ok) {
        await fetchProjects()
        return { success: true, project: data.project }
      }
      return { success: false, error: data.detail || 'Failed' }
    } catch (e) {
      return { success: false, error: e instanceof Error ? e.message : 'Failed' }
    } finally {
      setLoading(false)
    }
  }, [fetchProjects])

  const removeProject = useCallback(async (projectId: string) => {
    try {
      const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}`, { method: 'DELETE' })
      if (res.ok) {
        await fetchProjects()
        return { success: true }
      }
      const data = await res.json()
      return { success: false, error: data.detail || 'Failed' }
    } catch (e) {
      return { success: false, error: e instanceof Error ? e.message : 'Failed' }
    }
  }, [fetchProjects])

  const selectProject = useCallback(async (projectId: string) => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/select`, { method: 'POST' })
      const data = await res.json()
      if (res.ok) {
        setCurrentProject(data.project)
        return { success: true }
      }
      return { success: false, error: data.detail || 'Failed' }
    } catch (e) {
      return { success: false, error: e instanceof Error ? e.message : 'Failed' }
    } finally {
      setLoading(false)
    }
  }, [])

  const indexProject = useCallback(async (projectId: string, incremental = true) => {
    setLoading(true)
    try {
      const res = await fetch(
        `${API_BASE}/projects/${encodeURIComponent(projectId)}/index?incremental=${incremental}`,
        { method: 'POST' }
      )
      const data = await res.json()
      if (res.ok) {
        await fetchProjects()
        return { success: true, stats: data.stats }
      }
      return { success: false, error: data.detail || 'Failed' }
    } catch (e) {
      return { success: false, error: e instanceof Error ? e.message : 'Failed' }
    } finally {
      setLoading(false)
    }
  }, [fetchProjects])

  return {
    projects,
    currentProject,
    loading,
    error,
    fetchProjects,
    addProject,
    removeProject,
    selectProject,
    indexProject,
  }
}
