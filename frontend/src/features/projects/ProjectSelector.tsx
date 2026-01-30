import { useState } from 'react'
import { useProjects } from './useProjects'
import type { Project } from './useProjects'
import { useToast } from '../toast/ToastContext'

export function ProjectSelector() {
  const { show: showToast } = useToast()
  const {
    projects,
    currentProject,
    loading,
    addProject,
    removeProject,
    selectProject,
    indexProject,
  } = useProjects()

  const [showAddForm, setShowAddForm] = useState(false)
  const [newName, setNewName] = useState('')
  const [newPath, setNewPath] = useState('')
  const [indexingId, setIndexingId] = useState<string | null>(null)

  const handleAdd = async () => {
    if (!newName.trim() || !newPath.trim()) {
      showToast('Name and path are required', 'error')
      return
    }
    const result = await addProject(newName.trim(), newPath.trim())
    if (result.success) {
      showToast(`Added project: ${newName}`, 'success')
      setShowAddForm(false)
      setNewName('')
      setNewPath('')
    } else {
      showToast(result.error || 'Failed to add project', 'error')
    }
  }

  const handleSelect = async (project: Project) => {
    const result = await selectProject(project.id)
    if (result.success) {
      showToast(`Selected: ${project.name}`, 'success')
    } else {
      showToast(result.error || 'Failed to select', 'error')
    }
  }

  const handleIndex = async (project: Project) => {
    setIndexingId(project.id)
    showToast(`Indexing ${project.name}...`, 'info')
    const result = await indexProject(project.id)
    setIndexingId(null)
    if (result.success) {
      const stats = result.stats
      showToast(
        `Indexed ${stats?.files_found || 0} files, ${stats?.total_chunks || 0} chunks`,
        'success'
      )
    } else {
      showToast(result.error || 'Indexing failed', 'error')
    }
  }

  const handleRemove = async (project: Project) => {
    if (!confirm(`Remove project "${project.name}"?`)) return
    const result = await removeProject(project.id)
    if (result.success) {
      showToast(`Removed: ${project.name}`, 'success')
    } else {
      showToast(result.error || 'Failed to remove', 'error')
    }
  }

  return (
    <div className="project-selector">
      <div className="project-selector__header">
        <h3>Projects</h3>
        <button
          className="project-selector__add-btn"
          onClick={() => setShowAddForm(!showAddForm)}
        >
          {showAddForm ? 'Cancel' : '+ Add'}
        </button>
      </div>

      {showAddForm && (
        <div className="project-selector__form">
          <input
            type="text"
            placeholder="Project name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <input
            type="text"
            placeholder="Path (e.g., /Users/me/project)"
            value={newPath}
            onChange={(e) => setNewPath(e.target.value)}
          />
          <button onClick={handleAdd} disabled={loading}>
            Add Project
          </button>
        </div>
      )}

      <div className="project-selector__list">
        {projects.length === 0 ? (
          <div className="project-selector__empty">
            No projects. Add one to get started.
          </div>
        ) : (
          projects.map((project) => (
            <div
              key={project.id}
              className={`project-item ${currentProject?.id === project.id ? 'project-item--current' : ''}`}
            >
              <div className="project-item__info" onClick={() => handleSelect(project)}>
                <div className="project-item__name">
                  {project.name}
                  {currentProject?.id === project.id && (
                    <span className="project-item__current-badge">current</span>
                  )}
                </div>
                <div className="project-item__path">{project.path}</div>
                {project.indexed && (
                  <div className="project-item__stats">
                    {project.files_count} files indexed
                    {project.last_indexed && (
                      <span> · {new Date(project.last_indexed).toLocaleDateString()}</span>
                    )}
                  </div>
                )}
              </div>
              <div className="project-item__actions">
                <button
                  onClick={() => handleIndex(project)}
                  disabled={indexingId === project.id}
                  title="Index project"
                >
                  {indexingId === project.id ? '...' : '⟳'}
                </button>
                <button
                  onClick={() => handleRemove(project)}
                  className="project-item__remove"
                  title="Remove"
                >
                  ✕
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {currentProject && (
        <div className="project-selector__current">
          <strong>Active:</strong> {currentProject.name}
        </div>
      )}
    </div>
  )
}
