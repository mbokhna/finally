import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { AlertsPanel } from './components/AlertsPanel'
import { AiAssistant } from './components/ai/AiAssistant'
import { BacktestPanel } from './components/BacktestPanel'
import { Header } from './components/Header'
import { PositionsTable } from './components/PositionsTable'
import { TradeForm } from './components/TradeForm'
import { WatchlistGrid } from './components/WatchlistGrid'
import { PriceProvider } from './context/PriceContext'
import { getPortfolio } from './lib/api'
import type { PortfolioValuation } from './lib/types'

function App() {
  const [portfolio, setPortfolio] = useState<PortfolioValuation | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refreshPortfolio = useCallback(() => {
    getPortfolio()
      .then(setPortfolio)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load portfolio')
      })
  }, [])

  useEffect(() => {
    refreshPortfolio()
  }, [refreshPortfolio])

  return (
    <PriceProvider>
      <div className="terminal">
        <Header portfolio={portfolio} />
        <main className="layout">
          <WatchlistGrid />
          <PositionsTable portfolio={portfolio} />
          <AlertsPanel />
          <BacktestPanel />
        </main>
        <TradeForm onTraded={refreshPortfolio} />
        {error && <p className="error">{error}</p>}
      </div>
      <AiAssistant onTraded={refreshPortfolio} />
    </PriceProvider>
  )
}

export default App
