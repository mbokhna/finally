import { useState, type FormEvent } from 'react'
import { EquityChart } from './EquityChart'
import { runBacktest } from '../lib/api'
import type { BacktestResult } from '../lib/types'

export function BacktestPanel() {
  const [symbol, setSymbol] = useState('CRYPTO:BTCUSDT')
  const [fast, setFast] = useState('20')
  const [slow, setSlow] = useState('50')
  const [initialCash, setInitialCash] = useState('10000')
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setRunning(true)
    try {
      const res = await runBacktest(symbol, Number(fast), Number(slow), Number(initialCash))
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Backtest failed')
    } finally {
      setRunning(false)
    }
  }

  return (
    <section className="backtest">
      <h2>Backtest — MA crossover</h2>
      <form className="backtest-form" onSubmit={(event) => void handleSubmit(event)}>
        <input
          value={symbol}
          onChange={(event) => setSymbol(event.target.value)}
          placeholder="CRYPTO:BTCUSDT"
          aria-label="Backtest symbol"
        />
        <input
          type="number"
          min="1"
          value={fast}
          onChange={(event) => setFast(event.target.value)}
          aria-label="Fast window"
          title="Fast MA window"
        />
        <input
          type="number"
          min="2"
          value={slow}
          onChange={(event) => setSlow(event.target.value)}
          aria-label="Slow window"
          title="Slow MA window"
        />
        <input
          type="number"
          min="1"
          value={initialCash}
          onChange={(event) => setInitialCash(event.target.value)}
          aria-label="Initial cash"
          title="Initial cash"
        />
        <button type="submit" disabled={running}>
          {running ? 'Running…' : 'Run backtest'}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
      {result && (
        <div className="backtest-result">
          <EquityChart points={result.equity_curve} />
          <div className="backtest-metrics">
            <span>Return: {result.metrics.total_return_pct.toFixed(2)}%</span>
            <span>Max DD: {result.metrics.max_drawdown_pct.toFixed(2)}%</span>
            <span>Trades: {result.metrics.trade_count}</span>
          </div>
        </div>
      )}
    </section>
  )
}
