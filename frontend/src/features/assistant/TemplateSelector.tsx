import { useState } from 'react'
import type { PromptTemplate } from './useAssistant'

interface Props {
  templates: PromptTemplate[]
  categories: string[]
  onSelect: (template: PromptTemplate) => void
  onClose: () => void
}

export function TemplateSelector({ templates, categories, onSelect, onClose }: Props) {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)

  const filteredTemplates = selectedCategory 
    ? templates.filter(t => t.category === selectedCategory)
    : templates

  return (
    <div className="template-selector">
      <div className="template-selector__header">
        <h4>Prompt Templates</h4>
        <button className="template-selector__close" onClick={onClose}>✕</button>
      </div>

      <div className="template-selector__categories">
        <button
          className={`template-selector__category ${!selectedCategory ? 'template-selector__category--active' : ''}`}
          onClick={() => setSelectedCategory(null)}
        >
          All
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            className={`template-selector__category ${selectedCategory === cat ? 'template-selector__category--active' : ''}`}
            onClick={() => setSelectedCategory(cat)}
          >
            {cat}
          </button>
        ))}
      </div>

      <div className="template-selector__list">
        {filteredTemplates.map((template) => (
          <button
            key={template.id}
            className="template-selector__item"
            onClick={() => onSelect(template)}
          >
            <div className="template-selector__item-name">{template.name}</div>
            <div className="template-selector__item-desc">{template.description}</div>
          </button>
        ))}
      </div>
    </div>
  )
}
