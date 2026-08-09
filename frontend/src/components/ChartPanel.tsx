import { useEffect, useState } from 'react'
import { usePrices } from '../hooks/usePrices'
import { getCandles } from '../lib/api'
import type { Candle, Direction } from '../lib/types'
import { PriceChart } from './PriceChart'

interface Props {
  symbol: string
  onSymbolChange: (symbol: string) => void
}

function directionClass(direction: Direction | undefined): string {
  if (direction === 'up') return 'up'
  if (direction === 'down') return 'down'
  return ''
}

export function ChartPanel({ symbol, onSymbolChange }: Props) {
  const snapshot = usePrices()
  const [candles, setCandles] = useState<Candle[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    getCandles(symbol, '1h', 200)
      .then((res) => {
        if (!cancelled) setCandles(res.candles)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load chart')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [symbol])

  const current = snapshot?.prices.find((p) => p.symbol === symbol)
  const options = snapshot?.prices.map((p) => p.symbol) ?? [symbol]

  return (
    <section className="chart-panel">
      <div className="chart-panel-header">
        <select
          value={symbol}
          onChange={(event) => onSymbolChange(event.target.value)}
          aria-label="Chart instrument"
        >
          {options.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        {current && (
          <span className={`chart-panel-price ${directionClass(current.direction)}`}>
            {current.price.toFixed(4)}
          </span>
        )}
      </div>

      {loading && <p className="loading">Loading chart…</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && <PriceChart candles={candles} />}
    </section>
  )
}
