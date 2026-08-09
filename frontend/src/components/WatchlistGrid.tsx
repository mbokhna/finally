import { usePrices } from '../hooks/usePrices'
import type { Direction } from '../lib/types'

function directionClass(direction: Direction): string {
  if (direction === 'up') return 'up'
  if (direction === 'down') return 'down'
  return ''
}

function flashClass(direction: Direction): string {
  if (direction === 'up') return 'flash-up'
  if (direction === 'down') return 'flash-down'
  return ''
}

interface Props {
  selectedSymbol: string
  onSelect: (symbol: string) => void
}

export function WatchlistGrid({ selectedSymbol, onSelect }: Props) {
  const snapshot = usePrices()

  if (!snapshot) {
    return <p className="loading">Connecting to price stream…</p>
  }

  return (
    <table className="watchlist">
      <thead>
        <tr>
          <th>Symbol</th>
          <th>Price</th>
          <th>Change</th>
        </tr>
      </thead>
      <tbody>
        {snapshot.prices.map((update) => (
          <tr
            key={update.symbol}
            className={update.symbol === selectedSymbol ? 'selected' : ''}
            onClick={() => onSelect(update.symbol)}
          >
            <td>{update.symbol}</td>
            <td>
              {/* keyed by version so the flash animation retriggers every tick */}
              <span
                key={`${update.symbol}-${snapshot.version}`}
                className={`price-flash ${flashClass(update.direction)}`}
              >
                {update.price.toFixed(4)}
              </span>
            </td>
            <td className={directionClass(update.direction)}>
              {update.change !== null ? update.change.toFixed(4) : '—'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
