import { useMemo } from 'react'
import { Cpu, Sparkles } from 'lucide-react'
import type { ClassModelerResult, ModelClass } from '../../api'
import { Chip, cn } from '../../shared/ui'
import { ClassDiagramCanvas } from './diagram/ClassDiagramCanvas'
import { RelationshipGlyph } from './RelationshipLegend'

export type CompareSide = { label: string; result: ClassModelerResult }
type Props = { left: CompareSide; right: CompareSide }

const norm = (value: string) => value.toLowerCase().replace(/[^a-z0-9]/g, '')

function members(cls: ModelClass | undefined, kind: 'attributes' | 'methods') {
  return new Map((cls?.[kind] ?? []).map((item) => [norm(item.name), item.name]))
}

function jaccard(a: Set<string>, b: Set<string>) {
  const union = new Set([...a, ...b])
  if (!union.size) return 100
  return Math.round(([...a].filter((item) => b.has(item)).length / union.size) * 100)
}

function MemberDiff({ rule, llm, leftLabel, rightLabel }: { rule: Map<string, string>; llm: Map<string, string>; leftLabel: string; rightLabel: string }) {
  const keys = [...new Set([...rule.keys(), ...llm.keys()])].sort()
  if (!keys.length) return <span className="text-fg-3">—</span>
  return (
    <div className="flex flex-wrap gap-1">
      {keys.map((key) => {
        const inRule = rule.has(key)
        const inLlm = llm.has(key)
        return (
          <span
            key={key}
            title={inRule && inLlm ? 'In both runs' : inRule ? `${leftLabel} only` : `${rightLabel} only`}
            className={cn(
              'rounded-md px-1.5 py-0.5 font-mono text-[11px]',
              inRule && inLlm && 'bg-success/12 text-fg-2',
              inRule && !inLlm && 'bg-accent/12 text-accent-dim ring-1 ring-accent/30',
              !inRule && inLlm && 'bg-accent2/12 text-accent2-dim ring-1 ring-accent2/30',
            )}
          >
            {rule.get(key) ?? llm.get(key)}
          </span>
        )
      })}
    </div>
  )
}

export function CompareView({ left, right }: Props) {
  const rule = left.result
  const llm = right.result
  const diff = useMemo(() => {
    const ruleClasses = new Map(rule.model.classes.map((cls) => [norm(cls.name), cls]))
    const llmClasses = new Map(llm.model.classes.map((cls) => [norm(cls.name), cls]))
    const names = [...new Set([...ruleClasses.keys(), ...llmClasses.keys()])].sort()
    const rows = names.map((key) => ({
      key,
      name: ruleClasses.get(key)?.name ?? llmClasses.get(key)!.name,
      rule: ruleClasses.get(key),
      llm: llmClasses.get(key),
    }))
    const edgeKey = (source: string, target: string, type: string) => `${norm(source)}|${type}|${norm(target)}`
    const ruleEdges = new Map(rule.model.relationships.map((rel) => [edgeKey(rel.source, rel.target, rel.type), rel]))
    const llmEdges = new Map(llm.model.relationships.map((rel) => [edgeKey(rel.source, rel.target, rel.type), rel]))
    const edgeRows = [...new Set([...ruleEdges.keys(), ...llmEdges.keys()])].sort().map((key) => ({
      key,
      rel: ruleEdges.get(key) ?? llmEdges.get(key)!,
      inRule: ruleEdges.has(key),
      inLlm: llmEdges.has(key),
    }))
    const allMembers = (result: ClassModelerResult) =>
      new Set(result.model.classes.flatMap((cls) => [...cls.attributes, ...cls.methods].map((item) => `${norm(cls.name)}.${norm(item.name)}`)))
    return {
      rows,
      edgeRows,
      classAgreement: jaccard(new Set(ruleClasses.keys()), new Set(llmClasses.keys())),
      memberAgreement: jaccard(allMembers(rule), allMembers(llm)),
      edgeAgreement: jaccard(new Set(ruleEdges.keys()), new Set(llmEdges.keys())),
    }
  }, [rule, llm])

  const scores = [
    { label: 'Classes', value: diff.classAgreement },
    { label: 'Attributes & methods', value: diff.memberAgreement },
    { label: 'Relationships', value: diff.edgeAgreement },
  ]

  return (
    <div className="grid grid-cols-1 gap-5">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {scores.map((score) => (
          <div key={score.label} className="rounded-xl border border-border bg-surface px-4 py-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-fg-3">{score.label} agreement</div>
            <div className="mt-1 flex items-end gap-2">
              <span className="font-display text-2xl font-extrabold text-fg">{score.value}%</span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-3">
              <div className="h-full rounded-full bg-gradient-to-r from-accent to-accent2" style={{ width: `${score.value}%` }} />
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3 text-[11.5px] text-fg-3">
        <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-success/40" /> in both</span>
        <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-accent/40" /> only in {left.label}</span>
        <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-accent2/40" /> only in {right.label}</span>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {[
          { title: left.label, icon: rule.mode === 'rule_based' ? Cpu : Sparkles, result: rule, tone: 'accent' as const },
          { title: right.label, icon: llm.mode === 'rule_based' ? Cpu : Sparkles, result: llm, tone: 'ai' as const },
        ].map((side) => (
          <div key={side.title} className="grid grid-cols-1 gap-2">
            <div className="flex items-center gap-2">
              <side.icon className="size-4 text-fg-2" />
              <span className="font-display text-[14px] font-bold text-fg">{side.title}</span>
              <Chip tone={side.tone}>{side.result.model.classes.length} classes</Chip>
              <Chip tone="neutral">{side.result.model.relationships.length} links</Chip>
            </div>
            <ClassDiagramCanvas model={side.result.model} className="h-[26rem]" compact />
          </div>
        ))}
      </div>

      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full min-w-[42rem] text-left text-[12.5px]">
          <thead className="bg-surface-2 text-[10.5px] uppercase tracking-[0.08em] text-fg-3">
            <tr>
              <th className="px-3 py-2.5 font-semibold">Class</th>
              <th className="px-3 py-2.5 font-semibold">Found by</th>
              <th className="px-3 py-2.5 font-semibold">Attributes</th>
              <th className="px-3 py-2.5 font-semibold">Methods</th>
            </tr>
          </thead>
          <tbody>
            {diff.rows.map((row) => (
              <tr key={row.key} className="border-t border-border align-top">
                <td className="px-3 py-2.5 font-semibold text-fg">{row.name}</td>
                <td className="px-3 py-2.5">
                  {row.rule && row.llm ? <Chip tone="success">Both</Chip> : row.rule ? <Chip tone="accent">Left only</Chip> : <Chip tone="ai">Right only</Chip>}
                </td>
                <td className="px-3 py-2.5">
                  <MemberDiff rule={members(row.rule, 'attributes')} llm={members(row.llm, 'attributes')} leftLabel={left.label} rightLabel={right.label} />
                </td>
                <td className="px-3 py-2.5">
                  <MemberDiff rule={members(row.rule, 'methods')} llm={members(row.llm, 'methods')} leftLabel={left.label} rightLabel={right.label} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-1 gap-2">
        <h3 className="font-display text-[14px] font-bold text-fg">Relationships</h3>
        <ul className="grid grid-cols-1 gap-1.5 md:grid-cols-2">
          {diff.edgeRows.map((row) => (
            <li
              key={row.key}
              className={cn(
                'flex items-center gap-2 rounded-lg border px-3 py-2 text-[12px]',
                row.inRule && row.inLlm && 'border-success/30 bg-success/5',
                row.inRule && !row.inLlm && 'border-accent/30 bg-accent/5',
                !row.inRule && row.inLlm && 'border-accent2/30 bg-accent2/5',
              )}
            >
              <span className="font-semibold text-fg">{row.rel.source}</span>
              <RelationshipGlyph kind={row.rel.type} className="h-4 w-12" />
              <span className="font-semibold text-fg">{row.rel.target}</span>
              {row.rel.label ? <span className="truncate text-fg-3">{row.rel.label}</span> : null}
              <span className="ml-auto text-[10.5px] font-semibold text-fg-3">
                {row.inRule && row.inLlm ? 'both' : row.inRule ? 'left' : 'right'}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
