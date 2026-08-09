import type { EquityPoint } from '../lib/types'

interface Props {
  points: EquityPoint[]
}

const WIDTH = 600
const HEIGHT = 160
const PADDING = 8

export function EquityChart({ points }: Props) {
  if (points.length < 2) {
    return <p className="empty">Not enough data to chart.</p>
  }

  const values = points.map((point) => point.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1

  const coords = points
    .map((point, i) => {
      const x = PADDING + (i / (points.length - 1)) * (WIDTH - PADDING * 2)
      const y = HEIGHT - PADDING - ((point.value - min) / range) * (HEIGHT - PADDING * 2)
      return `${x.toFixed(2)},${y.toFixed(2)}`
    })
    .join(' ')

  return (
    <svg
      className="equity-chart"
      viewBox={`0 0 ${WIDTH.toString()} ${HEIGHT.toString()}`}
      preserveAspectRatio="none"
      role="img"
      aria-label="Equity curve"
    >
      <polyline points={coords} fill="none" />
    </svg>
  )
}
