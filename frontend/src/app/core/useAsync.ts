import { useCallback, useEffect, useRef, useState } from 'react'
import { errorMessage } from '../../api'

export type AsyncState<T> = {
  data: T | undefined
  error: string | null
  loading: boolean
  reload: () => Promise<void>
  setData: (updater: T | ((current: T | undefined) => T)) => void
}

/**
 * Load data for a page. Re-runs when `deps` change; a stale response from an older run is dropped.
 * Pass `enabled: false` to skip loading (e.g. no workspace selected yet).
 */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[], enabled = true): AsyncState<T> {
  const [data, setDataState] = useState<T | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(true)
  const generation = useRef(0)
  const loaderRef = useRef(loader)

  useEffect(() => {
    loaderRef.current = loader
  })

  const run = useCallback(async (reset = false) => {
    const current = ++generation.current
    if (reset) setDataState(undefined)
    setPending(true)
    setError(null)
    try {
      const result = await loaderRef.current()
      if (current === generation.current) setDataState(result)
    } catch (caught) {
      if (current === generation.current) setError(errorMessage(caught, 'Unable to load data'))
    } finally {
      if (current === generation.current) setPending(false)
    }
  }, [])

  useEffect(() => {
    // Fetching on input change is exactly what this effect is for; the state it sets is the request status.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (enabled) void run(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, ...deps])

  const reload = useCallback(() => run(), [run])
  const setData = useCallback((updater: T | ((current: T | undefined) => T)) => {
    setDataState((current) => (typeof updater === 'function' ? (updater as (value: T | undefined) => T)(current) : updater))
  }, [])

  return { data, error, loading: enabled && pending, reload, setData }
}
