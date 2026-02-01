import { useState, useRef, useCallback, useEffect, type ReactNode } from 'react'

interface TooltipProps {
  children: ReactNode
  text: string
  /** Side of the trigger to show tooltip */
  side?: 'top' | 'bottom' | 'left' | 'right'
}

const DELAY_MS = 400

export function Tooltip({ children, text, side = 'top' }: TooltipProps) {
  const [show, setShow] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearTimer = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
  }, [])

  const onEnter = useCallback(() => {
    clearTimer()
    timeoutRef.current = setTimeout(() => setShow(true), DELAY_MS)
  }, [clearTimer])

  const onLeave = useCallback(() => {
    clearTimer()
    setShow(false)
  }, [clearTimer])

  useEffect(() => () => clearTimer(), [clearTimer])

  return (
    <span
      className="tooltip-wrap"
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
    >
      {children}
      {show && text && (
        <span
          className={`tooltip-bubble tooltip-bubble--${side}`}
          role="tooltip"
        >
          {text}
        </span>
      )}
    </span>
  )
}
