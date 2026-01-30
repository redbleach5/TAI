import { createContext, useContext, useState, type ReactNode } from 'react'

export interface WorkflowCodeState {
  code: string
  plan: string
  tests: string
}

const initial: WorkflowCodeState = {
  code: '',
  plan: '',
  tests: '',
}

const WorkflowCodeContext = createContext<{
  state: WorkflowCodeState
  setState: React.Dispatch<React.SetStateAction<WorkflowCodeState>>
} | null>(null)

export function WorkflowCodeProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<WorkflowCodeState>(initial)
  return (
    <WorkflowCodeContext.Provider value={{ state, setState }}>
      {children}
    </WorkflowCodeContext.Provider>
  )
}

export function useWorkflowCode() {
  const ctx = useContext(WorkflowCodeContext)
  if (!ctx) throw new Error('useWorkflowCode must be used within WorkflowCodeProvider')
  return ctx
}
