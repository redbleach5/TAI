import { useEffect, useState } from 'react'
import { useWorkflowCode } from '../ide/WorkflowCodeContext'
import { useWorkflowStream } from './useWorkflowStream'

type StepStatus = 'pending' | 'active' | 'done' | 'error'

interface Step {
  id: string
  label: string
}

const STEPS: Step[] = [
  { id: 'plan', label: 'План' },
  { id: 'tests', label: 'Тесты' },
  { id: 'code', label: 'Код' },
  { id: 'validation', label: 'Валидация' },
]

function getStepStatus(
  stepId: string,
  currentStep: string,
  state: { plan: string; tests: string; code: string; validationOutput: string | null },
  loading: boolean,
  hasError: boolean
): StepStatus {
  if (hasError && currentStep === 'error') return 'error'
  
  const stepOrder = ['plan', 'tests', 'code', 'validation']
  const currentIdx = stepOrder.indexOf(currentStep)
  const stepIdx = stepOrder.indexOf(stepId)
  
  if (stepIdx < currentIdx) return 'done'
  if (stepIdx === currentIdx && loading) return 'active'
  if (stepIdx === currentIdx && !loading) {
    // Check if this step has content
    if (stepId === 'plan' && state.plan) return 'done'
    if (stepId === 'tests' && state.tests) return 'done'
    if (stepId === 'code' && state.code) return 'done'
    if (stepId === 'validation' && state.validationOutput != null) return 'done'
    return loading ? 'active' : 'pending'
  }
  return 'pending'
}

export function WorkflowPanel() {
  const { state, loading, streaming, error, run } = useWorkflowStream()
  const { setState: setWorkflowCode } = useWorkflowCode()

  useEffect(() => {
    if (state.code || state.plan || state.tests) {
      setWorkflowCode({
        code: state.code || '',
        plan: state.plan || '',
        tests: state.tests || '',
      })
    }
  }, [state.code, state.plan, state.tests, setWorkflowCode])
  const [task, setTask] = useState('')
  const [useStream, setUseStream] = useState(true)

  const handleRun = () => {
    run(task, useStream)
  }

  const content = state.templateResponse ?? state.code ?? state.plan
  const hasOutput = content || state.tests || state.validationOutput != null
  const showSteps = loading || (hasOutput && !state.templateResponse)

  return (
    <div className="workflow-panel">
      <div className="workflow-panel__input">
        <input
          type="text"
          className="workflow-panel__task"
          placeholder="Опишите задачу, например: напиши функцию факториала"
          value={task}
          onChange={(e) => setTask(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleRun()}
          disabled={loading}
        />
        <label className="workflow-panel__stream">
          <input
            type="checkbox"
            checked={useStream}
            onChange={(e) => setUseStream(e.target.checked)}
          />
          Стриминг
        </label>
        <button
          type="button"
          className="workflow-panel__run"
          onClick={handleRun}
          disabled={loading || !task.trim()}
        >
          {loading ? (streaming ? 'Стриминг...' : 'Выполняется...') : 'Запустить'}
        </button>
      </div>

      {showSteps && (
        <div className="workflow-steps">
          {STEPS.map((step) => {
            const status = getStepStatus(
              step.id,
              state.currentStep,
              { plan: state.plan, tests: state.tests, code: state.code, validationOutput: state.validationOutput },
              loading,
              !!error
            )
            return (
              <div key={step.id} className={`workflow-step workflow-step--${status}`}>
                <span className="workflow-step__indicator">
                  {status === 'done' && '✓'}
                  {status === 'active' && <span className="workflow-step__spinner" />}
                  {status === 'error' && '✗'}
                  {status === 'pending' && '○'}
                </span>
                <span className="workflow-step__label">{step.label}</span>
              </div>
            )
          })}
        </div>
      )}

      {error && <p className="workflow-panel__error">{error}</p>}

      {hasOutput && (
        <div className="workflow-panel__output">
          {state.templateResponse && (
            <div className="workflow-panel__section">
              <h4>Ответ</h4>
              <pre className="workflow-panel__content">{state.templateResponse}</pre>
            </div>
          )}
          {state.plan && (
            <div className="workflow-panel__section">
              <h4>План</h4>
              {state.planThinking && (
                <details className="workflow-panel__thinking">
                  <summary>Рассуждения ({state.planThinking.length} символов)</summary>
                  <pre className="workflow-panel__content workflow-panel__content--small">
                    {state.planThinking}
                  </pre>
                </details>
              )}
              <pre className="workflow-panel__content workflow-panel__content--code">
                {state.plan}
              </pre>
            </div>
          )}
          {state.tests && (
            <div className="workflow-panel__section">
              <h4>Тесты</h4>
              {state.testsThinking && (
                <details className="workflow-panel__thinking">
                  <summary>Рассуждения ({state.testsThinking.length} символов)</summary>
                  <pre className="workflow-panel__content workflow-panel__content--small">
                    {state.testsThinking}
                  </pre>
                </details>
              )}
              <pre className="workflow-panel__content workflow-panel__content--code">
                {state.tests}
              </pre>
            </div>
          )}
          {state.code && (
            <div className="workflow-panel__section">
              <h4>Код</h4>
              {state.codeThinking && (
                <details className="workflow-panel__thinking">
                  <summary>Рассуждения ({state.codeThinking.length} символов)</summary>
                  <pre className="workflow-panel__content workflow-panel__content--small">
                    {state.codeThinking}
                  </pre>
                </details>
              )}
              <pre className="workflow-panel__content workflow-panel__content--code">
                {state.code}
              </pre>
            </div>
          )}
          {state.validationOutput != null && (
            <div className="workflow-panel__section">
              <h4>
                Валидация{' '}
                {state.validationPassed === true ? '✓' : state.validationPassed === false ? '✗' : ''}
              </h4>
              <pre className="workflow-panel__content workflow-panel__content--small">
                {state.validationOutput}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
