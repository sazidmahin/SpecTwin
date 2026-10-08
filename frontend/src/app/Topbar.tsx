import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { ChevronRight, FileText, Folder, Loader2, LogOut, Menu, Moon, Network, Search, Settings, Sun, WandSparkles, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { workspaceApi } from '../api'
import type { AuthUser, SearchResults } from '../api'
import { useTheme } from '../shared/theme'
import {
  Avatar,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Tooltip,
  cn,
} from '../shared/ui'
import { navigate, routes } from './core/router'

type TopbarProps = {
  workspaceId: string
  workspaceName: string
  sectionLabel: string
  user: AuthUser
  onOpenNav: () => void
  onSignOut: () => void
}

const iconButton =
  'relative grid size-9 shrink-0 place-items-center rounded-lg text-fg-2 transition hover:bg-surface-3 hover:text-fg focus-visible:ring-4 focus-visible:ring-accent/15 [&_svg]:size-[18px]'

type FlatHit = { key: string; group: string; icon: LucideIcon; title: string; subtitle: string | null; go: () => void }

function flatten(results: SearchResults | null): FlatHit[] {
  if (!results) return []
  return [
    ...results.projects.map((hit) => ({
      key: `p-${hit.id}`,
      group: 'Projects',
      icon: Folder,
      title: hit.title,
      subtitle: hit.subtitle,
      go: () => navigate(routes.project(hit.id)),
    })),
    ...results.documents.map((hit) => ({
      key: `d-${hit.id}`,
      group: 'SRS documents',
      icon: FileText,
      title: hit.title,
      subtitle: hit.subtitle,
      go: () => navigate(routes.document(hit.project_id, hit.id)),
    })),
    ...results.runs.map((hit) => ({
      key: `r-${hit.id}`,
      group: 'Generations',
      icon: WandSparkles,
      title: hit.title,
      subtitle: hit.subtitle,
      go: () => navigate(routes.run(hit.project_id, hit.id)),
    })),
    ...results.diagrams.map((hit) => ({
      key: `g-${hit.id}`,
      group: 'Diagrams',
      icon: Network,
      title: hit.title,
      subtitle: hit.subtitle,
      go: () => navigate(routes.diagram(hit.project_id, hit.id)),
    })),
  ]
}

function GlobalSearch({ workspaceId, onClose, autoFocus }: { workspaceId: string; onClose?: () => void; autoFocus?: boolean }) {
  const [query, setQuery] = useState('')
  // Results are stored with the query they answer, so "loading" is simply "the answer is for an older query".
  const [answer, setAnswer] = useState<{ query: string; results: SearchResults } | null>(null)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const trimmedQuery = query.trim()
  const searching = trimmedQuery.length >= 2 && Boolean(workspaceId)
  const results = searching ? answer?.results ?? null : null
  const loading = searching && answer?.query !== trimmedQuery

  useEffect(() => {
    if (!searching) return
    let cancelled = false
    const timer = window.setTimeout(async () => {
      let next: SearchResults
      try {
        next = await workspaceApi.search(workspaceId, trimmedQuery)
      } catch {
        next = { projects: [], documents: [], runs: [], diagrams: [] }
      }
      if (!cancelled) {
        setAnswer({ query: trimmedQuery, results: next })
        setActive(0)
      }
    }, 220)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [searching, trimmedQuery, workspaceId])

  useEffect(() => {
    function onPointerDown(event: PointerEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false)
    }
    function onShortcut(event: globalThis.KeyboardEvent) {
      const target = event.target as HTMLElement | null
      const typing = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)
      if ((event.key === 'k' && (event.metaKey || event.ctrlKey)) || (event.key === '/' && !typing)) {
        event.preventDefault()
        inputRef.current?.focus()
        setOpen(true)
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onShortcut)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onShortcut)
    }
  }, [])

  const hits = flatten(results)

  function choose(hit: FlatHit) {
    hit.go()
    setQuery('')
    setOpen(false)
    inputRef.current?.blur()
    onClose?.()
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActive((index) => Math.min(hits.length - 1, index + 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((index) => Math.max(0, index - 1))
    } else if (event.key === 'Enter' && hits[active]) {
      event.preventDefault()
      choose(hits[active])
    } else if (event.key === 'Escape') {
      setOpen(false)
      onClose?.()
    }
  }

  const showPanel = open && query.trim().length >= 2

  return (
    <div ref={containerRef} className="relative w-full">
      <label className="relative flex items-center">
        <Search className="pointer-events-none absolute left-3 size-4 text-fg-3" />
        <input
          ref={inputRef}
          type="search"
          value={query}
          autoFocus={autoFocus}
          onChange={(event) => {
            setQuery(event.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder="Search projects, documents, diagrams…"
          aria-label="Search workspace"
          role="combobox"
          aria-expanded={showPanel}
          aria-controls="global-search-results"
          className="h-9.5 w-full rounded-lg border border-border bg-surface pl-9 pr-9 text-[13px] text-fg shadow-[var(--elev-1)] outline-none transition placeholder:text-fg-3 hover:border-border-strong focus:border-accent focus:ring-4 focus:ring-accent/15 [&::-webkit-search-cancel-button]:hidden"
        />
        {loading ? <Loader2 className="absolute right-3 size-4 animate-spin text-fg-3" /> : null}
      </label>
      {showPanel ? (
        <div
          id="global-search-results"
          role="listbox"
          className="absolute inset-x-0 top-full z-40 mt-2 max-h-[min(70vh,28rem)] overflow-y-auto rounded-xl border border-border bg-surface p-1.5 shadow-[var(--elev-3)] animate-fade-in"
        >
          {!loading && hits.length === 0 ? (
            <p className="px-3 py-6 text-center text-[13px] text-fg-3">No matches for “{query.trim()}”.</p>
          ) : null}
          {hits.map((hit, index) => {
            const Icon = hit.icon
            const showGroup = index === 0 || hits[index - 1].group !== hit.group
            return (
              <div key={hit.key}>
                {showGroup ? (
                  <div className="px-2.5 pb-1 pt-2.5 text-[10.5px] font-semibold uppercase tracking-[0.1em] text-fg-3">{hit.group}</div>
                ) : null}
                <button
                  type="button"
                  role="option"
                  aria-selected={index === active}
                  onMouseEnter={() => setActive(index)}
                  onClick={() => choose(hit)}
                  className={cn(
                    'flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition',
                    index === active ? 'bg-accent/[0.08]' : 'hover:bg-surface-2',
                  )}
                >
                  <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-surface-3 text-fg-2">
                    <Icon className="size-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-semibold text-fg">{hit.title}</span>
                    {hit.subtitle ? <span className="block truncate text-xs text-fg-3">{hit.subtitle}</span> : null}
                  </span>
                </button>
              </div>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}

export function Topbar({ workspaceId, workspaceName, sectionLabel, user, onOpenNav, onSignOut }: TopbarProps) {
  const { theme, toggleTheme } = useTheme()
  const [mobileSearch, setMobileSearch] = useState(false)

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-bg/75 backdrop-blur-xl backdrop-saturate-150">
      <div className="flex h-16 items-center gap-2 px-3 sm:gap-3 sm:px-6 lg:px-8">
        <button type="button" className={`${iconButton} lg:hidden`} aria-label="Open navigation" onClick={onOpenNav}>
          <Menu />
        </button>

        <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-[13px]">
          <span className="hidden truncate text-fg-3 sm:inline">{workspaceName}</span>
          <ChevronRight className="hidden size-3.5 shrink-0 text-fg-3 sm:block" />
          <span className="truncate font-semibold text-fg">{sectionLabel}</span>
        </nav>

        <div className="ml-auto hidden w-full max-w-sm md:block">
          <GlobalSearch workspaceId={workspaceId} />
        </div>

        <div className="ml-auto flex items-center gap-1 md:ml-2">
          <button type="button" className={`${iconButton} md:hidden`} aria-label="Search" onClick={() => setMobileSearch(true)}>
            <Search />
          </button>
          <Tooltip content={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
            <button type="button" className={iconButton} aria-label="Toggle colour theme" onClick={toggleTheme}>
              {theme === 'dark' ? <Sun /> : <Moon />}
            </button>
          </Tooltip>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="ml-1 rounded-full transition hover:ring-4 hover:ring-accent/15" aria-label="Account menu">
                <Avatar name={user.full_name} className="ring-0" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-[14rem]">
              <div className="flex items-center gap-2.5 px-2.5 py-2">
                <Avatar name={user.full_name} className="ring-0" />
                <div className="min-w-0">
                  <div className="truncate text-[13px] font-semibold text-fg">{user.full_name}</div>
                  <div className="truncate text-xs text-fg-3">{user.email}</div>
                </div>
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => navigate(routes.settings())}>
                <Settings className="size-4" />
                Settings
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={toggleTheme}>
                {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
                {theme === 'dark' ? 'Light mode' : 'Dark mode'}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={onSignOut} className="text-danger data-[highlighted]:text-danger">
                <LogOut className="size-4" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {mobileSearch ? (
        <div className="flex items-center gap-2 border-t border-border px-3 py-2.5 md:hidden">
          <GlobalSearch workspaceId={workspaceId} autoFocus onClose={() => setMobileSearch(false)} />
          <button type="button" className={iconButton} aria-label="Close search" onClick={() => setMobileSearch(false)}>
            <X />
          </button>
        </div>
      ) : null}
    </header>
  )
}
