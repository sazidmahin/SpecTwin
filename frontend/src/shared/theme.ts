import { useCallback, useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

export const THEME_STORAGE_KEY = 'spectwin.theme'

function readTheme(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'
}

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme)
  } catch {
    // Storage can be unavailable (private mode); the attribute still applies for this visit.
  }
  window.dispatchEvent(new CustomEvent<Theme>('spectwin:theme', { detail: theme }))
}

/** Current colour theme plus a toggle. The initial value is set before paint by the inline script in index.html. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(readTheme)

  useEffect(() => {
    const sync = () => setTheme(readTheme())
    window.addEventListener('spectwin:theme', sync)
    return () => window.removeEventListener('spectwin:theme', sync)
  }, [])

  const toggleTheme = useCallback(() => applyTheme(readTheme() === 'dark' ? 'light' : 'dark'), [])

  return { theme, toggleTheme }
}
