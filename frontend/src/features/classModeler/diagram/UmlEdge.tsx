import { useState } from 'react'
import { EdgeLabelRenderer, useInternalNode } from '@xyflow/react'
import type { Edge, EdgeProps, InternalNode } from '@xyflow/react'
import type { ModelRelationship } from '../../../api'
import { cn } from '../../../shared/ui'
import { relationshipGuide } from '../relationshipGuide'

export type UmlEdgeData = {
  rel: ModelRelationship | null
  kind: ModelRelationship['type'] | 'enum-type'
  markerPrefix: string
  headline: string
  detail: string
  offset: number
  focus: 'none' | 'highlight' | 'dimmed'
}
export type UmlEdgeType = Edge<UmlEdgeData, 'uml'>

type Pt = { x: number; y: number }

function centre(node: InternalNode): Pt {
  const { x, y } = node.internals.positionAbsolute
  return { x: x + (node.measured.width ?? 0) / 2, y: y + (node.measured.height ?? 0) / 2 }
}

/** Where the line from `node`'s centre towards `toward` leaves its rectangle. */
function borderPoint(node: InternalNode, toward: Pt): Pt {
  const c = centre(node)
  const halfW = (node.measured.width ?? 0) / 2 + 2
  const halfH = (node.measured.height ?? 0) / 2 + 2
  const dx = toward.x - c.x
  const dy = toward.y - c.y
  if (dx === 0 && dy === 0) return c
  const scale = 1 / Math.max(Math.abs(dx) / halfW, Math.abs(dy) / halfH)
  return { x: c.x + dx * scale, y: c.y + dy * scale }
}

function markersFor(kind: UmlEdgeData['kind'], prefix: string) {
  switch (kind) {
    case 'inheritance':
    case 'realization':
      return { end: `url(#${prefix}-triangle)` }
    case 'composition':
      return { start: `url(#${prefix}-diamond-filled)` }
    case 'aggregation':
      return { start: `url(#${prefix}-diamond-open)` }
    case 'association':
    case 'dependency':
    case 'enum-type':
      return { end: `url(#${prefix}-arrow)` }
  }
}

const dashed = new Set(['realization', 'dependency', 'enum-type'])

export function UmlEdge({ id, source, target, data, selected }: EdgeProps<UmlEdgeType>) {
  const sourceNode = useInternalNode(source)
  const targetNode = useInternalNode(target)
  const [hovered, setHovered] = useState(false)
  if (!sourceNode || !targetNode || !data) return null

  const markers = markersFor(data.kind, data.markerPrefix)
  let path: string
  let labelAt: Pt
  let sourceEnd: Pt
  let targetEnd: Pt

  if (source === target) {
    // Reflexive association ("a user follows other users"): a loop on the right.
    const { x, y } = sourceNode.internals.positionAbsolute
    const w = sourceNode.measured.width ?? 0
    const h = sourceNode.measured.height ?? 0
    sourceEnd = { x: x + w, y: y + h * 0.3 }
    targetEnd = { x: x + w, y: y + h * 0.7 }
    path = `M ${sourceEnd.x} ${sourceEnd.y} C ${x + w + 90} ${sourceEnd.y - 30}, ${x + w + 90} ${targetEnd.y + 30}, ${targetEnd.x} ${targetEnd.y}`
    labelAt = { x: x + w + 72, y: y + h / 2 }
  } else {
    sourceEnd = borderPoint(sourceNode, centre(targetNode))
    targetEnd = borderPoint(targetNode, centre(sourceNode))
    const mid = { x: (sourceEnd.x + targetEnd.x) / 2, y: (sourceEnd.y + targetEnd.y) / 2 }
    if (data.offset) {
      // Two edges between the same pair bow apart instead of overlapping.
      const dx = targetEnd.x - sourceEnd.x
      const dy = targetEnd.y - sourceEnd.y
      const length = Math.hypot(dx, dy) || 1
      const control = { x: mid.x - (dy / length) * data.offset * 2, y: mid.y + (dx / length) * data.offset * 2 }
      path = `M ${sourceEnd.x} ${sourceEnd.y} Q ${control.x} ${control.y} ${targetEnd.x} ${targetEnd.y}`
      labelAt = { x: (mid.x + control.x) / 2, y: (mid.y + control.y) / 2 }
    } else {
      path = `M ${sourceEnd.x} ${sourceEnd.y} L ${targetEnd.x} ${targetEnd.y}`
      labelAt = mid
    }
  }

  const active = hovered || selected || data.focus === 'highlight'
  const rel = data.rel
  const guide = data.kind === 'enum-type' ? null : relationshipGuide[data.kind]
  const nearEnd = (from: Pt, to: Pt, distance: number): Pt => {
    const dx = to.x - from.x
    const dy = to.y - from.y
    const length = Math.hypot(dx, dy) || 1
    return { x: from.x + (dx / length) * distance, y: from.y + (dy / length) * distance }
  }
  const sourceLabel = rel?.sourceMultiplicity ? nearEnd(sourceEnd, targetEnd, 22) : null
  const targetLabel = rel?.targetMultiplicity ? nearEnd(targetEnd, sourceEnd, 22) : null

  return (
    <>
      <path
        id={id}
        d={path}
        markerStart={markers.start}
        markerEnd={markers.end}
        strokeDasharray={dashed.has(data.kind) ? '6 4' : undefined}
        className={cn(
          'fill-none transition-[stroke,opacity] duration-200',
          active ? 'stroke-accent-dim stroke-[2.2]' : 'stroke-fg-3 stroke-[1.4]',
          data.focus === 'dimmed' && 'opacity-20',
        )}
      />
      <path
        d={path}
        className="cursor-pointer fill-none stroke-transparent stroke-[16]"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      />
      <EdgeLabelRenderer>
        {rel?.label && data.kind !== 'inheritance' && data.kind !== 'realization' ? (
          <div
            className={cn(
              'nodrag nopan pointer-events-auto absolute -translate-x-1/2 -translate-y-1/2 rounded-full border px-2 py-0.5 text-[10.5px] font-semibold shadow-xs transition',
              active ? 'border-accent/50 bg-accent/10 text-fg' : 'border-border bg-surface text-fg-2',
              data.focus === 'dimmed' && 'opacity-20',
            )}
            style={{ left: labelAt.x, top: labelAt.y }}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
          >
            {rel.label}
          </div>
        ) : null}
        {[
          { at: sourceLabel, text: rel?.sourceMultiplicity },
          { at: targetLabel, text: rel?.targetMultiplicity },
        ].map((item, index) =>
          item.at && item.text ? (
            <div
              key={index}
              className={cn(
                'pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded bg-bg/90 px-1 font-mono text-[10.5px] font-semibold',
                rel?.multiplicityAssumed ? 'text-fg-3 italic' : 'text-fg-2',
                data.focus === 'dimmed' && 'opacity-20',
              )}
              style={{ left: item.at.x, top: item.at.y }}
            >
              {item.text}
            </div>
          ) : null,
        )}
        {hovered ? (
          <div
            className="pointer-events-none absolute z-50 w-64 -translate-x-1/2 translate-y-4 rounded-lg border border-border-strong bg-surface p-3 shadow-xl"
            style={{ left: labelAt.x, top: labelAt.y }}
          >
            <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-accent">
              {guide ? guide.title : 'Attribute type'}
            </div>
            <div className="mt-0.5 text-[13px] font-semibold text-fg">{data.headline}</div>
            {data.detail ? <p className="mt-1 text-[11.5px] leading-snug text-fg-2">{data.detail}</p> : null}
            {guide ? (
              <p className="mt-2 border-t border-border pt-2 text-[10.5px] text-fg-3">
                {guide.line} · {guide.end}
              </p>
            ) : null}
          </div>
        ) : null}
      </EdgeLabelRenderer>
    </>
  )
}

/** SVG markers for every UML line end, scoped by `prefix` so two diagrams can share a page. */
export function UmlMarkers({ prefix }: { prefix: string }) {
  return (
    <svg className="absolute size-0" aria-hidden>
      <defs>
        <marker id={`${prefix}-triangle`} viewBox="0 0 20 20" refX="19" refY="10" markerWidth="18" markerHeight="18" markerUnits="userSpaceOnUse" orient="auto-start-reverse">
          <path d="M 1 1 L 19 10 L 1 19 z" className="fill-surface stroke-fg-2 stroke-[1.5]" />
        </marker>
        <marker id={`${prefix}-diamond-filled`} viewBox="0 0 24 14" refX="1" refY="7" markerWidth="24" markerHeight="14" markerUnits="userSpaceOnUse" orient="auto-start-reverse">
          <path d="M 1 7 L 12 1 L 23 7 L 12 13 z" className="fill-fg-2 stroke-fg-2 stroke-[1.2]" />
        </marker>
        <marker id={`${prefix}-diamond-open`} viewBox="0 0 24 14" refX="1" refY="7" markerWidth="24" markerHeight="14" markerUnits="userSpaceOnUse" orient="auto-start-reverse">
          <path d="M 1 7 L 12 1 L 23 7 L 12 13 z" className="fill-surface stroke-fg-2 stroke-[1.2]" />
        </marker>
        <marker id={`${prefix}-arrow`} viewBox="0 0 16 16" refX="15" refY="8" markerWidth="14" markerHeight="14" markerUnits="userSpaceOnUse" orient="auto-start-reverse">
          <path d="M 1 1 L 15 8 L 1 15" className="fill-none stroke-fg-2 stroke-[1.5]" />
        </marker>
      </defs>
    </svg>
  )
}
