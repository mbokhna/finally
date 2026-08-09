import { useEffect, useState } from 'react'

/** Consumes a JSON SSE stream. EventSource reconnects natively on drop. */
export function useEventSource<T>(url: string): T | null {
  const [data, setData] = useState<T | null>(null)

  useEffect(() => {
    const source = new EventSource(url)
    source.onmessage = (event: MessageEvent<string>) => {
      setData(JSON.parse(event.data) as T)
    }
    return () => source.close()
  }, [url])

  return data
}
