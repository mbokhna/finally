import type { PortfolioValuation } from '../lib/types'

interface Props {
  portfolio: PortfolioValuation | null
}

function pnlClass(pnl: number | null): string {
  if (pnl === null) return ''
  return pnl >= 0 ? 'up' : 'down'
}

export function PositionsTable({ portfolio }: Props) {
  if (!portfolio) {
    return <p className="loading">Loading positions…</p>
  }

  if (portfolio.positions.length === 0) {
    return <p className="empty">No open positions.</p>
  }

  return (
    <table className="positions">
      <thead>
        <tr>
          <th>Symbol</th>
          <th>Qty</th>
          <th>Avg cost</th>
          <th>Price</th>
          <th>Value</th>
          <th>P&amp;L</th>
        </tr>
      </thead>
      <tbody>
        {portfolio.positions.map((position) => (
          <tr key={position.symbol}>
            <td>{position.symbol}</td>
            <td>{position.quantity}</td>
            <td>{position.avg_cost.toFixed(2)}</td>
            <td>{position.current_price !== null ? position.current_price.toFixed(2) : '—'}</td>
            <td>{position.market_value !== null ? position.market_value.toFixed(2) : '—'}</td>
            <td className={pnlClass(position.unrealised_pnl)}>
              {position.unrealised_pnl !== null
                ? `${position.unrealised_pnl >= 0 ? '+' : ''}${position.unrealised_pnl.toFixed(2)}`
                : '—'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
