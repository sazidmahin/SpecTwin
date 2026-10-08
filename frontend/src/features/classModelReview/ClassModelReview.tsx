import { AlertTriangle, ArrowLeft, ArrowRight, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import type { PipelineStageRevision } from '../../api'
import { Button, inputClasses } from '../../shared/ui'

type Entity = Record<string, unknown>
type Props = {
  revision: PipelineStageRevision
  busy: boolean
  onSave: (payload: Record<string, unknown>, expectedVersion: number) => Promise<void>
  onDraftChange: (payload: Record<string, unknown>) => void
  onReviewStateChange: (ready: boolean) => void
}

const control = inputClasses()

function asRows(value: unknown): Entity[] {
  return Array.isArray(value) ? value.filter((item): item is Entity => typeof item === 'object' && item !== null) : []
}
function text(item: Entity, key: string) {
  return typeof item[key] === 'string' ? item[key] : ''
}
function identifier(label: string, prefix: string) {
  return `${prefix}_${label.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || Date.now()}`
}
function warnings(item: Entity) {
  return Array.isArray(item.warnings) ? item.warnings.map(String) : []
}

export function ClassModelReview({ revision, busy, onSave, onDraftChange, onReviewStateChange }: Props) {
  const [draft, setDraft] = useState<Record<string, unknown>>(revision.payload)
  const [phase, setPhase] = useState<'classes' | 'relationships'>('classes')
  const classes = asRows(draft.classes)
  const relationships = asRows(draft.relationships)
  const includedClasses = classes.filter((item) => item.enabled !== false)
  const includedClassIds = new Set(includedClasses.map((item) => text(item, 'id')))
  // Only relationships between two included classes belong in this review; an
  // edge to an excluded class is carried in the draft but hidden until the class
  // is included again.
  const visibleRelationships = relationships
    .map((item, index) => ({ item, index }))
    .filter(
      ({ item }) =>
        includedClassIds.has(text(item, 'sourceClassId')) && includedClassIds.has(text(item, 'targetClassId')),
    )

  function updateDraft(updater: (current: Record<string, unknown>) => Record<string, unknown>) {
    setDraft((current) => {
      const next = updater(current)
      onDraftChange(next)
      return next
    })
  }
  function updateClass(index: number, patch: Entity) {
    updateDraft((current) => ({
      ...current,
      classes: asRows(current.classes).map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    }))
  }
  // Excluding a class also excludes every relationship attached to it, so the
  // relationship review never asks about edges that point at a hidden class.
  // Re-including brings an edge back only when its other endpoint is included too.
  function setClassEnabled(index: number, enabled: boolean) {
    updateDraft((current) => {
      const rows = asRows(current.classes)
      const rowsAfter = rows.map((item, itemIndex) => (itemIndex === index ? { ...item, enabled } : item))
      const enabledIds = new Set(rowsAfter.filter((item) => item.enabled !== false).map((item) => text(item, 'id')))
      const classId = text(rows[index], 'id')
      return {
        ...current,
        classes: rowsAfter,
        relationships: asRows(current.relationships).map((relationship) => {
          const source = text(relationship, 'sourceClassId')
          const target = text(relationship, 'targetClassId')
          if (source !== classId && target !== classId) return relationship
          return { ...relationship, enabled: enabledIds.has(source) && enabledIds.has(target) }
        }),
      }
    })
  }
  function updateRelationship(index: number, patch: Entity) {
    updateDraft((current) => ({
      ...current,
      relationships: asRows(current.relationships).map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...patch } : item,
      ),
    }))
  }
  function addClass() {
    updateDraft((current) => ({
      ...current,
      classes: [
        ...asRows(current.classes),
        { id: identifier('NewClass', 'class'), name: 'NewClass', enabled: true, attributes: [], methods: [], sourceRequirementIds: [], warnings: [] },
      ],
    }))
  }
  function removeClass(index: number) {
    const removed = text(classes[index], 'id')
    if (window.confirm('Delete this class? Any relationships connected to it will also be removed.'))
      updateDraft((current) => ({
        ...current,
        classes: asRows(current.classes).filter((_, itemIndex) => itemIndex !== index),
        relationships: asRows(current.relationships).filter(
          (relationship) =>
            text(relationship, 'sourceClassId') !== removed && text(relationship, 'targetClassId') !== removed,
        ),
      }))
  }
  function addRelationship() {
    if (!includedClasses.length) return
    updateDraft((current) => ({
      ...current,
      relationships: [
        ...asRows(current.relationships),
        {
          id: identifier(`edge_${relationships.length + 1}`, 'edge'),
          type: 'association',
          sourceClassId: text(includedClasses[0], 'id'),
          targetClassId: text(includedClasses[1] ?? includedClasses[0], 'id'),
          direction: 'undirected',
          sourceMultiplicity: '1',
          targetMultiplicity: '0..*',
          label: '',
          enabled: true,
          warnings: [],
        },
      ],
    }))
  }
  function reviewRelationships() {
    setPhase('relationships')
    onReviewStateChange(true)
  }
  function reviewClasses() {
    setPhase('classes')
    onReviewStateChange(false)
  }

  if (phase === 'classes')
    return (
      <section className="grid grid-cols-1 content-start gap-5">
        <header className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div>
            <h2 className="font-display text-xl font-bold text-fg">Check class names</h2>
            <p className="mt-1 text-[13px] text-fg-3">
              Confirm that these are the right classes. You do not need to review technical details here.
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={addClass}>
            <Plus /> Add class
          </Button>
        </header>
        <div className="grid grid-cols-1 gap-3">
          {classes.map((item, index) => (
            <article
              className="flex flex-col gap-3 rounded-lg border border-border p-4 sm:flex-row sm:items-center"
              key={text(item, 'id') || index}
            >
              <input
                className={control}
                aria-label={`Class ${index + 1} name`}
                value={text(item, 'name')}
                onChange={(event) => updateClass(index, { name: event.target.value })}
              />
              <label className="flex items-center gap-2 whitespace-nowrap text-sm font-semibold text-fg-2">
                <input
                  className="size-4 accent-accent"
                  type="checkbox"
                  checked={item.enabled !== false}
                  onChange={(event) => setClassEnabled(index, event.target.checked)}
                />
                Include
              </label>
              <button
                className="rounded-md p-2 text-danger hover:bg-danger/10"
                type="button"
                aria-label={`Delete ${text(item, 'name') || 'class'}`}
                onClick={() => removeClass(index)}
              >
                <Trash2 className="size-4" />
              </button>
              {warnings(item).length ? (
                <span title={warnings(item).join('\n')} className="text-warning">
                  <AlertTriangle className="size-4" />
                </span>
              ) : null}
            </article>
          ))}
        </div>
        {!classes.length ? (
          <p className="rounded-md bg-surface-2 p-4 text-[13px] text-fg-3">
            No classes were generated. Add the classes you want to include.
          </p>
        ) : null}
        <footer className="flex flex-wrap gap-3 border-t border-border pt-4">
          <Button onClick={reviewRelationships} disabled={busy || !classes.length}>
            Class names look good <ArrowRight />
          </Button>
          <Button variant="secondary" onClick={() => void onSave(draft, revision.version_number)} disabled={busy}>
            {busy ? 'Saving…' : 'Save draft'}
          </Button>
        </footer>
      </section>
    )

  return (
    <section className="grid grid-cols-1 content-start gap-5">
      <header className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h2 className="font-display text-xl font-bold text-fg">Review relationships</h2>
          <p className="mt-1 text-[13px] text-fg-3">
            Connect the approved classes and confirm their relationship type and multiplicity.
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={addRelationship} disabled={!includedClasses.length}>
          <Plus /> Add relationship
        </Button>
      </header>
      <div className="grid grid-cols-1 gap-4">
        {visibleRelationships.map(({ item, index }) => (
          <article className="grid grid-cols-1 gap-3 rounded-lg border border-border p-4" key={text(item, 'id') || index}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <ClassSelect
                label="From"
                classes={includedClasses}
                selected={text(item, 'sourceClassId')}
                onChange={(sourceClassId) => updateRelationship(index, { sourceClassId })}
              />
              <label className="grid grid-cols-1 gap-1.5 text-sm font-semibold text-fg-2">
                Relationship
                <select
                  className={control}
                  value={text(item, 'type') || 'association'}
                  onChange={(event) => updateRelationship(index, { type: event.target.value })}
                >
                  {['association', 'aggregation', 'composition', 'dependency', 'inheritance', 'realization'].map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
              </label>
              <ClassSelect
                label="To"
                classes={includedClasses}
                selected={text(item, 'targetClassId')}
                onChange={(targetClassId) => updateRelationship(index, { targetClassId })}
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <label className="grid grid-cols-1 gap-1.5 text-sm font-semibold text-fg-2">
                From multiplicity
                <input
                  className={control}
                  placeholder="e.g. 1"
                  value={text(item, 'sourceMultiplicity')}
                  onChange={(event) => updateRelationship(index, { sourceMultiplicity: event.target.value || null })}
                />
              </label>
              <label className="grid grid-cols-1 gap-1.5 text-sm font-semibold text-fg-2">
                To multiplicity
                <input
                  className={control}
                  placeholder="e.g. 0..*"
                  value={text(item, 'targetMultiplicity')}
                  onChange={(event) => updateRelationship(index, { targetMultiplicity: event.target.value || null })}
                />
              </label>
              <label className="grid grid-cols-1 gap-1.5 text-sm font-semibold text-fg-2">
                Label (optional)
                <input
                  className={control}
                  value={text(item, 'label')}
                  onChange={(event) => updateRelationship(index, { label: event.target.value })}
                />
              </label>
            </div>
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-sm font-semibold text-fg-2">
                <input
                  className="size-4 accent-accent"
                  type="checkbox"
                  checked={item.enabled !== false}
                  onChange={(event) => updateRelationship(index, { enabled: event.target.checked })}
                />
                Include
              </label>
              <button
                className="rounded-md p-2 text-danger hover:bg-danger/10"
                type="button"
                aria-label="Delete relationship"
                onClick={() =>
                  updateDraft((current) => ({
                    ...current,
                    relationships: asRows(current.relationships).filter(
                      (_, relationshipIndex) => relationshipIndex !== index,
                    ),
                  }))
                }
              >
                <Trash2 className="size-4" />
              </button>
            </div>
            {warnings(item).length ? (
              <div className="rounded-md bg-warning/10 p-3 text-[13px] text-warning">
                <strong>Needs attention</strong>
                <ul className="mt-1 list-disc pl-5">
                  {warnings(item).map((warning, warningIndex) => (
                    <li key={warningIndex}>{warning}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </article>
        ))}
      </div>
      {!visibleRelationships.length ? (
        <p className="rounded-md bg-surface-2 p-4 text-[13px] text-fg-3">
          No relationships between the included classes. Add any relationships you need before continuing.
        </p>
      ) : null}
      <footer className="flex flex-wrap gap-3 border-t border-border pt-4">
        <Button variant="secondary" onClick={reviewClasses}>
          <ArrowLeft /> Back to class names
        </Button>
        <Button variant="secondary" onClick={() => void onSave(draft, revision.version_number)} disabled={busy}>
          {busy ? 'Saving…' : 'Save draft'}
        </Button>
      </footer>
    </section>
  )
}

function ClassSelect({
  label,
  classes,
  selected,
  onChange,
}: {
  label: string
  classes: Entity[]
  selected: string
  onChange: (value: string) => void
}) {
  return (
    <label className="grid grid-cols-1 gap-1.5 text-sm font-semibold text-fg-2">
      {label}
      <select className={control} value={selected} onChange={(event) => onChange(event.target.value)}>
        {classes.map((item) => (
          <option key={text(item, 'id')} value={text(item, 'id')}>
            {text(item, 'name') || 'Unnamed class'}
          </option>
        ))}
      </select>
    </label>
  )
}
