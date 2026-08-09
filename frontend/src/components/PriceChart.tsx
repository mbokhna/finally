import type { Candle } from '../lib/types'

interface Props {
  candles: Candle[]
}

const WIDTH = 900
const HEIGHT = 360
const PADDING_Y = 16
const PADDING_X = 8

export function PriceChart({ candles }: Props) {
  if (candles.length < 2) {
    return <p className="empty">Not enough data to chart.</p>
  }

  const min = Math.min(...candles.map((c) => c.l))
  const max = Math.max(...candles.map((c) => c.h))
  const range = max - min || 1

  const slotWidth = (WIDTH - PADDING_X * 2) / candles.length
  const bodyWidth = Math.max(slotWidth * 0.6, 1)

  function y(value: number): number {
    return HEIGHT - PADDING_Y - ((value - min) / range) * (HEIGHT - PADDING_Y * 2)
  }

  return (
    <svg
      className="price-chart"
      viewBox={`0 0 ${WIDTH.toString()} ${HEIGHT.toString()}`}
      preserveAspectRatio="none"
      role="img"
      aria-label="Price chart"
    >
      {candles.map((candle, i) => {
        const x = PADDING_X + i * slotWidth + slotWidth / 2
        const isUp = candle.c >= candle.o
        const bodyTop = y(Math.max(candle.o, candle.c))
        const bodyBottom = y(Math.min(candle.o, candle.c))

        return (
          <g key={`${candle.t}-${i.toString()}`} className={isUp ? 'up' : 'down'}>
            <line x1={x} x2={x} y1={y(candle.h)} y2={y(candle.l)} className="wick" />
            <rect
              x={x - bodyWidth / 2}
              y={bodyTop}
              width={bodyWidth}
              height={Math.max(bodyBottom - bodyTop, 1)}
              className="body"
            />
          </g>
        )
      })}
    </svg>
  )
}
