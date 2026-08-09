import { useState, type FormEvent } from 'react'
import { postTrade } from '../lib/api'
import type { Side } from '../lib/types'

interface Props {
  onTraded: () => void
}

export function TradeForm({ onTraded }: Props) {
  const [symbol, setSymbol] = useState('CRYPTO:BTCUSDT')
  const [side, setSide] = useState<Side>('BUY')
  const [quantity, setQuantity] = useState('0.01')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await postTrade(symbol, side, Number(quantity))
      onTraded()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Trade failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="trade-form" onSubmit={(event) => void handleSubmit(event)}>
      <input
        value={symbol}
        onChange={(event) => setSymbol(event.target.value)}
        placeholder="CRYPTO:BTCUSDT"
        aria-label="Symbol"
      />
      <select
        value={side}
        onChange={(event) => setSide(event.target.value as Side)}
        aria-label="Side"
      >
        <option value="BUY">BUY</option>
        <option value="SELL">SELL</option>
      </select>
      <input
        type="number"
        step="any"
        min="0"
        value={quantity}
        onChange={(event) => setQuantity(event.target.value)}
        aria-label="Quantity"
      />
      <button type="submit" disabled={submitting}>
        {submitting ? 'Placing…' : 'Place trade'}
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  )
}
