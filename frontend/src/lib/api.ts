import type {
  Alert,
  AlertCondition,
  AlertsResponse,
  AiStatus,
  BacktestResult,
  PortfolioValuation,
  Side,
  TradeResponse,
} from './types'

interface ErrorBody {
  detail?: string
}

async function parseJsonOrThrow<T>(response: Response): Promise<T> {
  const body: unknown = await response.json()
  if (!response.ok) {
    const detail = (body as ErrorBody).detail ?? response.statusText
    throw new Error(detail)
  }
  return body as T
}

export async function getPortfolio(): Promise<PortfolioValuation> {
  const response = await fetch('/api/portfolio')
  return parseJsonOrThrow<PortfolioValuation>(response)
}

export async function postTrade(
  symbol: string,
  side: Side,
  quantity: number,
): Promise<TradeResponse> {
  const response = await fetch('/api/trade', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol, side, quantity }),
  })
  return parseJsonOrThrow<TradeResponse>(response)
}

export async function getAlerts(): Promise<AlertsResponse> {
  const response = await fetch('/api/alerts')
  return parseJsonOrThrow<AlertsResponse>(response)
}

export async function createAlert(
  symbol: string,
  condition: AlertCondition,
  threshold: number,
): Promise<Alert> {
  const response = await fetch('/api/alerts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol, condition, threshold }),
  })
  return parseJsonOrThrow<Alert>(response)
}

export async function deleteAlert(id: number): Promise<void> {
  const response = await fetch(`/api/alerts/${id.toString()}`, { method: 'DELETE' })
  await parseJsonOrThrow<{ status: string }>(response)
}

export async function runBacktest(
  symbol: string,
  fast: number,
  slow: number,
  initialCash: number,
): Promise<BacktestResult> {
  const response = await fetch('/api/backtest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      symbol,
      interval: '1h',
      limit: 200,
      strategy: 'ma_crossover',
      params: { fast, slow },
      initial_cash: initialCash,
    }),
  })
  return parseJsonOrThrow<BacktestResult>(response)
}

export async function getAiStatus(): Promise<AiStatus> {
  const response = await fetch('/api/ai/status')
  return parseJsonOrThrow<AiStatus>(response)
}
