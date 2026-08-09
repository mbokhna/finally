import { useEffect, useState, type FormEvent } from 'react'
import { useEventSource } from '../hooks/useEventSource'
import { createAlert, deleteAlert, getAlerts } from '../lib/api'
import type { Alert, AlertCondition } from '../lib/types'

function notify(alert: Alert): void {
  if (!('Notification' in window) || Notification.permission !== 'granted') return
  const symbol = alert.condition === 'ABOVE' ? '≥' : '≤'
  new Notification('PulseDesk alert', {
    body: `${alert.symbol} ${symbol} ${alert.threshold}`,
  })
}

export function AlertsPanel() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [symbol, setSymbol] = useState('CRYPTO:BTCUSDT')
  const [condition, setCondition] = useState<AlertCondition>('ABOVE')
  const [threshold, setThreshold] = useState('80000')
  const [error, setError] = useState<string | null>(null)

  const fired = useEventSource<Alert>('/api/stream/alerts')

  function refresh(): void {
    getAlerts()
      .then((res) => setAlerts(res.alerts))
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load alerts')
      })
  }

  useEffect(refresh, [])

  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      void Notification.requestPermission()
    }
  }, [])

  useEffect(() => {
    if (!fired) return
    setAlerts((prev) => prev.map((alert) => (alert.id === fired.id ? fired : alert)))
    notify(fired)
  }, [fired])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    try {
      await createAlert(symbol, condition, Number(threshold))
      refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create alert')
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteAlert(id)
      refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete alert')
    }
  }

  return (
    <section className="alerts">
      <h2>Alerts</h2>
      {alerts.length === 0 ? (
        <p className="empty">No alerts set.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Condition</th>
              <th>Threshold</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((alert) => (
              <tr key={alert.id} className={alert.triggered ? 'triggered' : ''}>
                <td>{alert.symbol}</td>
                <td>{alert.condition}</td>
                <td>{alert.threshold}</td>
                <td>
                  <button
                    type="button"
                    aria-label={`Delete alert ${alert.id.toString()}`}
                    onClick={() => void handleDelete(alert.id)}
                  >
                    &times;
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <form className="alert-form" onSubmit={(event) => void handleSubmit(event)}>
        <input
          value={symbol}
          onChange={(event) => setSymbol(event.target.value)}
          placeholder="CRYPTO:BTCUSDT"
          aria-label="Alert symbol"
        />
        <select
          value={condition}
          onChange={(event) => setCondition(event.target.value as AlertCondition)}
          aria-label="Alert condition"
        >
          <option value="ABOVE">ABOVE</option>
          <option value="BELOW">BELOW</option>
        </select>
        <input
          type="number"
          step="any"
          value={threshold}
          onChange={(event) => setThreshold(event.target.value)}
          aria-label="Alert threshold"
        />
        <button type="submit">Add alert</button>
      </form>
      {error && <p className="error">{error}</p>}
    </section>
  )
}
