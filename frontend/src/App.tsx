import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { AlertsPanel } from './components/AlertsPanel'
import { AiAssistant } from './components/ai/AiAssistant'
import { ChartPanel } from './components/ChartPanel'
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
  const [selectedSymbol, setSelectedSymbol] = useState('CRYPTO:BTCUSDT')

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
          <div className="row row-chart">
            <WatchlistGrid selectedSymbol={selectedSymbol} onSelect={setSelectedSymbol} />
            <ChartPanel symbol={selectedSymbol} onSymbolChange={setSelectedSymbol} />
          </div>
          <div className="row row-secondary">
            <PositionsTable portfolio={portfolio} />
            <AlertsPanel />
          </div>
        </main>
        <TradeForm onTraded={refreshPortfolio} />
        {error && <p className="error">{error}</p>}
      </div>
      <AiAssistant onTraded={refreshPortfolio} />
    </PriceProvider>
  )
}

export default App
