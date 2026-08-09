import { createContext } from 'react'
import type { PricesSnapshot } from '../lib/types'

export const PriceContext = createContext<PricesSnapshot | null>(null)
