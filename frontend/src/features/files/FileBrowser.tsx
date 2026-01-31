import { useEffect, useState, useCallback } from 'react'
import { 
  File, 
  FileCode, 
  FileText, 
  FileJson,
  Folder, 
  FolderOpen, 
  ChevronRight, 
  ChevronDown,
  RefreshCw,
  FilePlus,
  FolderPlus,
  Pencil,
  Trash2,
  Settings,
  Palette,
  Terminal as TerminalIcon
} from 'lucide-react'
import { useFileTree } from './useFileTree'
import type { FileNode } from './useFileTree'
import { useToast } from '../toast/ToastContext'

interface FileBrowserProps {
  onFileSelect: (path: string) => void
  gitStatus?: Record<string, string>  // path -> status (M, A, ?, etc.)
  onOpenFolder?: () => void
}

// File extension to icon component mapping with colors
const FILE_ICON_CONFIG: Record<string, { icon: typeof File; color?: string }> = {
  py: { icon: FileCode, color: '#f7df1e' },      // Python - yellow
  ts: { icon: FileCode, color: '#3178c6' },      // TypeScript - blue
  tsx: { icon: FileCode, color: '#61dafb' },     // TSX - React blue
  js: { icon: FileCode, color: '#f7df1e' },      // JavaScript - yellow
  jsx: { icon: FileCode, color: '#61dafb' },     // JSX - React blue
  json: { icon: FileJson, color: '#cbcb41' },    // JSON
  md: { icon: FileText, color: '#519aba' },      // Markdown
  toml: { icon: Settings, color: '#9b9b9b' },    // Config
  yaml: { icon: Settings, color: '#9b9b9b' },    // Config
  yml: { icon: Settings, color: '#9b9b9b' },     // Config
  css: { icon: Palette, color: '#563d7c' },      // CSS - purple
  html: { icon: FileCode, color: '#e34c26' },    // HTML - orange
  txt: { icon: FileText },                        // Text
  sh: { icon: TerminalIcon, color: '#4eaa25' },  // Shell - green
  default: { icon: File },                        // Default file
}

const GIT_STATUS_LABELS: Record<string, { label: string; color: string }> = {
  'M': { label: 'M', color: '#e2b93d' },  // Modified
  'A': { label: 'A', color: '#73c991' },  // Added
  'D': { label: 'D', color: '#f14c4c' },  // Deleted
  '?': { label: 'U', color: '#6e6e6e' },  // Untracked
  'R': { label: 'R', color: '#73c991' },  // Renamed
  'U': { label: 'C', color: '#f14c4c' },  // Conflict
}

function getFileIconConfig(node: FileNode) {
  const config = FILE_ICON_CONFIG[node.extension || ''] || FILE_ICON_CONFIG.default
  return config
}

interface TreeNodeProps {
  node: FileNode
  depth: number
  onSelect: (path: string) => void
  expandedPaths: Set<string>
  onToggle: (path: string) => void
  gitStatus?: Record<string, string>
  onContextMenu: (e: React.MouseEvent, node: FileNode) => void
}

function TreeNode({ 
  node, 
  depth, 
  onSelect, 
  expandedPaths, 
  onToggle,
  gitStatus,
  onContextMenu,
}: TreeNodeProps) {
  const isExpanded = expandedPaths.has(node.path)
  const isDir = node.type === 'directory'
  const status = gitStatus?.[node.path]
  const statusInfo = status ? GIT_STATUS_LABELS[status] : null

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (isDir) {
      onToggle(node.path)
    } else {
      onSelect(node.path)
    }
  }

  const handleDoubleClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!isDir) {
      onSelect(node.path)
    }
  }

  const iconConfig = getFileIconConfig(node)
  const IconComponent = iconConfig.icon
  const FolderIcon = isExpanded ? FolderOpen : Folder

  return (
    <div className="tree-node">
      <div 
        className={`tree-node__row ${isDir ? 'tree-node__row--dir' : ''}`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
        onClick={handleClick}
        onDoubleClick={handleDoubleClick}
        onContextMenu={(e) => onContextMenu(e, node)}
      >
        {isDir && (
          <span className="tree-node__chevron">
            {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          </span>
        )}
        <span className="tree-node__icon">
          {isDir ? (
            <FolderIcon size={16} style={{ color: '#dcb67a' }} />
          ) : (
            <IconComponent size={16} style={{ color: iconConfig.color }} />
          )}
        </span>
        <span className="tree-node__name">{node.name}</span>
        {statusInfo && (
          <span 
            className="tree-node__status"
            style={{ color: statusInfo.color }}
            title={`Git: ${status}`}
          >
            {statusInfo.label}
          </span>
        )}
      </div>
      {isDir && isExpanded && node.children && (
        <div className="tree-node__children">
          {node.children.map((child) => (
            <TreeNode
              key={child.path}
              node={child}
              depth={depth + 1}
              onSelect={onSelect}
              expandedPaths={expandedPaths}
              onToggle={onToggle}
              gitStatus={gitStatus}
              onContextMenu={onContextMenu}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface ContextMenu {
  x: number
  y: number
  node: FileNode
}

export function FileBrowser({ onFileSelect, gitStatus, onOpenFolder }: FileBrowserProps) {
  const { tree, loading, error, fetchTree, createFile, deleteFile, renameFile } = useFileTree()
  const { show: showToast } = useToast()
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set(['.']))
  const [contextMenu, setContextMenu] = useState<ContextMenu | null>(null)
  const [renaming, setRenaming] = useState<{ path: string; name: string } | null>(null)
  const [creating, setCreating] = useState<{ parentPath: string; isDir: boolean } | null>(null)
  const [newName, setNewName] = useState('')

  useEffect(() => {
    fetchTree()
  }, [fetchTree])

  useEffect(() => {
    const onWorkspaceChanged = () => fetchTree()
    window.addEventListener('workspace-changed', onWorkspaceChanged)
    return () => window.removeEventListener('workspace-changed', onWorkspaceChanged)
  }, [fetchTree])

  const handleToggle = useCallback((path: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      return next
    })
  }, [])

  const handleContextMenu = useCallback((e: React.MouseEvent, node: FileNode) => {
    e.preventDefault()
    setContextMenu({ x: e.clientX, y: e.clientY, node })
  }, [])

  const closeContextMenu = useCallback(() => {
    setContextMenu(null)
  }, [])

  useEffect(() => {
    const handleClick = () => closeContextMenu()
    document.addEventListener('click', handleClick)
    return () => document.removeEventListener('click', handleClick)
  }, [closeContextMenu])

  const handleNewFile = async () => {
    if (!contextMenu) return
    const parentPath = contextMenu.node.type === 'directory' 
      ? contextMenu.node.path 
      : contextMenu.node.path.split('/').slice(0, -1).join('/') || '.'
    setCreating({ parentPath, isDir: false })
    setNewName('')
    closeContextMenu()
  }

  const handleNewFolder = async () => {
    if (!contextMenu) return
    const parentPath = contextMenu.node.type === 'directory' 
      ? contextMenu.node.path 
      : contextMenu.node.path.split('/').slice(0, -1).join('/') || '.'
    setCreating({ parentPath, isDir: true })
    setNewName('')
    closeContextMenu()
  }

  const handleRename = () => {
    if (!contextMenu) return
    setRenaming({ path: contextMenu.node.path, name: contextMenu.node.name })
    setNewName(contextMenu.node.name)
    closeContextMenu()
  }

  const handleDelete = async () => {
    if (!contextMenu) return
    const node = contextMenu.node
    closeContextMenu()
    
    if (!confirm(`Удалить ${node.name}?`)) return
    
    const result = await deleteFile(node.path)
    if (result.success) {
      showToast('Удалено', 'success')
    } else {
      showToast(result.error || 'Что-то пошло не так', 'error')
    }
  }

  const submitCreate = async () => {
    if (!creating || !newName.trim()) return
    const path = creating.parentPath === '.' 
      ? newName.trim() 
      : `${creating.parentPath}/${newName.trim()}`
    
    const result = await createFile(path, creating.isDir)
    if (result.success) {
      showToast('Создано', 'success')
      // Expand parent folder
      setExpandedPaths((prev) => new Set([...prev, creating.parentPath]))
    } else {
      showToast(result.error || 'Что-то пошло не так', 'error')
    }
    setCreating(null)
    setNewName('')
  }

  const submitRename = async () => {
    if (!renaming || !newName.trim()) return
    const parentPath = renaming.path.split('/').slice(0, -1).join('/') || '.'
    const newPath = parentPath === '.' 
      ? newName.trim() 
      : `${parentPath}/${newName.trim()}`
    
    const result = await renameFile(renaming.path, newPath)
    if (result.success) {
      showToast('Переименовано', 'success')
    } else {
      showToast(result.error || 'Что-то пошло не так', 'error')
    }
    setRenaming(null)
    setNewName('')
  }

  const handleRefresh = () => {
    fetchTree()
  }

  return (
    <div className="file-browser">
      <div className="file-browser__header">
        <span className="file-browser__title">Explorer</span>
        <div className="file-browser__actions">
          {onOpenFolder && (
            <button
              type="button"
              className="file-browser__action"
              onClick={onOpenFolder}
              title="Открыть папку"
            >
              <FolderOpen size={14} />
            </button>
          )}
          <button
            type="button"
            className="file-browser__action"
            onClick={handleRefresh}
            title="Обновить"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>
      
      <div className="file-browser__content">
        {loading && <div className="file-browser__loading">Загрузка...</div>}
        {error && <div className="file-browser__error">{error}</div>}
        {tree && (
          <TreeNode
            node={tree}
            depth={0}
            onSelect={onFileSelect}
            expandedPaths={expandedPaths}
            onToggle={handleToggle}
            gitStatus={gitStatus}
            onContextMenu={handleContextMenu}
          />
        )}
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <div 
          className="context-menu"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          <button onClick={handleNewFile}>
            <FilePlus size={14} />
            <span>Новый файл</span>
          </button>
          <button onClick={handleNewFolder}>
            <FolderPlus size={14} />
            <span>Новая папка</span>
          </button>
          <button onClick={handleRename}>
            <Pencil size={14} />
            <span>Переименовать</span>
          </button>
          <button onClick={handleDelete} className="context-menu__delete">
            <Trash2 size={14} />
            <span>Удалить</span>
          </button>
        </div>
      )}

      {/* Create Dialog */}
      {creating && (
        <div className="file-browser__dialog-overlay">
          <div className="file-browser__dialog">
            <h4>{creating.isDir ? 'Новая папка' : 'Новый файл'}</h4>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder={creating.isDir ? 'folder-name' : 'filename.py'}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') submitCreate()
                if (e.key === 'Escape') setCreating(null)
              }}
            />
            <div className="file-browser__dialog-actions">
              <button onClick={() => setCreating(null)}>Отмена</button>
              <button onClick={submitCreate} className="primary">Создать</button>
            </div>
          </div>
        </div>
      )}

      {/* Rename Dialog */}
      {renaming && (
        <div className="file-browser__dialog-overlay">
          <div className="file-browser__dialog">
            <h4>Переименовать</h4>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') submitRename()
                if (e.key === 'Escape') setRenaming(null)
              }}
            />
            <div className="file-browser__dialog-actions">
              <button onClick={() => setRenaming(null)}>Отмена</button>
              <button onClick={submitRename} className="primary">Переименовать</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
