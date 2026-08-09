import type { ReactNode } from 'react'
import { useEventSource } from '../hooks/useEventSource'
import type { PricesSnapshot } from '../lib/types'
import { PriceContext } from './priceContextValue'

export function PriceProvider({ children }: { children: ReactNode }) {
  const snapshot = useEventSource<PricesSnapshot>('/api/stream/prices')
  return <PriceContext.Provider value={snapshot}>{children}</PriceContext.Provider>
}
