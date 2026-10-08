import { useMemo, useState } from 'react'
import { Archive, Folder, MoreHorizontal, Pencil, Plus } from 'lucide-react'
import { errorMessage, projectApi } from '../api'
import type { Project } from '../api'
import { FilterBar } from '../app/components/FilterBar'
import { ErrorState, LoadingState } from '../app/components/PageStates'
import { ProjectDialog } from '../app/components/ProjectDialog'
import { href, navigate, routes, useRoute } from '../app/core/router'
import { useSession } from '../app/core/session'
import { useAsync } from '../app/core/useAsync'
import { relativeTime } from '../shared/format'
import {
  Button,
  Chip,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  EmptyState,
  PageHeader,
  Select,
  useFeedback,
} from '../shared/ui'

export function ProjectsPage() {
  const { workspaceId, workspace, canEdit } = useSession()
  const { query: routeQuery } = useRoute()
  const { toast, confirm } = useFeedback()
  const projects = useAsync(() => projectApi.list(workspaceId), [workspaceId], Boolean(workspaceId))
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('active')
  const [dialog, setDialog] = useState<{ open: boolean; project?: Project }>({ open: false })

  // Links like "#/projects?new=1" open the create dialog directly.
  const createRequested = routeQuery.get('new') === '1' && canEdit
  const dialogOpen = dialog.open || createRequested

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (projects.data ?? [])
      .filter((project) => !status || project.status === status)
      .filter((project) => !needle || project.name.toLowerCase().includes(needle) || (project.description ?? '').toLowerCase().includes(needle))
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
  }, [projects.data, query, status])

  async function archive(project: Project) {
    const ok = await confirm({
      title: `Archive “${project.name}”?`,
      description: 'Archived projects are hidden from lists and search. Their documents and diagrams are kept.',
      confirmLabel: 'Archive',
    })
    if (!ok) return
    try {
      const archived = await projectApi.archive(workspaceId, project.id)
      projects.setData((current) => (current ?? []).map((item) => (item.id === archived.id ? archived : item)))
      toast('Project archived')
    } catch (caught) {
      toast('Archive failed', { description: errorMessage(caught), tone: 'error' })
    }
  }

  function onSaved(saved: Project) {
    projects.setData((current) => {
      const list = current ?? []
      return list.some((item) => item.id === saved.id) ? list.map((item) => (item.id === saved.id ? saved : item)) : [saved, ...list]
    })
    if (!dialog.project) navigate(routes.project(saved.id))
  }

  const newButton = canEdit ? (
    <Button onClick={() => setDialog({ open: true })}>
      <Plus /> New project
    </Button>
  ) : null

  return (
    <section className="grid grid-cols-1 gap-5">
      <PageHeader
        title="Projects"
        description={`${projects.data?.filter((item) => item.status === 'active').length ?? 0} active projects in ${workspace?.workspace.name ?? 'this workspace'}`}
        actions={newButton}
      />
      <FilterBar query={query} onQueryChange={setQuery} placeholder="Search projects">
        <Select inputSize="sm" value={status} onChange={(event) => setStatus(event.target.value)} className="h-9.5 sm:w-40" aria-label="Filter by status">
          <option value="active">Active</option>
          <option value="archived">Archived</option>
          <option value="">All</option>
        </Select>
      </FilterBar>

      {projects.loading && !projects.data ? (
        <LoadingState rows={3} />
      ) : projects.error ? (
        <ErrorState message={projects.error} onRetry={projects.reload} />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Folder}
          title={projects.data?.length ? 'No projects match' : 'Create your first project'}
          description={projects.data?.length ? 'Try a different search or status filter.' : 'Projects group the SRS generations, documents and diagrams for one system.'}
          action={projects.data?.length ? undefined : newButton}
        />
      ) : (
        <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((project) => (
            <article
              key={project.id}
              className="group relative flex flex-col gap-4 rounded-xl border border-border bg-surface p-5 shadow-[var(--elev-1)] transition hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-[var(--elev-2)]"
            >
              <div className="flex items-start justify-between gap-3">
                <span className="grid size-11 place-items-center rounded-xl bg-gradient-to-br from-accent/15 to-accent2/15 text-accent ring-1 ring-inset ring-accent/15">
                  <Folder className="size-5" />
                </span>
                {canEdit ? (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm" className="relative z-10 px-2" aria-label={`Actions for ${project.name}`}>
                        <MoreHorizontal />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onSelect={() => setDialog({ open: true, project })}>
                        <Pencil /> Edit details
                      </DropdownMenuItem>
                      <DropdownMenuItem onSelect={() => navigate(routes.generate(), { project: project.id })} disabled={project.status !== 'active'}>
                        <Plus /> Generate SRS
                      </DropdownMenuItem>
                      {project.status === 'active' ? (
                        <>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem onSelect={() => void archive(project)} className="text-danger data-[highlighted]:text-danger">
                            <Archive /> Archive
                          </DropdownMenuItem>
                        </>
                      ) : null}
                    </DropdownMenuContent>
                  </DropdownMenu>
                ) : null}
              </div>
              <div className="min-w-0">
                <a
                  href={href(routes.project(project.id))}
                  className="font-display text-[16px] font-bold text-fg after:absolute after:inset-0 after:rounded-xl group-hover:text-accent"
                >
                  {project.name}
                </a>
                <p className="mt-1 line-clamp-2 text-[13px] leading-relaxed text-fg-2">{project.description || 'No description'}</p>
              </div>
              <div className="mt-auto flex items-center justify-between border-t border-border pt-3 text-xs text-fg-3">
                <Chip tone={project.status === 'active' ? 'success' : 'muted'}>{project.status === 'active' ? 'Active' : 'Archived'}</Chip>
                <span>Updated {relativeTime(project.updated_at)}</span>
              </div>
            </article>
          ))}
        </div>
      )}

      <ProjectDialog
        open={dialogOpen}
        project={dialog.project}
        onOpenChange={(open) => {
          setDialog((current) => ({ ...current, open }))
          if (!open && createRequested) navigate(routes.projects(), undefined, { replace: true })
        }}
        onSaved={onSaved}
      />
    </section>
  )
}
