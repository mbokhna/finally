import type { PortfolioValuation } from '../lib/types'

interface Props {
  portfolio: PortfolioValuation | null
}

export function Header({ portfolio }: Props) {
  return (
    <header className="app-header">
      <h1>PulseDesk</h1>
      {portfolio ? (
        <div className="totals">
          <span>
            Cash: {portfolio.cash.toFixed(2)} {portfolio.currency}
          </span>
          <span>
            Total: {portfolio.total_value.toFixed(2)} {portfolio.currency}
          </span>
        </div>
      ) : (
        <span className="loading">Loading…</span>
      )}
    </header>
  )
}
