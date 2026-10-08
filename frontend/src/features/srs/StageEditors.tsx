import { useRef, useState } from 'react'
import { AlertTriangle, Download, ImageDown, Quote, Save } from 'lucide-react'
import type { PipelineStage, PipelineStageRevision } from '../../api'
import { downloadDataUrl } from '../../shared/download'
import { Button, Card, Chip, Textarea, inputClasses, cn } from '../../shared/ui'
import { ClassModelReview } from '../classModelReview/ClassModelReview'
import { DrawioEmbed, type DrawioEmbedHandle } from '../diagram/DrawioEmbed'


export function StageReview({
  revision,
  stage,
  busy,
  onSave,
  onDraftChange,
  onClassModelReviewStateChange,
}: {
  revision: PipelineStageRevision
  stage: PipelineStage
  busy: boolean
  onSave: (
    stage: PipelineStage,
    payload: Record<string, unknown>,
    version: number,
  ) => Promise<PipelineStageRevision | undefined>
  onDraftChange: (payload: Record<string, unknown>) => void
  onClassModelReviewStateChange: (ready: boolean) => void
}) {
  if (stage === 'class-model')
    return (
      <ClassModelReview
        revision={revision}
        busy={busy}
        onSave={async (payload, version) => {
          await onSave(stage, payload, version)
        }}
        onDraftChange={onDraftChange}
        onReviewStateChange={onClassModelReviewStateChange}
      />
    )
  if (stage === 'xml') return <XmlReview revision={revision} />
  return <GenericStageEditor revision={revision} stage={stage} busy={busy} onSave={onSave} onDraftChange={onDraftChange} />
}

function GenericStageEditor({
  revision,
  stage,
  busy,
  onSave,
  onDraftChange,
}: {
  revision: PipelineStageRevision
  stage: PipelineStage
  busy: boolean
  onSave: (
    stage: PipelineStage,
    payload: Record<string, unknown>,
    version: number,
  ) => Promise<PipelineStageRevision | undefined>
  onDraftChange: (payload: Record<string, unknown>) => void
}) {
  // The parent remounts this editor for every new revision, so the initial payload is always current.
  const [payload, setPayload] = useState(revision.payload)
  function updatePayload(nextPayload: Record<string, unknown>) {
    setPayload(nextPayload)
    onDraftChange(nextPayload)
  }

  if (stage === 'input') {
    const normalization = (payload.normalization as Record<string, unknown> | undefined) ?? {}
    return (
      <section className="grid grid-cols-1 content-start gap-3">
        <h2 className="font-display text-xl font-bold text-fg">Review input story</h2>
        <p className="text-[13px] text-fg-3">Improve the source before the pipeline generates clarifications.</p>
        <Textarea
          className="min-h-64"
          value={String(normalization.rawText ?? '')}
          onChange={(event) => updatePayload({ ...payload, normalization: { ...normalization, rawText: event.target.value } })}
        />
        <SaveButton busy={busy} onClick={() => void onSave(stage, payload, revision.version_number)} />
      </section>
    )
  }

  if (stage === 'clarifications')
    return <ClarificationsReview revision={revision} payload={payload} busy={busy} onSave={onSave} onChange={updatePayload} />


  if (stage === 'final-story')
    return <FinalStoryReview revision={revision} payload={payload} busy={busy} onSave={onSave} onChange={updatePayload} />
  if (stage === 'requirements')
    return <RequirementsReview revision={revision} payload={payload} busy={busy} onSave={onSave} onChange={updatePayload} />
  return null
}

const CLARIFICATION_TONES: Record<string, 'warning' | 'ai' | 'danger' | 'muted' | 'accent'> = {
  'Missing Actor': 'warning',
  'Missing Object': 'ai',
  'Missing Action': 'ai',
  'Unknown Action': 'muted',
  'Vague Metric': 'danger',
  'Vague Timing': 'danger',
  'Ambiguous Quantity': 'warning',
  'Pronoun Reference': 'accent',
  'Conflicting Rule': 'danger',
}

type ClarificationAnswer = Record<string, unknown> & {
  questionStableId?: unknown
  question_id?: unknown
  answerText?: unknown
  status?: unknown
}

function ClarificationsReview({
  revision,
  payload,
  busy,
  onSave,
  onChange,
}: {
  revision: PipelineStageRevision
  payload: Record<string, unknown>
  busy: boolean
  onSave: (
    stage: PipelineStage,
    payload: Record<string, unknown>,
    version: number,
  ) => Promise<PipelineStageRevision | undefined>
  onChange: (payload: Record<string, unknown>) => void
}) {
  const questions = Array.isArray(payload.clarificationQuestions)
    ? (payload.clarificationQuestions as Array<Record<string, unknown>>)
    : []
  const answers = Array.isArray(payload.answers) ? (payload.answers as ClarificationAnswer[]) : []

  const matches = (item: ClarificationAnswer, id: unknown) => item.questionStableId === id || item.question_id === id
  const answerFor = (id: unknown) => answers.find((item) => matches(item, id))
  const isResolved = (item: ClarificationAnswer | undefined) =>
    Boolean(item && (String(item.answerText ?? '').trim() || item.status === 'skipped'))
  const resolvedCount = questions.filter((question) => isResolved(answerFor(question.id))).length

  const writeAnswer = (id: unknown, patch: Partial<ClarificationAnswer> | null) =>
    onChange({
      ...payload,
      answers: [
        ...answers.filter((item) => !matches(item, id)),
        ...(patch ? [{ questionStableId: id, ...patch }] : []),
      ],
    })

  return (
    <section className="grid grid-cols-1 content-start gap-4">
      <header>
        <h2 className="font-display text-xl font-bold text-fg">Clarifying questions</h2>
        <p className="mt-1 text-[13px] text-fg-3">
          Each question links back to the sentence that triggered it. Answer or skip every one, then accept to build the
          final story.
        </p>
      </header>

      {questions.length ? (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-warning/20 bg-warning/[0.08] px-4 py-3">
          <AlertTriangle className="size-4 shrink-0 text-warning" />
          <p className="text-[13px] text-fg-2">
            {questions.length} question{questions.length === 1 ? '' : 's'} identified. You can skip any or all and generate
            anyway.
          </p>
          <div className="ml-auto flex items-center gap-2">
            <div className="h-1.5 w-28 overflow-hidden rounded-full bg-warning/20">
              <div
                className="h-full rounded-full bg-warning transition-[width]"
                style={{ width: `${questions.length ? (resolvedCount / questions.length) * 100 : 0}%` }}
              />
            </div>
            <span className="whitespace-nowrap text-[13px] font-bold text-fg">
              {resolvedCount} / {questions.length}
            </span>
          </div>
        </div>
      ) : (
        <p className="rounded-md bg-surface-2 p-4 text-[13px] text-fg-3">
          No ambiguities were detected. Accept this stage to continue.
        </p>
      )}

      <div className="grid grid-cols-1 gap-3.5 lg:grid-cols-2">
        {questions.map((question, index) => {
          const id = question.id
          const answer = answerFor(id)
          const skipped = answer?.status === 'skipped'
          const category = String(question.category ?? 'Clarification')
          const sourceSentence = String(question.sourceSentence ?? question.sourceClause ?? '')
          const sentenceIndex = question.sentenceIndex
          return (
            <Card key={String(id ?? index)} className={cn('p-[18px]', skipped && 'opacity-60')}>
              <div className="mb-2.5 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[11px] font-bold text-fg-3">Q{index + 1}</span>
                  <Chip tone={CLARIFICATION_TONES[category] ?? 'muted'} className="text-[10px]">
                    {category}
                  </Chip>
                </div>
                <button
                  type="button"
                  className="text-[11px] font-semibold text-fg-3 transition hover:text-fg"
                  onClick={() => writeAnswer(id, skipped ? null : { status: 'skipped' })}
                >
                  {skipped ? 'Undo skip' : 'Skip'}
                </button>
              </div>
              <p className="mb-2.5 text-sm font-semibold text-fg">
                {String(question.text ?? question.question ?? `Question ${index + 1}`)}
              </p>
              {sourceSentence ? (
                <div className="mb-3 flex items-start gap-2 rounded-md border border-border bg-surface-2 px-3 py-2.5">
                  <Quote className="mt-0.5 size-3.5 shrink-0 text-warning" />
                  <p className="text-xs italic text-fg-2">
                    {sentenceIndex ? (
                      <span className="mr-1 font-mono not-italic text-fg-3">S{String(sentenceIndex)}</span>
                    ) : null}
                    “{sourceSentence}”
                  </p>
                </div>
              ) : null}
              {question.reason ? (
                <p className="mb-2 text-[11.5px] text-fg-3">{String(question.reason)}</p>
              ) : null}
              <label className="mb-1.5 block text-[11.5px] font-semibold text-fg-3">Your answer</label>
              <input
                className={inputClasses()}
                value={String(answer?.answerText ?? '')}
                placeholder={skipped ? 'Skipped — click Undo skip to answer' : 'Type your answer…'}
                disabled={skipped}
                onChange={(event) => writeAnswer(id, { answerText: event.target.value })}
              />
            </Card>
          )
        })}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <SaveButton busy={busy} onClick={() => void onSave('clarifications', payload, revision.version_number)} />
        {questions.length ? (
          <Button
            variant="secondary"
            size="sm"
            disabled={busy}
            onClick={() => {
              onChange({
                ...payload,
                answers: questions.map((question) => ({ questionStableId: question.id, status: 'skipped' })),
              })
            }}
          >
            Skip all
          </Button>
        ) : null}
        <small className="text-xs text-fg-3">
          {resolvedCount} of {questions.length} answered or skipped
        </small>
      </div>
    </section>
  )
}

function FinalStoryReview({
  revision,
  payload,
  busy,
  onSave,
  onChange,
}: {
  revision: PipelineStageRevision
  payload: Record<string, unknown>
  busy: boolean
  onSave: (
    stage: PipelineStage,
    payload: Record<string, unknown>,
    version: number,
  ) => Promise<PipelineStageRevision | undefined>
  onChange: (payload: Record<string, unknown>) => void
}) {
  const sections = Array.isArray(payload.atomicStorySections)
    ? payload.atomicStorySections.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    : []
  const warnings = Array.isArray(payload.warnings) ? payload.warnings.map(String) : []
  const answers = Array.isArray(payload.appliedClarificationAnswers)
    ? payload.appliedClarificationAnswers.filter(
        (item): item is Record<string, unknown> => typeof item === 'object' && item !== null,
      )
    : []
  function updateSection(index: number, field: string, value: string) {
    const nextSections = sections.map((section, sectionIndex) =>
      sectionIndex === index ? { ...section, [field]: value || null } : section,
    )
    onChange({ ...payload, atomicStorySections: nextSections })
  }
  return (
    <section className="grid grid-cols-1 content-start gap-5">
      <header>
        <h2 className="font-display text-xl font-bold text-fg">Final story</h2>
        <p className="mt-1 text-[13px] text-fg-3">
          Review each generated user story. Correct the sentence or its actor, action, and object before proceeding.
        </p>
      </header>
      {sections.length ? (
        <div className="grid grid-cols-1 gap-4">
          {sections.map((section, index) => {
            const sectionWarnings = Array.isArray(section.warnings) ? section.warnings.map(String) : []
            return (
              <article className="grid grid-cols-1 gap-4 rounded-lg border border-border p-4 shadow-sm" key={String(section.id ?? index)}>
                <header className="flex flex-wrap items-center justify-between gap-2">
                  <Chip tone="accent">{String(section.id ?? `Story ${index + 1}`)}</Chip>
                  {section.modality ? <Chip tone="muted">{String(section.modality)}</Chip> : null}
                </header>
                <label className="grid grid-cols-1 gap-1.5 text-sm font-semibold text-fg-2">
                  User story
                  <Textarea
                    className="min-h-20 font-normal"
                    value={String(section.normalizedSentence ?? '')}
                    onChange={(event) => updateSection(index, 'normalizedSentence', event.target.value)}
                  />
                </label>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <StoryField label="Actor" value={section.actor} onChange={(value) => updateSection(index, 'actor', value)} />
                  <StoryField label="Action" value={section.action} onChange={(value) => updateSection(index, 'action', value)} />
                  <StoryField label="Object" value={section.object} onChange={(value) => updateSection(index, 'object', value)} />
                </div>
                {sectionWarnings.length ? (
                  <div className="rounded-md bg-warning/10 p-3 text-[13px] text-warning">
                    <strong>Needs attention</strong>
                    <ul className="mt-1 list-disc space-y-1 pl-5">
                      {sectionWarnings.map((warning, warningIndex) => (
                        <li key={warningIndex}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </article>
            )
          })}
        </div>
      ) : (
        <p className="rounded-md bg-surface-2 p-4 text-[13px] text-fg-3">No individual user stories were generated.</p>
      )}
      {answers.length ? (
        <details className="rounded-md border border-border p-4">
          <summary className="cursor-pointer text-sm font-semibold text-fg-2">
            Applied clarification answers ({answers.length})
          </summary>
          <ul className="mt-3 grid grid-cols-1 gap-2 text-[13px] text-fg-2">
            {answers.map((answer, index) => (
              <li key={String(answer.questionStableId ?? index)}>
                <span className="font-semibold">{String(answer.questionStableId ?? `Answer ${index + 1}`)}:</span>{' '}
                {String(answer.answerText ?? '')}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {warnings.length ? (
        <div className="rounded-md bg-warning/10 p-4 text-[13px] text-warning">
          <strong>Story-wide warnings</strong>
          <ul className="mt-1 list-disc space-y-1 pl-5">
            {warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <SaveButton busy={busy} onClick={() => void onSave('final-story', payload, revision.version_number)} />
    </section>
  )
}

function StoryField({ label, value, onChange }: { label: string; value: unknown; onChange: (value: string) => void }) {
  return (
    <label className="grid grid-cols-1 gap-1.5 text-sm font-semibold text-fg-2">
      {label}
      <input className={inputClasses()} value={String(value ?? '')} onChange={(event) => onChange(event.target.value)} />
    </label>
  )
}

function RequirementsReview({
  revision,
  payload,
  busy,
  onSave,
  onChange,
}: {
  revision: PipelineStageRevision
  payload: Record<string, unknown>
  busy: boolean
  onSave: (
    stage: PipelineStage,
    payload: Record<string, unknown>,
    version: number,
  ) => Promise<PipelineStageRevision | undefined>
  onChange: (payload: Record<string, unknown>) => void
}) {
  const requirements = Array.isArray(payload.requirements)
    ? payload.requirements.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    : []
  const enabledCount = requirements.filter((requirement) => requirement.enabled !== false).length
  function updateRequirement(index: number, field: string, value: unknown) {
    const nextRequirements = requirements.map((requirement, requirementIndex) =>
      requirementIndex === index ? { ...requirement, [field]: value } : requirement,
    )
    onChange({ ...payload, requirements: nextRequirements })
  }
  return (
    <section className="grid grid-cols-1 content-start gap-5">
      <header>
        <h2 className="font-display text-xl font-bold text-fg">Requirements review</h2>
        <p className="mt-1 text-[13px] text-fg-3">
          Review the generated requirements, adjust wording, and disable any item you do not want to carry forward.
        </p>
        <p className="mt-2 text-[13px] font-semibold text-fg-2">
          {enabledCount} of {requirements.length} requirements included
        </p>
      </header>
      {requirements.length ? (
        <div className="grid grid-cols-1 gap-4">
          {requirements.map((requirement, index) => {
            const type = String(requirement.requirementType ?? 'functional')
            const isNfr = type === 'non_functional'
            const warnings = Array.isArray(requirement.warnings) ? requirement.warnings.map(String) : []
            const enabled = requirement.enabled !== false
            return (
              <article
                className={cn(
                  'grid gap-4 rounded-lg border border-border p-4 shadow-sm',
                  !enabled && 'bg-surface-2 opacity-65',
                )}
                key={String(requirement.id ?? index)}
              >
                <header className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Chip tone="accent">
                      {String(requirement.requirementId ?? requirement.id ?? `Requirement ${index + 1}`)}
                    </Chip>
                    <Chip tone="muted">{type.replaceAll('_', ' ')}</Chip>
                  </div>
                  <label className="flex items-center gap-2 text-sm font-semibold text-fg-2">
                    <input
                      className="size-4 accent-accent"
                      type="checkbox"
                      checked={enabled}
                      onChange={(event) => updateRequirement(index, 'enabled', event.target.checked)}
                    />
                    Include
                  </label>
                </header>
                <label className="grid grid-cols-1 gap-1.5 text-sm font-semibold text-fg-2">
                  Requirement statement
                  <Textarea
                    className="min-h-20 font-normal"
                    value={String(requirement.statement ?? '')}
                    onChange={(event) => updateRequirement(index, 'statement', event.target.value)}
                  />
                </label>
                {requirement.sourceSentence ? (
                  <p className="-mt-2 text-[11.5px] italic text-fg-3">
                    Traces to: “{String(requirement.sourceSentence)}”
                  </p>
                ) : null}
                {isNfr ? (
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <StoryField label="Category" value={requirement.nfrCategory} onChange={(value) => updateRequirement(index, 'nfrCategory', value || null)} />
                    <StoryField label="Metric" value={requirement.metric} onChange={(value) => updateRequirement(index, 'metric', value || null)} />
                    <StoryField label="Target" value={requirement.targetValue} onChange={(value) => updateRequirement(index, 'targetValue', value || null)} />
                    <StoryField label="Unit" value={requirement.unit} onChange={(value) => updateRequirement(index, 'unit', value || null)} />
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                    <StoryField label="Actor" value={requirement.actor} onChange={(value) => updateRequirement(index, 'actor', value || null)} />
                    <StoryField label="Action" value={requirement.action} onChange={(value) => updateRequirement(index, 'action', value || null)} />
                    <StoryField label="Object" value={requirement.object} onChange={(value) => updateRequirement(index, 'object', value || null)} />
                  </div>
                )}
                {warnings.length ? (
                  <div className="rounded-md bg-warning/10 p-3 text-[13px] text-warning">
                    <strong>Needs attention</strong>
                    <ul className="mt-1 list-disc space-y-1 pl-5">
                      {warnings.map((warning, warningIndex) => (
                        <li key={warningIndex}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </article>
            )
          })}
        </div>
      ) : (
        <p className="rounded-md bg-surface-2 p-4 text-[13px] text-fg-3">No requirements were generated.</p>
      )}
      <SaveButton busy={busy} onClick={() => void onSave('requirements', payload, revision.version_number)} />
    </section>
  )
}

function XmlReview({ revision }: { revision: PipelineStageRevision }) {
  const xml = typeof revision.payload.xml === 'string' ? revision.payload.xml : ''
  const valid = (revision.payload.validation as Record<string, unknown> | undefined)?.valid === true
  const drawioRef = useRef<DrawioEmbedHandle>(null)
  const [pngError, setPngError] = useState<string | null>(null)
  const [isExportingPng, setIsExportingPng] = useState(false)

  function download() {
    const file = new Blob([xml], { type: 'application/xml;charset=utf-8' })
    const url = URL.createObjectURL(file)
    const link = document.createElement('a')
    link.href = url
    link.download = 'class-diagram.drawio'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  async function downloadPng() {
    if (!drawioRef.current) return
    setPngError(null)
    setIsExportingPng(true)
    try {
      const dataUrl = await drawioRef.current.exportImage('png')
      downloadDataUrl('class-diagram.png', dataUrl)
    } catch (caught) {
      setPngError(caught instanceof Error ? caught.message : 'Unable to export diagram as PNG')
    } finally {
      setIsExportingPng(false)
    }
  }

  return (
    <section className="grid grid-cols-1 content-start gap-5">
      <header>
        <h2 className="font-display text-xl font-bold text-fg">Draw.io class diagram</h2>
        <p className="mt-1 text-[13px] text-fg-3">
          Preview the generated class diagram, then download the compatible Draw.io XML file if you need to keep editing it.
        </p>
      </header>
      <div className={cn('rounded-md p-4 text-[13px]', valid ? 'bg-success/10 text-success' : 'bg-warning/10 text-warning')}>
        <strong>{valid ? 'Diagram validated' : 'Diagram needs review'}</strong>
        <p className="mt-1">
          {valid ? 'The XML is ready to preview, download, and open in Draw.io.' : 'Review the XML before using it.'}
        </p>
      </div>
      {xml ? <DrawioEmbed ref={drawioRef} xml={xml} title="Draw.io class diagram preview" className="h-[32rem]" /> : null}
      <div className="flex flex-wrap gap-2">
        <Button disabled={!xml} onClick={download}>
          <Download /> Download Draw.io XML
        </Button>
        <Button variant="secondary" disabled={!xml || isExportingPng} onClick={() => void downloadPng()}>
          <ImageDown /> {isExportingPng ? 'Exporting…' : 'Download as PNG'}
        </Button>
      </div>
      {pngError ? <p className="text-[13px] text-danger">{pngError}</p> : null}
      <details className="rounded-md border border-border p-4">
        <summary className="cursor-pointer text-sm font-semibold text-fg-2">View XML source</summary>
        <pre className="mt-3 max-h-96 overflow-auto rounded-md bg-sidebar p-3 font-mono text-xs leading-5 text-sidebar-fg-active">
          {xml || 'No XML was generated.'}
        </pre>
      </details>
    </section>
  )
}

function SaveButton({ busy, onClick }: { busy: boolean; onClick: () => void }) {
  return (
    <Button className="w-max" disabled={busy} onClick={onClick}>
      <Save /> {busy ? 'Saving…' : 'Save draft'}
    </Button>
  )
}

export function ErrorNotice({ text }: { text: string }) {
  return (
    <p className="flex items-center gap-2 rounded-md bg-danger/10 p-3 text-[13px] text-danger">
      <AlertTriangle className="size-4" /> {text}
    </p>
  )
}
