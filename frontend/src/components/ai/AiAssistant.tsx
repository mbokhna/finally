import { useEffect, useRef, useState, type FormEvent } from 'react'
import { getAiStatus } from '../../lib/api'
import { AiButton } from './AiButton'
import { AiDrawer } from './AiDrawer'
import { AiMessage } from './AiMessage'
import { AiProposal } from './AiProposal'
import { useAiChat } from './useAiChat'

const STORAGE_KEY = 'pulsedesk.ai.open'

interface Props {
  onTraded: () => void
}

export function AiAssistant({ onTraded }: Props) {
  const [open, setOpen] = useState(() => localStorage.getItem(STORAGE_KEY) === 'true')
  const [configured, setConfigured] = useState<boolean | null>(null)
  const [hasUnread, setHasUnread] = useState(false)
  const [input, setInput] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)
  const { messages, proposal, sending, error, sendMessage, dismissProposal } = useAiChat()

  useEffect(() => {
    getAiStatus()
      .then((status) => setConfigured(status.configured))
      .catch(() => setConfigured(false))
  }, [])

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, open ? 'true' : 'false')
    if (open) setHasUnread(false)
  }, [open])

  useEffect(() => {
    if (messages.length > 0 && !open) setHasUnread(true)
  }, [messages.length, open])

  useEffect(() => {
    if (!open) return
    function handlePointerDown(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handlePointerDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
    }
  }, [open])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = input
    setInput('')
    await sendMessage(text)
  }

  function handleConfirmed() {
    dismissProposal()
    onTraded()
  }

  return (
    <div ref={containerRef} className={`ai-widget ${open ? 'drawer-open' : ''}`}>
      <AiButton open={open} hasUnread={hasUnread} onClick={() => setOpen((o) => !o)} />
      <AiDrawer open={open} onClose={() => setOpen(false)}>
        <div className="ai-drawer-header">
          <h2>Assistant</h2>
          <button type="button" className="ai-close" onClick={() => setOpen(false)} aria-label="Close">
            &times;
          </button>
        </div>

        <div className="ai-drawer-body">
          {configured === false && (
            <p className="ai-unconfigured">
              AI assistant not configured — set OPENROUTER_API_KEY to enable.
            </p>
          )}

          {configured && (
            <>
              <div className="ai-messages">
                {messages.length === 0 && (
                  <p className="empty">Ask about your positions, concentration, or recent trades.</p>
                )}
                {messages.map((message) => (
                  <AiMessage key={message.id} message={message} />
                ))}
                {sending && <p className="ai-thinking">Thinking…</p>}
              </div>

              {proposal && (
                <AiProposal
                  proposal={proposal}
                  onConfirmed={handleConfirmed}
                  onDismiss={dismissProposal}
                />
              )}

              {error && <p className="error">{error}</p>}

              <form className="ai-input-form" onSubmit={(event) => void handleSubmit(event)}>
                <input
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder="Ask about your portfolio…"
                  aria-label="Message"
                  disabled={sending}
                />
                <button type="submit" disabled={sending || !input.trim()}>
                  Send
                </button>
              </form>
            </>
          )}
        </div>
      </AiDrawer>
    </div>
  )
}
