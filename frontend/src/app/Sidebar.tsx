import { ChevronsUpDown, LogOut, Plus, Settings, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { AuthUser, WorkspaceMembership } from '../api'
import { href, routes } from './core/router'
import {
  Avatar,
  BrandMark,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  cn,
  initials,
} from '../shared/ui'

export type NavItem = { id: string; label: string; icon: LucideIcon; path: string }
export type NavGroup = { title?: string; items: NavItem[] }

type SidebarProps = {
  user: AuthUser
  roleLabel: string
  groups: NavGroup[]
  activeSection: string
  workspaces: WorkspaceMembership[]
  activeWorkspace: WorkspaceMembership | undefined
  mobileOpen: boolean
  onMobileClose: () => void
  onSelectWorkspace: (workspaceId: string) => void
  onSignOut: () => void
}

export function Sidebar({
  user,
  roleLabel,
  groups,
  activeSection,
  workspaces,
  activeWorkspace,
  mobileOpen,
  onMobileClose,
  onSelectWorkspace,
  onSignOut,
}: SidebarProps) {
  const workspaceName = activeWorkspace?.workspace.name ?? 'No workspace'

  return (
    <>
      <div
        className={cn(
          'fixed inset-0 z-40 bg-slate-950/50 backdrop-blur-[2px] transition-opacity lg:hidden',
          mobileOpen ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
        aria-hidden="true"
        onClick={onMobileClose}
      />
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex h-svh w-[17rem] shrink-0 flex-col overflow-hidden border-r border-sidebar-border bg-sidebar transition-transform duration-300 ease-out',
          'bg-[radial-gradient(420px_260px_at_0%_0%,color-mix(in_oklab,var(--color-accent)_16%,transparent),transparent_70%)]',
          'lg:sticky lg:top-0 lg:z-30 lg:w-64 lg:translate-x-0',
          mobileOpen ? 'translate-x-0 shadow-[var(--elev-3)]' : '-translate-x-full',
        )}
        aria-label="Primary navigation"
      >
        <div className="flex items-center gap-2.5 px-4 pb-3 pt-5">
          <BrandMark className="size-9" />
          <div className="min-w-0 flex-1 font-display text-[18px] font-extrabold tracking-tight text-sidebar-fg-active">SpecTwin</div>
          <button
            type="button"
            className="grid size-8 place-items-center rounded-md text-sidebar-fg transition hover:bg-white/[0.06] hover:text-sidebar-fg-active lg:hidden"
            aria-label="Close navigation"
            onClick={onMobileClose}
          >
            <X className="size-4" />
          </button>
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="mx-3 mb-2 mt-2 flex items-center gap-2.5 rounded-lg border border-sidebar-border bg-sidebar-2/80 px-2.5 py-2 text-left transition hover:border-white/10 hover:bg-white/[0.06]">
              <span className="grid size-7 shrink-0 place-items-center rounded-md bg-gradient-to-br from-sky/90 to-accent text-[10.5px] font-extrabold text-white">
                {initials(workspaceName, 'W')}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-semibold text-sidebar-fg-active">{workspaceName}</span>
                <span className="block truncate text-[10.5px] capitalize text-sidebar-fg">
                  {activeWorkspace ? `${activeWorkspace.workspace.type} workspace` : 'Create one in Settings'}
                </span>
              </span>
              <ChevronsUpDown className="size-3.5 shrink-0 text-sidebar-fg" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="min-w-[15rem]">
            {workspaces.length === 0 ? (
              <DropdownMenuItem disabled>No workspaces</DropdownMenuItem>
            ) : (
              workspaces.map((membership) => {
                const selected = membership.workspace.id === activeWorkspace?.workspace.id
                return (
                  <DropdownMenuItem
                    key={membership.workspace.id}
                    onSelect={() => onSelectWorkspace(membership.workspace.id)}
                    className={cn(selected && 'bg-accent/[0.07] text-fg')}
                  >
                    <span className="grid size-6 shrink-0 place-items-center rounded-md bg-accent/15 text-[10px] font-extrabold text-accent">
                      {initials(membership.workspace.name, 'W')}
                    </span>
                    <span className="flex-1 truncate">{membership.workspace.name}</span>
                    <span className="text-[10px] uppercase tracking-wide text-fg-3">{membership.role.replaceAll('_', ' ')}</span>
                  </DropdownMenuItem>
                )
              })
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => { window.location.hash = href(routes.settings('workspaces')) }}>
              <Plus className="size-4" />
              New organization workspace
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <nav className="flex flex-1 flex-col gap-px overflow-y-auto px-3 py-2 [scrollbar-color:rgba(255,255,255,0.12)_transparent]">
          {groups.map((group, groupIndex) => (
            <div key={group.title ?? groupIndex} className="flex flex-col gap-0.5">
              {group.title ? (
                <div className="px-2.5 pb-1.5 pt-4 text-[10.5px] font-semibold uppercase tracking-[0.12em] text-sidebar-fg/70">
                  {group.title}
                </div>
              ) : groupIndex > 0 ? (
                <div className="mx-2.5 my-2.5 h-px bg-sidebar-border" />
              ) : null}
              {group.items.map((item) => {
                const Icon = item.icon
                const active = item.id === activeSection
                return (
                  <a
                    key={item.id}
                    href={href(item.path)}
                    aria-current={active ? 'page' : undefined}
                    onClick={onMobileClose}
                    className={cn(
                      'group relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition',
                      active
                        ? 'bg-white/[0.08] text-sidebar-fg-active shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]'
                        : 'text-sidebar-fg hover:bg-white/[0.04] hover:text-sidebar-fg-active',
                    )}
                  >
                    {active ? (
                      <span className="absolute inset-y-2 -left-3 w-[3px] rounded-r-full bg-sidebar-accent" aria-hidden="true" />
                    ) : null}
                    <Icon className={cn('size-4 shrink-0 transition', active ? 'text-sidebar-accent' : 'text-sidebar-fg group-hover:text-sidebar-fg-active')} />
                    <span className="truncate">{item.label}</span>
                  </a>
                )
              })}
            </div>
          ))}
        </nav>

        <div className="border-t border-sidebar-border p-3">
          <a
            href={href(routes.generate())}
            onClick={onMobileClose}
            className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-accent to-accent2-dim px-3 py-2.5 text-[13px] font-semibold text-white shadow-[0_8px_20px_-8px_color-mix(in_oklab,var(--color-accent)_90%,transparent)] transition hover:brightness-110"
          >
            <Plus className="size-4" />
            New SRS
          </a>
          <div className="mt-3 flex items-center gap-2.5 rounded-lg px-1.5 py-1">
            <Avatar name={user.full_name} />
            <div className="min-w-0 flex-1">
              <div className="truncate text-[12.5px] font-semibold text-sidebar-fg-active">{user.full_name}</div>
              <div className="truncate text-[11px] capitalize text-sidebar-fg">{roleLabel.replaceAll('_', ' ')}</div>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  className="grid size-8 shrink-0 place-items-center rounded-md text-sidebar-fg transition hover:bg-white/[0.06] hover:text-sidebar-fg-active"
                  aria-label="Account menu"
                >
                  <Settings className="size-4" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" side="top">
                <DropdownMenuItem onSelect={() => { window.location.hash = href(routes.settings()) }}>
                  <Settings className="size-4" />
                  Settings
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
      </aside>
    </>
  )
}
