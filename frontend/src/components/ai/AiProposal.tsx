import { useState } from 'react'
import { postTrade } from '../../lib/api'
import type { AiProposalData } from '../../lib/types'

interface Props {
  proposal: AiProposalData
  onConfirmed: () => void
  onDismiss: () => void
}

export function AiProposal({ proposal, onConfirmed, onDismiss }: Props) {
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleConfirm() {
    setError(null)
    setConfirming(true)
    try {
      // The only path from a proposal to a real trade: the ordinary /api/trade
      // endpoint, with the same validation the manual buy form uses.
      await postTrade(proposal.symbol, proposal.action, proposal.quantity)
      onConfirmed()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Trade failed')
    } finally {
      setConfirming(false)
    }
  }

  return (
    <div className="ai-proposal">
      <div className="ai-proposal-header">Proposed trade</div>
      <div className="ai-proposal-body">
        <span className={proposal.action === 'BUY' ? 'up' : 'down'}>{proposal.action}</span>{' '}
        {proposal.quantity} {proposal.symbol}
      </div>
      {proposal.reason && <p className="ai-proposal-reason">{proposal.reason}</p>}
      <div className="ai-proposal-actions">
        <button type="button" onClick={() => void handleConfirm()} disabled={confirming}>
          {confirming ? 'Confirming…' : 'Confirm'}
        </button>
        <button type="button" onClick={onDismiss} disabled={confirming}>
          Dismiss
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </div>
  )
}
