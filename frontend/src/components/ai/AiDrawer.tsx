import { useEffect, type ReactNode } from 'react'

interface Props {
  open: boolean
  onClose: () => void
  children: ReactNode
}

/**
 * Overlays with `transform` only — never a flex sibling of the terminal grid,
 * so opening it never reflows anything behind it.
 */
export function AiDrawer({ open, onClose, children }: Props) {
  useEffect(() => {
    if (!open) return
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open, onClose])

  return (
    <div className={`ai-drawer ${open ? 'open' : ''}`} aria-hidden={!open}>
      {children}
    </div>
  )
}
