import { useMemo, useState } from 'react'
import { ArrowLeft, ArrowLeftRight, FileText, GitCompareArrows } from 'lucide-react'
import type { SrsDocument } from '../api'
import { projectApi, srsApi } from '../api'
import { ErrorState, LoadingState } from '../app/components/PageStates'
import { href, navigate, routes } from '../app/core/router'
import { useSession } from '../app/core/session'
import { useAsync } from '../app/core/useAsync'
import { diffLines, diffRequirements, toHunks } from '../features/srs/documentDiff'
import type { RequirementChange } from '../features/srs/documentDiff'
import { ENGINE_LABELS, formatDateTime } from '../shared/format'
import { Button, Card, Chip, EmptyState, PageHeader, Select, Switch, Tabs, TabsContent, TabsList, TabsTrigger, cn } from '../shared/ui'

const KIND_STYLES = {
  added: 'bg-success/10 text-fg',
  removed: 'bg-danger/10 text-fg',
  same: 'text-fg-2',
}

function DocumentPicker({
  label,
  value,
  exclude,
  documents,
  projectNames,
  onChange,
}: {
  label: string
  value: string
  exclude: string
  documents: SrsDocument[]
  projectNames: Map<string, string>
  onChange: (id: string) => void
}) {
  return (
    <label className="grid min-w-0 flex-1 gap-1.5">
      <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-fg-3">{label}</span>
      <Select value={value} onChange={(event) => onChange(event.target.value)} aria-label={label}>
        <option value="">Select a document…</option>
        {documents.map((document) => (
          <option key={document.id} value={document.id} disabled={document.id === exclude}>
            {document.title}
            {projectNames.get(document.project_id) ? ` — ${projectNames.get(document.project_id)}` : ''} ({formatDateTime(document.updated_at)})
          </option>
        ))}
      </Select>
    </label>
  )
}

function DocumentMeta({ document, tone }: { document: SrsDocument; tone: 'danger' | 'success' }) {
  const mode = document.content_json.generationMode
  return (
    <a
      href={href(routes.document(document.project_id, document.id))}
      className={cn(
        'flex min-w-0 flex-1 flex-col gap-1 rounded-xl border p-3 transition hover:border-accent/40',
        tone === 'danger' ? 'border-danger/25' : 'border-success/25',
      )}
    >
      <span className="flex items-center gap-1.5 truncate text-[13px] font-semibold text-fg">
        <FileText className="size-3.5 shrink-0 text-fg-3" /> {document.title}
      </span>
      <span className="flex flex-wrap items-center gap-1.5 text-xs text-fg-3">
        {mode ? <Chip tone="ai">{ENGINE_LABELS[mode] ?? mode}</Chip> : null}
        {(document.content_json.requirements ?? []).length} requirements · Updated {formatDateTime(document.updated_at)}
      </span>
    </a>
  )
}

function RequirementRow({ change }: { change: RequirementChange }) {
  const chip = {
    same: <Chip tone="muted">Unchanged</Chip>,
    changed: <Chip tone="warning">Changed</Chip>,
    added: <Chip tone="success">Added</Chip>,
    removed: <Chip tone="danger">Removed</Chip>,
  }[change.kind]
  const left = 'left' in change ? change.left : undefined
  const right = 'right' in change ? change.right : undefined
  const idLabel = left && right && left.id !== right.id ? `${left.id} → ${right.id}` : (left ?? right)!.id
  return (
    <li className="grid grid-cols-1 gap-2 border-b border-border px-4 py-3 last:border-b-0 md:grid-cols-[8rem_minmax(0,1fr)_minmax(0,1fr)]">
      <div className="flex flex-wrap items-start gap-1.5 md:flex-col">
        <span className="font-mono text-xs font-semibold text-fg">{idLabel}</span>
        {chip}
      </div>
      <p className={cn('rounded-lg px-2.5 py-1.5 text-[13px]', left ? (change.kind === 'same' ? 'text-fg-2' : 'bg-danger/8 text-fg') : 'text-fg-3 italic')}>
        {left ? left.statement : 'Not in this document'}
      </p>
      <p className={cn('rounded-lg px-2.5 py-1.5 text-[13px]', right ? (change.kind === 'same' ? 'text-fg-2' : 'bg-success/8 text-fg') : 'text-fg-3 italic')}>
        {right ? right.statement : 'Not in this document'}
      </p>
    </li>
  )
}

function Comparison({ left, right }: { left: SrsDocument; right: SrsDocument }) {
  const [showUnchanged, setShowUnchanged] = useState(false)
  const lines = useMemo(() => diffLines(left.content_markdown, right.content_markdown), [left.content_markdown, right.content_markdown])
  const hunks = useMemo(() => toHunks(lines), [lines])
  const requirements = useMemo(
    () => diffRequirements(left.content_json.requirements ?? [], right.content_json.requirements ?? []),
    [left.content_json.requirements, right.content_json.requirements],
  )
  const count = (kind: RequirementChange['kind']) => requirements.filter((item) => item.kind === kind).length
  const added = lines.filter((op) => op.kind === 'added').length
  const removed = lines.filter((op) => op.kind === 'removed').length
  const visibleRequirements = showUnchanged ? requirements : requirements.filter((item) => item.kind !== 'same')

  return (
    <div className="grid grid-cols-1 gap-4">
      <div className="flex flex-col gap-3 sm:flex-row">
        <DocumentMeta document={left} tone="danger" />
        <DocumentMeta document={right} tone="success" />
      </div>

      <div className="flex flex-wrap gap-2 text-xs">
        <Chip tone="success">+{added} lines</Chip>
        <Chip tone="danger">−{removed} lines</Chip>
        <Chip tone="success">{count('added')} requirements added</Chip>
        <Chip tone="danger">{count('removed')} removed</Chip>
        <Chip tone="warning">{count('changed')} changed</Chip>
        <Chip tone="muted">{count('same')} unchanged</Chip>
      </div>

      <Tabs defaultValue="requirements" className="grid grid-cols-1 gap-3">
        <TabsList className="w-max">
          <TabsTrigger value="requirements">Requirements</TabsTrigger>
          <TabsTrigger value="text">Full text</TabsTrigger>
        </TabsList>

        <TabsContent value="requirements">
          <Card className="overflow-hidden">
            <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5">
              <span className="text-xs text-fg-3">Matched by identical statement first, then by requirement ID.</span>
              <label className="flex items-center gap-2 text-xs text-fg-2">
                <Switch checked={showUnchanged} onCheckedChange={setShowUnchanged} aria-label="Show unchanged requirements" /> Show unchanged
              </label>
            </div>
            {visibleRequirements.length ? (
              <ul>
                {visibleRequirements.map((change, index) => (
                  <RequirementRow key={index} change={change} />
                ))}
              </ul>
            ) : (
              <p className="px-4 py-8 text-center text-sm text-fg-3">
                {requirements.length ? 'Both documents have the same requirements.' : 'Neither document has structured requirements.'}
              </p>
            )}
          </Card>
        </TabsContent>

        <TabsContent value="text">
          <Card className="overflow-x-auto">
            {added || removed ? (
              <table className="w-full border-collapse font-mono text-[12.5px] leading-6">
                <tbody>
                  {hunks.map((hunk, hunkIndex) =>
                    hunk.hidden ? (
                      <tr key={`h${hunkIndex}`} className="bg-surface-2 text-fg-3">
                        <td colSpan={4} className="px-4 py-1 text-center text-xs">
                          ⋯ {hunk.hidden} unchanged line{hunk.hidden === 1 ? '' : 's'}
                        </td>
                      </tr>
                    ) : (
                      hunk.ops.map((op, opIndex) => (
                        <tr key={`${hunkIndex}-${opIndex}`} className={KIND_STYLES[op.kind]}>
                          <td className="w-12 select-none px-2 text-right text-fg-3">{op.leftNo ?? ''}</td>
                          <td className="w-12 select-none px-2 text-right text-fg-3">{op.rightNo ?? ''}</td>
                          <td className={cn('w-5 select-none text-center', op.kind === 'added' ? 'text-success' : op.kind === 'removed' ? 'text-danger' : '')}>
                            {op.kind === 'added' ? '+' : op.kind === 'removed' ? '−' : ''}
                          </td>
                          <td className="whitespace-pre-wrap break-words pr-4">{op.text || ' '}</td>
                        </tr>
                      ))
                    ),
                  )}
                </tbody>
              </table>
            ) : (
              <p className="px-4 py-8 text-center text-sm text-fg-3">The two documents have identical text.</p>
            )}
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

export function DocumentComparePage({ leftId, rightId }: { leftId: string; rightId: string }) {
  const { workspaceId } = useSession()
  const documents = useAsync(() => srsApi.listWorkspace(workspaceId), [workspaceId], Boolean(workspaceId))
  const projects = useAsync(() => projectApi.list(workspaceId), [workspaceId], Boolean(workspaceId))
  const projectNames = useMemo(() => new Map((projects.data ?? []).map((item) => [item.id, item.name])), [projects.data])
  const list = documents.data ?? []
  const left = list.find((item) => item.id === leftId)
  const right = list.find((item) => item.id === rightId)

  const select = (a: string, b: string) => navigate(routes.compareDocuments(), { a, b }, { replace: true })

  return (
    <section className="grid grid-cols-1 gap-5">
      <a href={href(routes.documents())} className="inline-flex w-max items-center gap-1.5 text-xs font-semibold text-fg-3 transition hover:text-accent">
        <ArrowLeft className="size-3.5" /> SRS documents
      </a>
      <PageHeader title="Compare SRS documents" description="See which requirements and lines changed between two published documents." />

      {documents.loading && !documents.data ? (
        <LoadingState rows={3} />
      ) : documents.error ? (
        <ErrorState message={documents.error} onRetry={documents.reload} />
      ) : list.length < 2 ? (
        <EmptyState icon={GitCompareArrows} title="Not enough documents" description="You need at least two SRS documents to compare." />
      ) : (
        <>
          <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-end">
            <DocumentPicker label="Original" value={leftId} exclude={rightId} documents={list} projectNames={projectNames} onChange={(id) => select(id, rightId)} />
            <Button variant="secondary" className="self-center sm:self-end" onClick={() => select(rightId, leftId)} aria-label="Swap documents" disabled={!leftId && !rightId}>
              <ArrowLeftRight />
            </Button>
            <DocumentPicker label="Compared with" value={rightId} exclude={leftId} documents={list} projectNames={projectNames} onChange={(id) => select(leftId, id)} />
          </Card>
          {left && right ? (
            <Comparison left={left} right={right} />
          ) : (
            <EmptyState icon={GitCompareArrows} title="Pick two documents" description="Choose an original and a document to compare it with." />
          )}
        </>
      )}
    </section>
  )
}
