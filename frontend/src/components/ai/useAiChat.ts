import { useCallback, useRef, useState } from 'react'
import type { AiMessageData, AiProposalData } from '../../lib/types'

interface ParsedReply {
  reply: string
  proposal: AiProposalData | null
}

function parseSseEvents(raw: string): ParsedReply {
  let reply = ''
  let proposal: AiProposalData | null = null

  for (const block of raw.split('\n\n')) {
    if (!block.trim()) continue
    let event = 'message'
    let data = ''
    for (const line of block.split('\n')) {
      if (line.startsWith('event: ')) event = line.slice('event: '.length)
      else if (line.startsWith('data: ')) data = line.slice('data: '.length)
    }
    if (!data) continue

    if (event === 'token') {
      const parsed = JSON.parse(data) as { text: string }
      reply += parsed.text
    } else if (event === 'proposal') {
      proposal = JSON.parse(data) as AiProposalData
    }
  }

  return { reply, proposal }
}

export function useAiChat() {
  const [messages, setMessages] = useState<AiMessageData[]>([])
  const [proposal, setProposal] = useState<AiProposalData | null>(null)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const nextId = useRef(0)

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed) return

      setError(null)
      setSending(true)
      setProposal(null)
      const history = messages.map((m) => ({ role: m.role, content: m.text }))
      setMessages((prev) => [...prev, { id: nextId.current++, role: 'user', text: trimmed }])

      try {
        const response = await fetch('/api/ai/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: trimmed, history }),
        })

        if (!response.ok) {
          const body: unknown = await response.json().catch(() => null)
          const detail =
            body && typeof body === 'object' && 'detail' in body
              ? String((body as { detail?: unknown }).detail)
              : `Request failed (${response.status.toString()})`
          throw new Error(detail)
        }

        const raw = await response.text()
        const { reply, proposal: parsedProposal } = parseSseEvents(raw)
        if (reply) {
          setMessages((prev) => [...prev, { id: nextId.current++, role: 'assistant', text: reply }])
        }
        setProposal(parsedProposal)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to reach the assistant')
      } finally {
        setSending(false)
      }
    },
    [messages],
  )

  const dismissProposal = useCallback(() => setProposal(null), [])

  return { messages, proposal, sending, error, sendMessage, dismissProposal }
}
