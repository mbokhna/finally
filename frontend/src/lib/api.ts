import type { PortfolioValuation, Side, TradeResponse } from './types'

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
