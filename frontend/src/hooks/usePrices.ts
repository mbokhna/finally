import { useContext } from 'react'
import { PriceContext } from '../context/priceContextValue'
import type { PricesSnapshot } from '../lib/types'

export function usePrices(): PricesSnapshot | null {
  return useContext(PriceContext)
}
