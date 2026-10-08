import type { ClassModelerResult } from '../../api'
import { cn } from '../../shared/ui'
import type { RelationshipKind } from './relationshipGuide'
import { explainRelationship, relationshipGuide, stereotypeGuide } from './relationshipGuide'

const order: RelationshipKind[] = ['inheritance', 'realization', 'composition', 'aggregation', 'association', 'dependency']

/** A small drawing of each UML line end, matching the diagram's markers. */
export function RelationshipGlyph({ kind, className }: { kind: RelationshipKind; className?: string }) {
  const dashedLine = kind === 'realization' || kind === 'dependency'
  return (
    <svg viewBox="0 0 64 20" className={cn('h-5 w-16 shrink-0', className)} aria-hidden>
      <line
        x1={kind === 'composition' || kind === 'aggregation' ? 20 : 2}
        y1="10"
        x2={kind === 'inheritance' || kind === 'realization' ? 46 : 60}
        y2="10"
        strokeDasharray={dashedLine ? '5 3' : undefined}
        className="stroke-fg-2 stroke-[1.5]"
      />
      {kind === 'inheritance' || kind === 'realization' ? (
        <path d="M 46 3 L 61 10 L 46 17 z" className="fill-surface stroke-fg-2 stroke-[1.5]" />
      ) : null}
      {kind === 'composition' ? <path d="M 2 10 L 11 5 L 20 10 L 11 15 z" className="fill-fg-2 stroke-fg-2 stroke-[1.2]" /> : null}
      {kind === 'aggregation' ? <path d="M 2 10 L 11 5 L 20 10 L 11 15 z" className="fill-surface stroke-fg-2 stroke-[1.2]" /> : null}
      {kind === 'association' || kind === 'dependency' ? <path d="M 52 4 L 61 10 L 52 16" className="fill-none stroke-fg-2 stroke-[1.5]" /> : null}
    </svg>
  )
}

export function RelationshipLegend({ model, className }: { model: ClassModelerResult['model']; className?: string }) {
  const present = new Set(model.relationships.map((rel) => rel.type))
  const kinds = [...order.filter((kind) => present.has(kind)), ...order.filter((kind) => !present.has(kind))]
  const stereotypes = new Set(model.classes.map((cls) => cls.stereotype))

  return (
    <div className={cn('grid grid-cols-1 gap-3', className)}>
      <div>
        <h3 className="font-display text-[14px] font-bold text-fg">How to read this diagram</h3>
        <p className="text-[11.5px] text-fg-3">Line style and the shape at the end tell you the kind of relationship.</p>
      </div>

      <ul className="grid grid-cols-1 gap-2">
        {kinds.map((kind) => {
          const guide = relationshipGuide[kind]
          const examples = model.relationships.filter((rel) => rel.type === kind).slice(0, 2)
          return (
            <li
              key={kind}
              className={cn(
                'rounded-lg border px-3 py-2.5 transition',
                examples.length ? 'border-accent/30 bg-accent/5' : 'border-border bg-surface opacity-60',
              )}
            >
              <div className="flex items-center gap-2.5">
                <RelationshipGlyph kind={kind} />
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[12.5px] font-bold text-fg">{guide.title}</span>
                    <span className="rounded bg-fg/5 px-1 text-[10px] font-semibold text-fg-3">"{guide.reads}"</span>
                  </div>
                  <div className="text-[10.5px] text-fg-3">
                    {guide.line} · {guide.end}
                  </div>
                </div>
              </div>
              <p className="mt-1.5 text-[11.5px] leading-snug text-fg-2">{guide.meaning}</p>
              {examples.length ? (
                <ul className="mt-1.5 grid grid-cols-1 gap-0.5">
                  {examples.map((rel) => (
                    <li key={rel.id} className="text-[11.5px] font-semibold text-accent-dim">
                      e.g. {explainRelationship(rel, model.classes).headline.replace(/\.$/, '')}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 text-[10.5px] italic text-fg-3">Not used in this model.</p>
              )}
            </li>
          )
        })}
      </ul>

      <div className="grid grid-cols-1 gap-1.5 rounded-lg border border-border bg-surface px-3 py-2.5">
        <div className="text-[10.5px] font-bold uppercase tracking-[0.1em] text-fg-3">Box types</div>
        {(['entity', 'abstract', 'interface', 'enumeration'] as const).map((key) => (
          <div key={key} className={cn('flex gap-2 text-[11.5px]', key !== 'enumeration' && !stereotypes.has(key) && key !== 'entity' && 'opacity-60')}>
            <span
              className={cn(
                'mt-0.5 size-3 shrink-0 rounded-sm border-[1.5px]',
                key === 'entity' && 'border-accent/60 bg-accent/15',
                key === 'abstract' && 'border-warning/60 bg-warning/20',
                key === 'interface' && 'border-dashed border-accent2/60 bg-accent2/15',
                key === 'enumeration' && 'border-sky/60 bg-sky/15',
              )}
            />
            <span>
              <strong className="text-fg">{stereotypeGuide[key].label}:</strong> <span className="text-fg-2">{stereotypeGuide[key].meaning}</span>
            </span>
          </div>
        ))}
        <div className="mt-1 text-[11px] text-fg-3">
          <span className="font-mono">-</span> private attribute · <span className="font-mono">+</span> public method ·{' '}
          <span className="font-mono">0..5</span> = up to five · <span className="font-mono">1..*</span> = one or more
        </div>
      </div>
    </div>
  )
}
