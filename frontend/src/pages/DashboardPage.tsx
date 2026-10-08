import { useMemo, useState } from 'react'
import { ArrowRight, Boxes, Check, FileText, Folder, FolderPlus, Network, Sparkles, WandSparkles } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { diagramApi, pipelineApi, projectApi, srsApi } from '../api'
import { DocumentList, RunList } from '../app/components/Lists'
import { ErrorState } from '../app/components/PageStates'
import { ProjectDialog } from '../app/components/ProjectDialog'
import { href, navigate, routes } from '../app/core/router'
import { useSession } from '../app/core/session'
import { useAsync } from '../app/core/useAsync'
import { relativeTime } from '../shared/format'
import { Card, PageHeader, StatTile, cn } from '../shared/ui'

type QuickAction = { title: string; description: string; icon: LucideIcon; onClick: () => void; primary?: boolean }

export function DashboardPage() {
  const { workspaceId, user, workspace, canEdit } = useSession()
  const projects = useAsync(() => projectApi.list(workspaceId), [workspaceId], Boolean(workspaceId))
  const runs = useAsync(() => pipelineApi.listWorkspace(workspaceId), [workspaceId], Boolean(workspaceId))
  const documents = useAsync(() => srsApi.listWorkspace(workspaceId), [workspaceId], Boolean(workspaceId))
  const diagrams = useAsync(() => diagramApi.listWorkspace(workspaceId), [workspaceId], Boolean(workspaceId))
  const [creatingProject, setCreatingProject] = useState(false)

  const firstName = user?.full_name.trim().split(/\s+/)[0] || 'there'
  const activeProjects = useMemo(() => (projects.data ?? []).filter((item) => item.status === 'active'), [projects.data])
  const projectMap = useMemo(() => new Map(activeProjects.map((item) => [item.id, item])), [activeProjects])
  const inProgress = (runs.data ?? []).filter((run) => run.status !== 'completed')
  const completed = (runs.data ?? []).filter((run) => run.status === 'completed').length
  const loadError = projects.error ?? runs.error ?? documents.error ?? diagrams.error

  const actions: QuickAction[] = [
    {
      title: 'Generate an SRS',
      description: 'Describe a system and review six AI-assisted stages.',
      icon: WandSparkles,
      onClick: () => navigate(routes.generate()),
      primary: true,
    },
    { title: 'New project', description: 'Group documents and diagrams for one system.', icon: FolderPlus, onClick: () => setCreatingProject(true) },
    { title: 'Class modeler', description: 'Turn a task statement straight into UML.', icon: Boxes, onClick: () => navigate(routes.classModeler()) },
  ]

  const checklist = [
    { done: activeProjects.length > 0, label: 'Create a project' },
    { done: (runs.data?.length ?? 0) > 0, label: 'Start your first generation' },
    { done: (documents.data?.length ?? 0) > 0, label: 'Publish an SRS document' },
  ]
  const onboarding = projects.data && runs.data && documents.data && checklist.some((item) => !item.done)

  return (
    <section className="grid grid-cols-1 gap-6">
      <PageHeader
        eyebrow={workspace?.workspace.name}
        title={`Welcome back, ${firstName}`}
        description="Pick up where you left off, or start a new specification."
      />

      {loadError ? <ErrorState message={loadError} onRetry={() => void Promise.all([projects.reload(), runs.reload(), documents.reload(), diagrams.reload()])} /> : null}

      <div className="grid grid-cols-2 gap-3 sm:gap-3.5 xl:grid-cols-4">
        <StatTile label="Active projects" value={projects.data ? activeProjects.length : '–'} icon={Folder} />
        <StatTile label="SRS documents" value={documents.data?.length ?? '–'} icon={FileText} />
        <StatTile label="Generations" value={runs.data?.length ?? '–'} icon={WandSparkles}>
          {runs.data ? <p className="text-xs text-fg-3">{completed} completed · {inProgress.length} in progress</p> : null}
        </StatTile>
        <StatTile label="Diagrams" value={diagrams.data?.length ?? '–'} icon={Network} />
      </div>

      {canEdit ? (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {actions.map((action) => {
            const Icon = action.icon
            return (
              <button
                key={action.title}
                type="button"
                onClick={action.onClick}
                className={cn(
                  'group relative flex items-start gap-3.5 overflow-hidden rounded-xl border p-4 text-left transition hover:-translate-y-0.5',
                  action.primary
                    ? 'border-transparent bg-gradient-to-br from-accent to-accent2-dim text-white shadow-[0_12px_28px_-14px_color-mix(in_oklab,var(--color-accent)_90%,transparent)]'
                    : 'border-border bg-surface shadow-[var(--elev-1)] hover:border-accent/40 hover:shadow-[var(--elev-2)]',
                )}
              >
                <span
                  className={cn(
                    'grid size-10 shrink-0 place-items-center rounded-xl',
                    action.primary ? 'bg-white/15 text-white' : 'bg-accent/10 text-accent ring-1 ring-inset ring-accent/15',
                  )}
                >
                  <Icon className="size-5" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className={cn('block text-[14px] font-semibold', action.primary ? 'text-white' : 'text-fg')}>{action.title}</span>
                  <span className={cn('mt-0.5 block text-xs leading-relaxed', action.primary ? 'text-white/80' : 'text-fg-3')}>{action.description}</span>
                </span>
                <ArrowRight className={cn('mt-1 size-4 shrink-0 transition group-hover:translate-x-0.5', action.primary ? 'text-white/80' : 'text-fg-3')} />
              </button>
            )
          })}
        </div>
      ) : null}

      {onboarding ? (
        <Card className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-accent/10 text-accent">
            <Sparkles className="size-5" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="font-display text-[15px] font-bold text-fg">Get started with SpecTwin</p>
            <ul className="mt-2 flex flex-col gap-1.5 sm:flex-row sm:gap-5">
              {checklist.map((item) => (
                <li key={item.label} className={cn('flex items-center gap-2 text-[13px]', item.done ? 'text-fg-3 line-through' : 'text-fg-2')}>
                  <span className={cn('grid size-4.5 place-items-center rounded-full border', item.done ? 'border-success bg-success text-white' : 'border-border-strong')}>
                    {item.done ? <Check className="size-3" /> : null}
                  </span>
                  {item.label}
                </li>
              ))}
            </ul>
          </div>
        </Card>
      ) : null}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <div className="grid grid-cols-1 content-start gap-3">
          <SectionTitle title="Continue reviewing" to={routes.generations()} />
          {runs.data ? <RunList runs={inProgress.slice(0, 5)} canEdit={false} emptyTitle={runs.data?.length ? "Nothing waiting for review" : undefined} emptyDescription={runs.data?.length ? "Every generation is complete. Start a new one any time." : undefined} /> : <Card className="h-40 animate-pulse" />}
        </div>
        <div className="grid grid-cols-1 content-start gap-3">
          <SectionTitle title="Recent projects" to={routes.projects()} />
          <Card className="overflow-hidden">
            {projects.data && activeProjects.length === 0 ? (
              <p className="px-5 py-8 text-center text-[13px] text-fg-3">No projects yet.</p>
            ) : (
              <ul className="divide-y divide-border">
                {[...activeProjects]
                  .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
                  .slice(0, 5)
                  .map((project) => (
                    <li key={project.id}>
                      <a href={href(routes.project(project.id))} className="group flex items-center gap-3 px-4 py-3 transition hover:bg-surface-2">
                        <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent/10 text-accent">
                          <Folder className="size-4" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-[13px] font-semibold text-fg group-hover:text-accent">{project.name}</span>
                          <span className="block truncate text-xs text-fg-3">{project.description || 'No description'}</span>
                        </span>
                        <span className="shrink-0 text-xs text-fg-3">{relativeTime(project.updated_at)}</span>
                      </a>
                    </li>
                  ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      <div className="grid grid-cols-1 content-start gap-3">
        <SectionTitle title="Latest SRS documents" to={routes.documents()} />
        {documents.data ? <DocumentList documents={documents.data.slice(0, 3)} projects={projectMap} /> : <Card className="h-32 animate-pulse" />}
      </div>

      <ProjectDialog open={creatingProject} onOpenChange={setCreatingProject} onSaved={(project) => navigate(routes.project(project.id))} />
    </section>
  )
}

function SectionTitle({ title, to }: { title: string; to: string }) {
  return (
    <div className="flex items-center justify-between px-1">
      <h2 className="font-display text-[15px] font-bold text-fg">{title}</h2>
      <a href={href(to)} className="text-xs font-semibold text-accent hover:text-accent-dim">
        View all
      </a>
    </div>
  )
}
