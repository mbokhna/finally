interface Props {
  open: boolean
  hasUnread: boolean
  onClick: () => void
}

export function AiButton({ open, hasUnread, onClick }: Props) {
  return (
    <button
      type="button"
      className="ai-button"
      onClick={onClick}
      aria-label={open ? 'Close AI assistant' : 'Open AI assistant'}
    >
      AI
      {hasUnread && !open && <span className="ai-unread-dot" aria-hidden="true" />}
    </button>
  )
}
