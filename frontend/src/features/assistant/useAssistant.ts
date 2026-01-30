import { useState, useCallback, useEffect } from 'react'

export interface AssistantMode {
  id: string
  name: string
  description: string
  icon: string
}

export interface PromptTemplate {
  id: string
  name: string
  category: string
  description: string
  content?: string
}

export function useAssistant() {
  const [modes, setModes] = useState<AssistantMode[]>([])
  const [templates, setTemplates] = useState<PromptTemplate[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [currentMode, setCurrentMode] = useState<string>('default')
  const [loading, setLoading] = useState(false)

  const fetchModes = useCallback(async () => {
    try {
      const res = await fetch('/api/assistant/modes')
      const data = await res.json()
      setModes(data.modes || [])
    } catch (e) {
      console.error('Failed to fetch modes:', e)
    }
  }, [])

  const fetchTemplates = useCallback(async (category?: string) => {
    try {
      const url = category 
        ? `/api/assistant/templates?category=${category}`
        : '/api/assistant/templates'
      const res = await fetch(url)
      const data = await res.json()
      setTemplates(data.templates || [])
      setCategories(data.categories || [])
    } catch (e) {
      console.error('Failed to fetch templates:', e)
    }
  }, [])

  const getTemplate = useCallback(async (templateId: string): Promise<PromptTemplate | null> => {
    try {
      const res = await fetch(`/api/assistant/templates/${templateId}`)
      const data = await res.json()
      return data.error ? null : data
    } catch (e) {
      console.error('Failed to get template:', e)
      return null
    }
  }, [])

  const fillTemplate = useCallback(async (
    templateId: string, 
    variables: Record<string, string>
  ): Promise<string | null> => {
    try {
      const res = await fetch('/api/assistant/templates/fill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_id: templateId, variables }),
      })
      const data = await res.json()
      return data.content || null
    } catch (e) {
      console.error('Failed to fill template:', e)
      return null
    }
  }, [])

  const webSearch = useCallback(async (query: string) => {
    setLoading(true)
    try {
      const res = await fetch('/api/assistant/search/web', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, max_results: 5 }),
      })
      return await res.json()
    } catch (e) {
      console.error('Web search failed:', e)
      return { error: 'Search failed', results: [] }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchModes()
    fetchTemplates()
  }, [fetchModes, fetchTemplates])

  return {
    modes,
    templates,
    categories,
    currentMode,
    setCurrentMode,
    loading,
    fetchTemplates,
    getTemplate,
    fillTemplate,
    webSearch,
  }
}
