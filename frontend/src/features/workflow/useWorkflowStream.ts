import { useState, useCallback } from 'react'
import {
  postWorkflow,
  streamWorkflow,
  type WorkflowRequest,
  type WorkflowStreamEvent,
} from '../../api/client'

export interface WorkflowState {
  plan: string
  tests: string
  code: string
  planThinking: string
  testsThinking: string
  codeThinking: string
  validationOutput: string | null
  validationPassed: boolean | null
  templateResponse: string | null
  intentKind: string
  currentStep: string
}

const initial: WorkflowState = {
  plan: '',
  tests: '',
  code: '',
  planThinking: '',
  testsThinking: '',
  codeThinking: '',
  validationOutput: null,
  validationPassed: null,
  templateResponse: null,
  intentKind: '',
  currentStep: '',
}

export function useWorkflowStream() {
  const [state, setState] = useState<WorkflowState>(initial)
  const [loading, setLoading] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)

  const run = useCallback(async (task: string, useStream = false) => {
    if (!task.trim() || loading) return

    setLoading(true)
    setStreaming(useStream)
    setError(null)
    setState(initial)

    const request: WorkflowRequest = { task: task.trim() }

    try {
      if (useStream) {
        for await (const evt of streamWorkflow(request)) {
          handleStreamEvent(evt, setState, setSessionId, setError)
        }
      } else {
        const resp = await postWorkflow(request)
        setSessionId(resp.session_id)
        setState({
          plan: resp.plan ?? '',
          tests: resp.tests ?? '',
          code: resp.code ?? '',
          planThinking: '',
          testsThinking: '',
          codeThinking: '',
          validationOutput: resp.validation_output ?? null,
          validationPassed: resp.validation_passed ?? null,
          templateResponse: resp.intent_kind === 'greeting' || resp.intent_kind === 'help' ? resp.content : null,
          intentKind: resp.intent_kind,
          currentStep: resp.validation_passed != null ? 'validation' : 'code',
        })
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
      setStreaming(false)
    }
  }, [loading])

  return { state, loading, streaming, error, sessionId, run }
}

function handleStreamEvent(
  evt: WorkflowStreamEvent,
  setState: React.Dispatch<React.SetStateAction<WorkflowState>>,
  setSessionId: React.Dispatch<React.SetStateAction<string | null>>,
  setError: React.Dispatch<React.SetStateAction<string | null>>
) {
  if (evt.event_type === 'done' && evt.payload) {
    const p = evt.payload
    setSessionId((p.session_id as string) ?? null)
    setState((s) => ({
      ...s,
      plan: (p.plan as string) ?? s.plan,
      tests: (p.tests as string) ?? s.tests,
      code: (p.code as string) ?? s.code,
      validationOutput: (p.validation_output as string) ?? s.validationOutput,
      validationPassed: (p.validation_passed as boolean) ?? s.validationPassed,
      templateResponse: (p.template_response as string) ?? s.templateResponse,
      intentKind: (p.intent_kind as string) ?? s.intentKind,
      currentStep: 'validation',
    }))
    return
  }
  if (evt.event_type === 'error' && evt.chunk) {
    setError(evt.chunk)
    setState((s) => ({ ...s, currentStep: 'error' }))
    return
  }
  if (evt.chunk) {
    setState((s) => {
      const next = { ...s }
      switch (evt.event_type) {
        case 'plan':
          next.plan += evt.chunk
          next.currentStep = 'plan'
          break
        case 'tests':
          next.tests += evt.chunk
          next.currentStep = 'tests'
          break
        case 'code':
          next.code += evt.chunk
          next.currentStep = 'code'
          break
        case 'plan_thinking':
          next.planThinking += evt.chunk
          break
        case 'tests_thinking':
          next.testsThinking += evt.chunk
          break
        case 'code_thinking':
          next.codeThinking += evt.chunk
          break
        default:
          break
      }
      return next
    })
  }
}
