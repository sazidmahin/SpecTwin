import { useState } from 'react'
import {
  ArrowLeft,
  CheckCircle2,
  Circle,
  CircleDot,
  FileText,
  Loader2,
  MoreHorizontal,
  Network,
  Pencil,
  RotateCcw,
  Trash2,
  XCircle,
} from 'lucide-react'
import { errorMessage, pipelineApi, projectApi } from '../api'
import type { PipelineRun, PipelineStage } from '../api'
import { ErrorState, LoadingState } from '../app/components/PageStates'
import { RunStatusChip } from '../app/components/StatusChip'
import { href, navigate, routes } from '../app/core/router'
import { useSession } from '../app/core/session'
import { useAsync } from '../app/core/useAsync'
import { ENGINE_LABELS, formatDateTime } from '../shared/format'
import {
  Button,
  Card,
  Chip,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Input,
  Modal,
  ModalContent,
  cn,
  useFeedback,
} from '../shared/ui'
import { PIPELINE_STAGES } from '../features/srs/pipelineStages'
import { ErrorNotice, StageReview } from '../features/srs/StageEditors'

type Answer = { questionStableId?: unknown; question_id?: unknown; questionId?: unknown; answerText?: unknown; answer?: unknown; status?: unknown }

/** Returns the clarifications payload with every unresolved question marked skipped, or null if nothing changed. */
function skipUnansweredQuestions(payload: Record<string, unknown>): Record<string, unknown> | null {
  const questions = Array.isArray(payload.clarificationQuestions) ? (payload.clarificationQuestions as Array<Record<string, unknown>>) : []
  const answers = Array.isArray(payload.answers) ? (payload.answers as Answer[]) : []
  const resolved = new Set(
    answers
      .filter((item) => String(item.answerText ?? item.answer ?? '').trim() || item.status === 'skipped' || item.status === 'not_applicable')
      .map((item) => String(item.questionStableId ?? item.question_id ?? item.questionId)),
  )
  const open = questions.filter((question) => (question.status ?? 'open') === 'open' && !resolved.has(String(question.id)))
  if (!open.length) return null
  const openIds = new Set(open.map((question) => String(question.id)))
  return {
    ...payload,
    answers: [
      ...answers.filter((item) => !openIds.has(String(item.questionStableId ?? item.question_id ?? item.questionId))),
      ...open.map((question) => ({ questionStableId: question.id, status: 'skipped' })),
    ],
  }
}

function engineDetail(run: PipelineRun) {
  const engine = ENGINE_LABELS[run.generation_mode] ?? run.generation_mode
  if (run.generation_mode === 'byok' || run.generation_mode === 'ollama') {
    const model = [run.provider, run.model_name].filter(Boolean).join(' · ')
    return model ? `${engine} · ${model}` : engine
  }
  return engine
}

export function RunPage({ projectId, runId }: { projectId: string; runId: string }) {
  const { workspaceId, canEdit } = useSession()
  const { toast, confirm } = useFeedback()
  const run = useAsync(() => pipelineApi.get(workspaceId, projectId, runId), [workspaceId, projectId, runId], Boolean(workspaceId))
  const project = useAsync(() => projectApi.get(workspaceId, projectId), [workspaceId, projectId], Boolean(workspaceId))

  const [viewStage, setViewStage] = useState<PipelineStage | null>(null)
  const [draft, setDraft] = useState<{ stage: PipelineStage; payload: Record<string, unknown> } | null>(null)
  const [classModelReady, setClassModelReady] = useState(false)
  const [busy, setBusy] = useState<null | 'save' | 'approve' | 'reopen' | 'retry'>(null)
  const [error, setError] = useState<string | null>(null)
  const [renaming, setRenaming] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')

  const data = run.data
  const currentStage = data?.current_stage ?? 'input'
  const shownStage = viewStage ?? currentStage
  const revision = data?.stages.find((item) => item.stage_name === shownStage) ?? null
  const isCurrent = shownStage === currentStage
  const completed = data?.status === 'completed'
  const editable = canEdit && isCurrent && !completed && revision?.status === 'ready_for_review'

  // Follow the pipeline forward whenever a new stage becomes current (the page is keyed by run id).
  const [trackedStage, setTrackedStage] = useState(currentStage)
  if (trackedStage !== currentStage) {
    setTrackedStage(currentStage)
    setViewStage(null)
    setDraft(null)
    setClassModelReady(false)
  }

  function replaceRun(next: PipelineRun) {
    run.setData(next)
  }

  async function save(stage: PipelineStage, payload: Record<string, unknown>, version: number) {
    if (!data) return undefined
    setBusy('save')
    setError(null)
    try {
      const saved = await pipelineApi.saveStage(workspaceId, projectId, data.id, stage, payload, version)
      setDraft(null)
      replaceRun({
        ...data,
        status: 'ready_for_review',
        stages: data.stages.map((item) => (item.stage_name === stage ? saved : item)),
      })
      toast('Draft saved', { description: `Version ${saved.version_number}` })
      return saved
    } catch (caught) {
      setError(errorMessage(caught, 'Unable to save this draft'))
      return undefined
    } finally {
      setBusy(null)
    }
  }

  async function approve() {
    if (!data || !revision) return
    setBusy('approve')
    setError(null)
    try {
      let version = revision.version_number
      let payload = draft?.stage === currentStage ? draft.payload : null
      if (currentStage === 'clarifications') {
        // "Accept" means: continue with whatever was answered; anything left open is skipped.
        const withSkips = skipUnansweredQuestions(payload ?? revision.payload)
        if (withSkips) payload = withSkips
      }
      if (payload) {
        const saved = await pipelineApi.saveStage(workspaceId, projectId, data.id, currentStage, payload, version)
        version = saved.version_number
      }
      const next = await pipelineApi.approveStage(workspaceId, projectId, data.id, currentStage, version)
      setDraft(null)
      replaceRun(next)
      if (next.status === 'completed') {
        toast('SRS document created', { description: 'The class diagram was saved to Diagrams too.' })
      }
    } catch (caught) {
      setError(errorMessage(caught, 'Unable to accept this stage'))
      await run.reload()
    } finally {
      setBusy(null)
    }
  }

  async function retry() {
    if (!data) return
    setBusy('retry')
    setError(null)
    try {
      replaceRun(await pipelineApi.next(workspaceId, projectId, data.id))
    } catch (caught) {
      setError(errorMessage(caught, 'The next stage could not be generated'))
      await run.reload()
    } finally {
      setBusy(null)
    }
  }

  async function reopen(stage: PipelineStage) {
    if (!data) return
    const later = PIPELINE_STAGES.slice(PIPELINE_STAGES.findIndex((item) => item.id === stage) + 1).map((item) => item.label)
    const ok = await confirm({
      title: `Reopen “${PIPELINE_STAGES.find((item) => item.id === stage)?.label}”?`,
      description: later.length
        ? `You can edit it again. Later stages (${later.join(', ')}) will be regenerated after you accept it.`
        : 'You can edit it again and re-accept it to refresh the SRS document.',
      confirmLabel: 'Reopen stage',
      tone: 'primary',
    })
    if (!ok) return
    setBusy('reopen')
    setError(null)
    try {
      await pipelineApi.reopenStage(workspaceId, projectId, data.id, stage)
      await run.reload()
      setViewStage(null)
      toast('Stage reopened', { description: 'Make your changes, then accept it again.' })
    } catch (caught) {
      setError(errorMessage(caught, 'Unable to reopen this stage'))
    } finally {
      setBusy(null)
    }
  }

  async function rename() {
    if (!data || !titleDraft.trim()) return
    try {
      replaceRun(await pipelineApi.rename(workspaceId, projectId, data.id, titleDraft.trim()))
      setRenaming(false)
      toast('Generation renamed')
    } catch (caught) {
      toast('Rename failed', { description: errorMessage(caught), tone: 'error' })
    }
  }

  async function remove() {
    if (!data) return
    const ok = await confirm({
      title: 'Delete this generation?',
      description: data.srs_document_id
        ? 'The stage history is removed. The published SRS document and diagram are kept.'
        : 'All stages of this run are removed permanently.',
    })
    if (!ok) return
    try {
      await pipelineApi.remove(workspaceId, projectId, data.id)
      toast('Generation deleted')
      navigate(routes.generations())
    } catch (caught) {
      toast('Delete failed', { description: errorMessage(caught), tone: 'error' })
    }
  }

  if (run.loading && !data) return <LoadingState rows={4} />
  if (run.error || !data) return <ErrorState message={run.error ?? 'Generation not found'} onRetry={run.reload} />

  const stageIndex = PIPELINE_STAGES.findIndex((item) => item.id === currentStage)
  const shownMeta = PIPELINE_STAGES.find((item) => item.id === shownStage)
  const acceptLabel = currentStage === 'xml' ? 'Accept & publish SRS' : 'Accept & continue'

  return (
    <section className="grid grid-cols-1 gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <a
            href={href(project.data ? routes.project(projectId, 'generations') : routes.generations())}
            className="mb-2 inline-flex items-center gap-1.5 text-xs font-semibold text-fg-3 transition hover:text-accent"
          >
            <ArrowLeft className="size-3.5" /> {project.data?.name ?? 'Generations'}
          </a>
          <h1 className="font-display text-[22px] font-extrabold leading-tight tracking-tight text-fg sm:text-[26px]">{data.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-fg-3">
            <RunStatusChip status={data.status} />
            <Chip tone="ai">{engineDetail(data)}</Chip>
            <span>Started {formatDateTime(data.created_at)}</span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {data.srs_document_id ? (
            <Button onClick={() => navigate(routes.document(projectId, data.srs_document_id!))}>
              <FileText /> Open SRS document
            </Button>
          ) : null}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="secondary" aria-label="More actions" className="px-2.5">
                <MoreHorizontal />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                disabled={!canEdit}
                onSelect={() => {
                  setTitleDraft(data.title)
                  setRenaming(true)
                }}
              >
                <Pencil /> Rename
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => navigate(routes.generate(), { project: projectId })}>
                <RotateCcw /> New generation in this project
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem disabled={!canEdit} onSelect={() => void remove()} className="text-danger data-[highlighted]:text-danger">
                <Trash2 /> Delete generation
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {completed ? (
        <Card className="flex flex-col gap-3 border-success/25 bg-success/[0.06] p-4 sm:flex-row sm:items-center">
          <CheckCircle2 className="size-5 shrink-0 text-success" />
          <div className="min-w-0 flex-1">
            <p className="text-[13.5px] font-semibold text-fg">All six stages accepted — your SRS document is ready.</p>
            <p className="text-xs text-fg-2">Reopen any stage to change it; accepting it again refreshes the same document.</p>
          </div>
          {data.srs_document_id ? (
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => navigate(routes.document(projectId, data.srs_document_id!))}>
                <FileText /> View document
              </Button>
              <Button size="sm" variant="secondary" onClick={() => navigate(routes.diagrams())}>
                <Network /> Diagrams
              </Button>
            </div>
          ) : null}
        </Card>
      ) : null}

      {data.status === 'failed' ? (
        <Card className="flex flex-col gap-3 border-danger/25 bg-danger/[0.05] p-4 sm:flex-row sm:items-center">
          <XCircle className="size-5 shrink-0 text-danger" />
          <p className="min-w-0 flex-1 text-[13px] text-fg">
            Generating the stage after <strong>{shownMeta?.label}</strong> failed. Check the engine (Ollama server or AI generation) and try again.
          </p>
          <Button size="sm" onClick={() => void retry()} disabled={busy !== null || !canEdit}>
            {busy === 'retry' ? <Loader2 className="animate-spin" /> : <RotateCcw />} Retry
          </Button>
        </Card>
      ) : null}

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[15.5rem_minmax(0,1fr)]">
        <Card className="p-2 lg:sticky lg:top-20">
          <ol className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible" aria-label="Pipeline stages">
            {PIPELINE_STAGES.map((stage, index) => {
              const stageRevision = data.stages.find((item) => item.stage_name === stage.id)
              const isShown = stage.id === shownStage
              const done = stageRevision?.status === 'approved'
              const stale = stageRevision?.status === 'stale'
              const current = stage.id === currentStage && !completed
              const Icon = done ? CheckCircle2 : current ? CircleDot : Circle
              return (
                <li key={stage.id} className="shrink-0 lg:shrink">
                  <button
                    type="button"
                    disabled={!stageRevision || stale}
                    onClick={() => setViewStage(stage.id === currentStage ? null : stage.id)}
                    aria-current={isShown ? 'step' : undefined}
                    className={cn(
                      'flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left transition disabled:cursor-not-allowed disabled:opacity-50',
                      isShown ? 'bg-accent/10 text-accent' : 'text-fg-2 hover:bg-surface-2 hover:text-fg',
                    )}
                  >
                    <Icon className={cn('size-[18px] shrink-0', done ? 'text-success' : current ? 'text-accent' : 'text-fg-3')} />
                    <span className="min-w-0">
                      <span className="block whitespace-nowrap text-[13px] font-semibold">
                        {index + 1}. {stage.label}
                      </span>
                      <span className="hidden text-[11px] text-fg-3 lg:block">
                        {!stageRevision ? 'Waiting' : stale ? 'Will be regenerated' : done ? 'Accepted' : current ? 'Needs your review' : 'Draft'}
                      </span>
                    </span>
                  </button>
                </li>
              )
            })}
          </ol>
          <div className="mt-2 hidden border-t border-border px-3 pb-2 pt-3 lg:block">
            <div className="mb-1.5 flex justify-between text-[11px] font-semibold text-fg-3">
              <span>Progress</span>
              <span>{completed ? 6 : stageIndex}/6</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-surface-3">
              <div
                className="h-full rounded-full bg-gradient-to-r from-accent to-accent2 transition-[width] duration-500"
                style={{ width: `${((completed ? 6 : stageIndex) / 6) * 100}%` }}
              />
            </div>
          </div>
        </Card>

        <Card className="min-w-0 p-4 sm:p-6">
          {!isCurrent || completed ? (
            <div className="mb-5 flex flex-col gap-3 rounded-lg border border-border bg-surface-2 px-4 py-3 sm:flex-row sm:items-center">
              <p className="min-w-0 flex-1 text-[13px] text-fg-2">
                {revision?.status === 'approved'
                  ? `You are viewing the accepted “${shownMeta?.label}” stage. Reopen it to make changes.`
                  : `You are viewing “${shownMeta?.label}”.`}
              </p>
              <div className="flex gap-2">
                {!isCurrent ? (
                  <Button size="sm" variant="secondary" onClick={() => setViewStage(null)}>
                    Back to current stage
                  </Button>
                ) : null}
                {revision?.status === 'approved' && canEdit ? (
                  <Button size="sm" onClick={() => void reopen(shownStage)} disabled={busy !== null}>
                    {busy === 'reopen' ? <Loader2 className="animate-spin" /> : <RotateCcw />} Reopen to edit
                  </Button>
                ) : null}
              </div>
            </div>
          ) : null}

          {revision ? (
            <fieldset disabled={shownStage !== 'xml' && (!editable || busy !== null)} className="min-w-0 disabled:[&_button]:cursor-not-allowed">
              <StageReview
                key={`${revision.id}-${revision.version_number}`}
                revision={revision}
                stage={shownStage}
                busy={busy !== null}
                onSave={save}
                onDraftChange={(payload) => setDraft({ stage: shownStage, payload })}
                onClassModelReviewStateChange={setClassModelReady}
              />
            </fieldset>
          ) : (
            <p className="text-[13px] text-fg-3">This stage has not been generated yet.</p>
          )}

          {editable ? (
            <div className="mt-6 flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center">
              <Button
                size="lg"
                onClick={() => void approve()}
                disabled={busy !== null || !revision || (currentStage === 'class-model' && !classModelReady)}
              >
                {busy === 'approve' ? <Loader2 className="animate-spin" /> : <CheckCircle2 />}
                {busy === 'approve' ? (currentStage === 'xml' ? 'Publishing…' : 'Generating next stage…') : acceptLabel}
              </Button>
              <p className="text-xs text-fg-3" aria-live="polite">
                {busy === 'approve' && data?.generation_mode === 'ollama' && currentStage !== 'xml'
                  ? 'The local model is working. Without a GPU a stage can take a few minutes, and long input is processed in parts.'
                  : currentStage === 'class-model' && !classModelReady
                  ? 'Confirm the class names, then review the relationships before continuing.'
                  : currentStage === 'xml'
                  ? 'Publishes the SRS document and saves this diagram to Diagrams.'
                  : currentStage === 'clarifications'
                  ? 'Unanswered questions are skipped when you continue.'
                  : draft
                  ? 'Your unsaved edits are saved automatically when you accept.'
                  : shownMeta?.help}
              </p>
            </div>
          ) : null}
          {error ? (
            <div className="mt-4">
              <ErrorNotice text={error} />
            </div>
          ) : null}
        </Card>
      </div>

      <Modal open={renaming} onOpenChange={setRenaming}>
        <ModalContent title="Rename generation">
          <form
            className="grid grid-cols-1 gap-4"
            onSubmit={(event) => {
              event.preventDefault()
              void rename()
            }}
          >
            <Input value={titleDraft} autoFocus maxLength={255} onChange={(event) => setTitleDraft(event.target.value)} />
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setRenaming(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={!titleDraft.trim()}>
                Save
              </Button>
            </div>
          </form>
        </ModalContent>
      </Modal>
    </section>
  )
}
