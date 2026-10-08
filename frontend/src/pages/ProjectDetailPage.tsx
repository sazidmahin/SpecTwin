import { useMemo, useState } from 'react'
import { ArrowLeft, FileText, Folder, Network, Pencil, Plus, WandSparkles } from 'lucide-react'
import { diagramApi, pipelineApi, projectApi, srsApi } from '../api'
import { DiagramDialog } from '../app/components/DiagramDialog'
import { DiagramList, DocumentList, RunList } from '../app/components/Lists'
import { ErrorState, LoadingState } from '../app/components/PageStates'
import { ProjectDialog } from '../app/components/ProjectDialog'
import { useRunActions } from '../app/components/useRunActions'
import { href, navigate, routes } from '../app/core/router'
import { useSession } from '../app/core/session'
import { useAsync } from '../app/core/useAsync'
import { formatDate } from '../shared/format'
import { Button, Chip, LinkButton, StatTile, cn } from '../shared/ui'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'documents', label: 'SRS documents' },
  { id: 'generations', label: 'Generations' },
  { id: 'diagrams', label: 'Diagrams' },
] as const

type TabId = (typeof TABS)[number]['id']

export function ProjectDetailPage({ projectId, tab }: { projectId: string; tab?: string }) {
  const { workspaceId, canEdit } = useSession()
  const activeTab: TabId = TABS.some((item) => item.id === tab) ? (tab as TabId) : 'overview'
  const project = useAsync(() => projectApi.get(workspaceId, projectId), [workspaceId, projectId], Boolean(workspaceId))
  const documents = useAsync(() => srsApi.listProject(workspaceId, projectId), [workspaceId, projectId], Boolean(workspaceId))
  const runs = useAsync(() => pipelineApi.listProject(workspaceId, projectId), [workspaceId, projectId], Boolean(workspaceId))
  const diagrams = useAsync(() => diagramApi.listProject(workspaceId, projectId), [workspaceId, projectId], Boolean(workspaceId))
  const runActions = useRunActions(() => void runs.reload())
  const [editing, setEditing] = useState(false)
  const [creatingDiagram, setCreatingDiagram] = useState(false)

  const runsWithProject = useMemo(
    () => (runs.data ?? []).map((run) => ({ ...run, project_name: project.data?.name })),
    [runs.data, project.data?.name],
  )
  const inProgress = runsWithProject.filter((run) => run.status !== 'completed')

  if (project.loading && !project.data) return <LoadingState rows={3} />
  if (project.error || !project.data) return <ErrorState message={project.error ?? 'Project not found'} onRetry={project.reload} />

  const data = project.data
  const active = data.status === 'active'
  const generateButton =
    canEdit && active ? (
      <LinkButton href={href(routes.generate(), { project: projectId })}>
        <WandSparkles /> Generate SRS
      </LinkButton>
    ) : null

  return (
    <section className="grid grid-cols-1 gap-5">
      <div>
        <a href={href(routes.projects())} className="mb-3 inline-flex items-center gap-1.5 text-xs font-semibold text-fg-3 transition hover:text-accent">
          <ArrowLeft className="size-3.5" /> Projects
        </a>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-4">
            <span className="hidden size-14 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-accent to-accent2-dim text-white shadow-[var(--elev-2)] sm:grid">
              <Folder className="size-6" />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="font-display text-[22px] font-extrabold leading-tight tracking-tight text-fg sm:text-[26px]">{data.name}</h1>
                {!active ? <Chip tone="muted">Archived</Chip> : null}
              </div>
              <p className="mt-1 max-w-2xl text-[13.5px] text-fg-2">{data.description || 'No description yet.'}</p>
              <p className="mt-1 text-xs text-fg-3">Created {formatDate(data.created_at)}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {canEdit ? (
              <Button variant="secondary" onClick={() => setEditing(true)}>
                <Pencil /> Edit
              </Button>
            ) : null}
            {generateButton}
          </div>
        </div>
      </div>

      <nav className="-mx-1 flex gap-1 overflow-x-auto border-b border-border px-1" aria-label="Project sections">
        {TABS.map((item) => {
          const count =
            item.id === 'documents' ? documents.data?.length : item.id === 'generations' ? runs.data?.length : item.id === 'diagrams' ? diagrams.data?.length : undefined
          const selected = item.id === activeTab
          return (
            <a
              key={item.id}
              href={href(routes.project(projectId, item.id === 'overview' ? undefined : item.id))}
              aria-current={selected ? 'page' : undefined}
              className={cn(
                '-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 text-[13px] font-semibold transition',
                selected ? 'border-accent text-accent' : 'border-transparent text-fg-3 hover:text-fg',
              )}
            >
              {item.label}
              {count !== undefined ? (
                <span className={cn('rounded-full px-1.5 py-px text-[11px]', selected ? 'bg-accent/15' : 'bg-surface-3')}>{count}</span>
              ) : null}
            </a>
          )
        })}
      </nav>

      {activeTab === 'overview' ? (
        <div className="grid grid-cols-1 gap-5">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile label="SRS documents" value={documents.data?.length ?? '–'} icon={FileText} />
            <StatTile label="Generations" value={runs.data?.length ?? '–'} icon={WandSparkles} />
            <StatTile label="In progress" value={runs.data ? inProgress.length : '–'} icon={WandSparkles} />
            <StatTile label="Diagrams" value={diagrams.data?.length ?? '–'} icon={Network} />
          </div>
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <div className="grid grid-cols-1 content-start gap-3">
              <SectionTitle title="Continue reviewing" to={routes.project(projectId, 'generations')} />
              <RunList runs={inProgress.slice(0, 4)} showProject={false} canEdit={false} emptyAction={generateButton} emptyTitle={runs.data?.length ? "Nothing waiting for review" : undefined} emptyDescription={runs.data?.length ? "Every generation is complete. Start a new one any time." : undefined} />
            </div>
            <div className="grid grid-cols-1 content-start gap-3">
              <SectionTitle title="Latest documents" to={routes.project(projectId, 'documents')} />
              <DocumentList documents={(documents.data ?? []).slice(0, 2)} showProject={false} />
            </div>
          </div>
        </div>
      ) : null}

      {activeTab === 'documents' ? (
        documents.error ? (
          <ErrorState message={documents.error} onRetry={documents.reload} />
        ) : documents.loading && !documents.data ? (
          <LoadingState />
        ) : (
          <DocumentList documents={documents.data ?? []} showProject={false} emptyAction={generateButton} />
        )
      ) : null}

      {activeTab === 'generations' ? (
        runs.error ? (
          <ErrorState message={runs.error} onRetry={runs.reload} />
        ) : runs.loading && !runs.data ? (
          <LoadingState />
        ) : (
          <RunList runs={runsWithProject} showProject={false} canEdit={canEdit} onRename={runActions.onRename} onDelete={runActions.onDelete} emptyAction={generateButton} />
        )
      ) : null}

      {activeTab === 'diagrams' ? (
        <div className="grid grid-cols-1 gap-4">
          {canEdit && active && diagrams.data?.length ? (
            <div className="flex justify-end">
              <Button variant="secondary" onClick={() => setCreatingDiagram(true)}>
                <Plus /> New diagram
              </Button>
            </div>
          ) : null}
          {diagrams.error ? (
            <ErrorState message={diagrams.error} onRetry={diagrams.reload} />
          ) : diagrams.loading && !diagrams.data ? (
            <LoadingState />
          ) : (
            <DiagramList
              diagrams={diagrams.data ?? []}
              showProject={false}
              emptyAction={
                canEdit && active ? (
                  <Button onClick={() => setCreatingDiagram(true)}>
                    <Plus /> New diagram
                  </Button>
                ) : undefined
              }
            />
          )}
        </div>
      ) : null}

      {runActions.dialog}
      <ProjectDialog open={editing} project={data} onOpenChange={setEditing} onSaved={(saved) => project.setData(saved)} />
      <DiagramDialog
        open={creatingDiagram}
        onOpenChange={setCreatingDiagram}
        projects={[data]}
        defaultProjectId={data.id}
        onCreated={(diagram) => navigate(routes.diagram(diagram.project_id, diagram.id))}
      />
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
