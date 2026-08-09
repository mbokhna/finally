export type Direction = 'up' | 'down' | 'flat'

export interface PriceUpdate {
  symbol: string
  price: number
  previous_price: number | null
  change: number | null
  direction: Direction
  timestamp: string
}

export interface PricesSnapshot {
  prices: PriceUpdate[]
  version: number
}

export interface PositionValuation {
  symbol: string
  quantity: number
  avg_cost: number
  current_price: number | null
  market_value: number | null
  unrealised_pnl: number | null
  unrealised_pnl_pct: number | null
}

export interface PortfolioValuation {
  cash: number
  positions: PositionValuation[]
  total_value: number
  currency: string
}

export type Side = 'BUY' | 'SELL'

export interface Trade {
  id: number
  symbol: string
  side: Side
  quantity: number
  price: number
  executed_at: string
}

export interface TradeResponse {
  trade: Trade
  cash: number
}

export type AlertCondition = 'ABOVE' | 'BELOW'

export interface Alert {
  id: number
  symbol: string
  condition: AlertCondition
  threshold: number
  triggered: boolean
  created_at: string
}

export interface AlertsResponse {
  alerts: Alert[]
}

export interface BacktestTrade {
  t: string
  side: Side
  price: number
  quantity: number
}

export interface EquityPoint {
  t: string
  value: number
}

export interface BacktestMetrics {
  total_return_pct: number
  max_drawdown_pct: number
  trade_count: number
}

export interface BacktestResult {
  trades: BacktestTrade[]
  equity_curve: EquityPoint[]
  metrics: BacktestMetrics
}
