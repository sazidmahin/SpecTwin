import type { ReactNode } from 'react'
import { ArrowRight, FileText, MoreHorizontal, Network, Pencil, Trash2, WandSparkles } from 'lucide-react'
import type { Diagram, PipelineRunSummary, Project, SrsDocument } from '../../api'
import { ENGINE_LABELS, STAGE_LABELS, relativeTime } from '../../shared/format'
import {
  Button,
  Card,
  Chip,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  EmptyState,
  LinkButton,
} from '../../shared/ui'
import { href, routes } from '../core/router'
import { RunStatusChip } from './StatusChip'

type ProjectsById = Map<string, Project>

function requirementSummary(document: SrsDocument) {
  const requirements = document.content_json.requirements ?? []
  if (!requirements.length) return null
  const functional = requirements.filter((item) => item.type !== 'non_functional').length
  return `${functional} FR · ${requirements.length - functional} NFR`
}

export function DocumentList({
  documents,
  projects,
  showProject = true,
  emptyAction,
}: {
  documents: SrsDocument[]
  projects?: ProjectsById
  showProject?: boolean
  emptyAction?: ReactNode
}) {
  if (!documents.length) {
    return (
      <EmptyState
        icon={FileText}
        title="No SRS documents yet"
        description="A document is published automatically when you accept the last stage of a generation."
        action={emptyAction}
      />
    )
  }
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 2xl:grid-cols-3">
      {documents.map((document) => {
        const summary = requirementSummary(document)
        const projectName = projects?.get(document.project_id)?.name
        return (
          <a
            key={document.id}
            href={href(routes.document(document.project_id, document.id))}
            className="group flex flex-col gap-3 rounded-xl border border-border bg-surface p-4 shadow-[var(--elev-1)] transition hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-[var(--elev-2)]"
          >
            <div className="flex items-start gap-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent/10 text-accent ring-1 ring-inset ring-accent/15">
                <FileText className="size-[18px]" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="line-clamp-2 text-[14px] font-semibold leading-snug text-fg group-hover:text-accent">{document.title}</p>
                <p className="mt-0.5 truncate text-xs text-fg-3">
                  {showProject && projectName ? `${projectName} · ` : ''}
                  Updated {relativeTime(document.updated_at)}
                </p>
              </div>
            </div>
            <div className="mt-auto flex flex-wrap items-center gap-1.5">
              {document.content_json.generationMode ? (
                <Chip tone="ai">{ENGINE_LABELS[document.content_json.generationMode] ?? document.content_json.generationMode}</Chip>
              ) : null}
              {summary ? <Chip tone="muted">{summary}</Chip> : null}
              {document.diagram_id ? (
                <Chip tone="sky">
                  <Network /> Diagram
                </Chip>
              ) : null}
            </div>
          </a>
        )
      })}
    </div>
  )
}

export function RunList({
  runs,
  showProject = true,
  canEdit,
  onRename,
  onDelete,
  emptyAction,
  emptyTitle,
  emptyDescription,
}: {
  runs: PipelineRunSummary[]
  showProject?: boolean
  canEdit: boolean
  onRename?: (run: PipelineRunSummary) => void
  onDelete?: (run: PipelineRunSummary) => void
  emptyAction?: ReactNode
  emptyTitle?: string
  emptyDescription?: string
}) {
  if (!runs.length) {
    return (
      <EmptyState
        icon={WandSparkles}
        title={emptyTitle ?? 'No generations yet'}
        description={emptyDescription ?? 'Start a generation to turn a plain-language description into a reviewed SRS.'}
        action={emptyAction}
      />
    )
  }
  return (
    <Card className="overflow-hidden">
      <ul className="divide-y divide-border">
        {runs.map((run) => {
          const target = href(routes.run(run.project_id, run.id))
          return (
            <li key={run.id} className="group relative flex items-center gap-3 px-4 py-3.5 transition hover:bg-surface-2 sm:px-5">
              <span className="hidden size-10 shrink-0 place-items-center rounded-xl bg-surface-3 text-fg-2 sm:grid">
                <WandSparkles className="size-[18px]" />
              </span>
              <div className="min-w-0 flex-1">
                <a href={target} className="block truncate text-[13.5px] font-semibold text-fg after:absolute after:inset-0 group-hover:text-accent">
                  {run.title}
                </a>
                <p className="mt-0.5 truncate text-xs text-fg-3">
                  {showProject && run.project_name ? `${run.project_name} · ` : ''}
                  {ENGINE_LABELS[run.generation_mode] ?? run.generation_mode}
                  {run.status !== 'completed' ? ` · at ${STAGE_LABELS[run.current_stage] ?? run.current_stage}` : ''} · {relativeTime(run.updated_at)}
                </p>
              </div>
              <div className="relative z-10 flex shrink-0 items-center gap-2">
                <RunStatusChip status={run.status} />
                {run.srs_document_id ? (
                  <span className="hidden md:block">
                    <LinkButton href={href(routes.document(run.project_id, run.srs_document_id))} variant="secondary" size="sm">
                      <FileText /> Document
                    </LinkButton>
                  </span>
                ) : null}
                {canEdit && (onRename || onDelete) ? (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm" className="px-2" aria-label={`Actions for ${run.title}`}>
                        <MoreHorizontal />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onSelect={() => (window.location.hash = target)}>
                        <ArrowRight /> Open
                      </DropdownMenuItem>
                      {run.srs_document_id ? (
                        <DropdownMenuItem onSelect={() => (window.location.hash = href(routes.document(run.project_id, run.srs_document_id!)))}>
                          <FileText /> Open document
                        </DropdownMenuItem>
                      ) : null}
                      {onRename ? (
                        <DropdownMenuItem onSelect={() => onRename(run)}>
                          <Pencil /> Rename
                        </DropdownMenuItem>
                      ) : null}
                      {onDelete ? (
                        <>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem onSelect={() => onDelete(run)} className="text-danger data-[highlighted]:text-danger">
                            <Trash2 /> Delete
                          </DropdownMenuItem>
                        </>
                      ) : null}
                    </DropdownMenuContent>
                  </DropdownMenu>
                ) : null}
              </div>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

export function DiagramList({
  diagrams,
  projects,
  showProject = true,
  emptyAction,
}: {
  diagrams: Diagram[]
  projects?: ProjectsById
  showProject?: boolean
  emptyAction?: ReactNode
}) {
  if (!diagrams.length) {
    return (
      <EmptyState
        icon={Network}
        title="No diagrams yet"
        description="Completed generations save their UML class diagram here. You can also create a blank draw.io diagram."
        action={emptyAction}
      />
    )
  }
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {diagrams.map((diagram) => (
        <a
          key={diagram.id}
          href={href(routes.diagram(diagram.project_id, diagram.id))}
          className="group flex flex-col overflow-hidden rounded-xl border border-border bg-surface shadow-[var(--elev-1)] transition hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-[var(--elev-2)]"
        >
          <div className="relative grid h-28 place-items-center border-b border-border bg-surface-2 bg-[radial-gradient(var(--color-border-strong)_1px,transparent_1px)] [background-size:14px_14px]">
            <span className="grid size-12 place-items-center rounded-2xl bg-surface text-accent shadow-[var(--elev-2)] ring-1 ring-border">
              <Network className="size-6" />
            </span>
          </div>
          <div className="flex flex-1 flex-col gap-2 p-4">
            <p className="line-clamp-2 text-[13.5px] font-semibold text-fg group-hover:text-accent">{diagram.title}</p>
            <p className="truncate text-xs text-fg-3">
              {showProject && projects?.get(diagram.project_id) ? `${projects.get(diagram.project_id)!.name} · ` : ''}v{diagram.current_version} ·{' '}
              {relativeTime(diagram.updated_at)}
            </p>
            <div className="mt-auto flex gap-1.5 pt-1">
              <Chip tone={diagram.source === 'generated' ? 'ai' : 'muted'}>{diagram.source === 'generated' ? 'Generated' : 'Manual'}</Chip>
              <Chip tone="muted">{diagram.diagram_type}</Chip>
            </div>
          </div>
        </a>
      ))}
    </div>
  )
}
