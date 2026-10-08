import { useEffect, useState } from 'react'

export type Route = { path: string; segments: string[]; query: URLSearchParams }

function parseHash(): Route {
  const raw = window.location.hash.replace(/^#/, '')
  const [pathPart, queryPart = ''] = raw.split('?')
  const path = `/${pathPart.replace(/^\/+/, '').replace(/\/+$/, '')}`
  return {
    path,
    segments: path.split('/').filter(Boolean).map(decodeURIComponent),
    query: new URLSearchParams(queryPart),
  }
}

/** Current hash route (`#/projects/123?tab=documents`). */
export function useRoute(): Route {
  const [route, setRoute] = useState(parseHash)
  useEffect(() => {
    const onChange = () => setRoute(parseHash())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}

export function href(path: string, query?: Record<string, string | undefined>) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) if (value) params.set(key, value)
  const search = params.toString()
  return `#${path}${search ? `?${search}` : ''}`
}

export function navigate(path: string, query?: Record<string, string | undefined>, options: { replace?: boolean } = {}) {
  const target = href(path, query)
  if (options.replace) {
    window.history.replaceState(null, '', target)
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  } else if (window.location.hash !== target) {
    window.location.hash = target
  }
}

export const routes = {
  dashboard: () => '/',
  projects: () => '/projects',
  project: (projectId: string, tab?: string) => `/projects/${projectId}${tab ? `/${tab}` : ''}`,
  generate: () => '/generate',
  run: (projectId: string, runId: string) => `/generate/${projectId}/${runId}`,
  generations: () => '/generations',
  documents: () => '/documents',
  compareDocuments: () => '/documents/compare',
  document: (projectId: string, documentId: string) => `/documents/${projectId}/${documentId}`,
  diagrams: () => '/diagrams',
  diagram: (projectId: string, diagramId: string) => `/diagrams/${projectId}/${diagramId}`,
  classModeler: () => '/class-modeler',
  settings: (tab?: string) => `/settings${tab ? `/${tab}` : ''}`,
  members: () => '/members',
  admin: (tab?: string) => `/admin${tab ? `/${tab}` : ''}`,
  invite: (token: string) => `/invite/${token}`,
}
