import '@xyflow/react/dist/base.css'
import { useCallback, useId, useImperativeHandle, useMemo, useState } from 'react'
import type { Ref } from 'react'
import { Background, BackgroundVariant, MiniMap, ReactFlow, ReactFlowProvider, useNodesState, useReactFlow } from '@xyflow/react'
import { LayoutGrid, Maximize2, MousePointerClick, X, ZoomIn, ZoomOut } from 'lucide-react'
import type { ClassModelerResult, ModelClass, ModelRelationship } from '../../../api'
import { Button, Chip, Tooltip, cn } from '../../../shared/ui'
import { explainRelationship, relationshipGuide, stereotypeGuide } from '../relationshipGuide'
import { buildDiagramSvg, svgToPng } from './exportImage'
import { estimateClassBox, estimateEnumBox, layoutDiagram } from './layout'
import { UmlClassNode } from './UmlClassNode'
import type { UmlNode } from './UmlClassNode'
import { UmlEdge, UmlMarkers } from './UmlEdge'
import type { UmlEdgeType } from './UmlEdge'

const nodeTypes = { uml: UmlClassNode }
const edgeTypes = { uml: UmlEdge }

export type ClassDiagramHandle = {
  /** The diagram exactly as arranged on screen, as an SVG document. */
  exportSvg: () => { svg: string; width: number; height: number }
  exportPng: () => Promise<string>
}

type Props = { model: ClassModelerResult['model']; className?: string; compact?: boolean; ref?: Ref<ClassDiagramHandle> }

const modelKeys = new WeakMap<object, number>()
let nextModelKey = 0

/** A fresh canvas (layout, selection, viewport) for every new model. */
function keyFor(model: object) {
  if (!modelKeys.has(model)) modelKeys.set(model, (nextModelKey += 1))
  return modelKeys.get(model)
}

export function ClassDiagramCanvas(props: Props) {
  return (
    <ReactFlowProvider>
      <Canvas key={keyFor(props.model)} {...props} />
    </ReactFlowProvider>
  )
}

function parentsOf(cls: ModelClass, relationships: ModelRelationship[]) {
  return relationships
    .filter((rel) => rel.sourceClassId === cls.id && (rel.type === 'inheritance' || rel.type === 'realization'))
    .map((rel) => ({ name: rel.target, via: rel.type === 'inheritance' ? ('extends' as const) : ('implements' as const) }))
}

function buildGraph(model: Props['model'], markerPrefix: string) {
  const classIds = new Set(model.classes.map((cls) => cls.id))
  const relationships = model.relationships.filter((rel) => classIds.has(rel.sourceClassId) && classIds.has(rel.targetClassId))
  const byName = new Map(model.classes.map((cls) => [cls.name, cls]))
  const enumEdges = model.enums
    .map((item) => {
      const owner = model.classes.find((cls) => cls.attributes.some((attr) => attr.type === item.name)) ?? (item.owner ? byName.get(item.owner) : undefined)
      return owner ? { owner, item } : null
    })
    .filter((value): value is NonNullable<typeof value> => value !== null)

  const boxes = [...model.classes.map(estimateClassBox), ...model.enums.map(estimateEnumBox)]
  const positions = layoutDiagram(
    boxes,
    relationships,
    enumEdges.map(({ owner, item }) => [owner.id, item.id]),
  )

  const nodes: UmlNode[] = [
    ...model.classes.map((cls) => ({
      id: cls.id,
      type: 'uml' as const,
      position: positions[cls.id] ?? { x: 0, y: 0 },
      data: { kind: 'class' as const, cls, parents: parentsOf(cls, relationships), focus: 'none' as const },
    })),
    ...model.enums.map((item) => ({
      id: item.id,
      type: 'uml' as const,
      position: positions[item.id] ?? { x: 0, y: 0 },
      data: { kind: 'enum' as const, enumeration: item, parents: [], focus: 'none' as const },
    })),
  ]

  const pairCount = new Map<string, number>()
  const edges: UmlEdgeType[] = [
    ...relationships.map((rel) => {
      const pair = [rel.sourceClassId, rel.targetClassId].sort().join('|')
      const seen = pairCount.get(pair) ?? 0
      pairCount.set(pair, seen + 1)
      const { headline, detail } = explainRelationship(rel, model.classes)
      return {
        id: rel.id,
        source: rel.sourceClassId,
        target: rel.targetClassId,
        type: 'uml' as const,
        data: { rel, kind: rel.type, markerPrefix, headline, detail, offset: seen * 28, focus: 'none' as const },
      }
    }),
    ...enumEdges.map(({ owner, item }) => {
      const attribute = owner.attributes.find((attr) => attr.type === item.name)?.name ?? 'status'
      return {
        id: `enum-edge-${owner.id}-${item.id}`,
        source: owner.id,
        target: item.id,
        type: 'uml' as const,
        data: {
          rel: null,
          kind: 'enum-type' as const,
          markerPrefix,
          headline: `${owner.name}.${attribute} is a ${item.name}`,
          detail: `It can only hold one of: ${item.literals.join(', ')}.`,
          offset: 0,
          focus: 'none' as const,
        },
      }
    }),
  ]
  return { nodes, edges, relationships }
}

function Canvas({ model, className, compact, ref }: Props) {
  const markerPrefix = `uml${useId().replace(/[^a-zA-Z0-9]/g, '')}`
  const graph = useMemo(() => buildGraph(model, markerPrefix), [model, markerPrefix])
  const [nodes, setNodes, onNodesChange] = useNodesState<UmlNode>(graph.nodes)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const { fitView, zoomIn, zoomOut, getNodes } = useReactFlow()

  useImperativeHandle(ref, () => {
    const exportSvg = () => {
      const placed = getNodes().map((node) => ({
        id: node.id,
        x: node.position.x,
        y: node.position.y,
        width: node.measured?.width ?? node.width ?? 200,
        height: node.measured?.height ?? node.height ?? 120,
      }))
      return buildDiagramSvg(model, placed)
    }
    return {
      exportSvg,
      exportPng: () => {
        const { svg, width, height } = exportSvg()
        return svgToPng(svg, width, height)
      },
    }
  }, [getNodes, model])

  const related = useMemo(() => {
    if (!selectedId) return null
    const ids = new Set([selectedId])
    for (const edge of graph.edges) {
      if (edge.source === selectedId) ids.add(edge.target)
      if (edge.target === selectedId) ids.add(edge.source)
    }
    return ids
  }, [selectedId, graph.edges])

  const viewNodes = useMemo(
    () =>
      nodes.map((node) => ({
        ...node,
        data: {
          ...node.data,
          focus: !related ? ('none' as const) : node.id === selectedId ? ('selected' as const) : related.has(node.id) ? ('related' as const) : ('dimmed' as const),
        },
      })),
    [nodes, related, selectedId],
  )
  const viewEdges = useMemo(
    () =>
      graph.edges.map((edge) => ({
        ...edge,
        data: {
          ...edge.data!,
          focus: !selectedId
            ? ('none' as const)
            : edge.source === selectedId || edge.target === selectedId
              ? ('highlight' as const)
              : ('dimmed' as const),
        },
      })),
    [graph.edges, selectedId],
  )

  const relayout = useCallback(() => {
    setNodes(graph.nodes)
    requestAnimationFrame(() => fitView({ padding: 0.15, duration: 400 }))
  }, [graph.nodes, setNodes, fitView])

  const selectedClass = model.classes.find((cls) => cls.id === selectedId)
  const selectedEnum = model.enums.find((item) => item.id === selectedId)

  return (
    <div className={cn('relative overflow-hidden rounded-xl border border-border bg-surface-2', className ?? 'h-[38rem]')}>
      <UmlMarkers prefix={markerPrefix} />
      <ReactFlow
        nodes={viewNodes}
        edges={viewEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onNodeClick={(_, node) => setSelectedId((current) => (current === node.id ? null : node.id))}
        onPaneClick={() => setSelectedId(null)}
        nodesConnectable={false}
        edgesFocusable={false}
        minZoom={0.15}
        maxZoom={2}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        proOptions={{ hideAttribution: true }}
        className="[&_.react-flow__edge-textwrapper]:pointer-events-auto"
      >
        <Background variant={BackgroundVariant.Dots} gap={18} size={1.2} className="!bg-surface-2 [&_circle]:fill-fg-3/30" />
        {!compact ? (
          <MiniMap
            pannable
            zoomable
            className="!m-3 overflow-hidden rounded-lg border border-border !bg-surface shadow-sm"
            nodeClassName="fill-accent/30"
            maskColor="color-mix(in oklab, var(--color-bg) 72%, transparent)"
          />
        ) : null}
      </ReactFlow>

      <div className="absolute left-3 top-3 z-10 flex items-center gap-1 rounded-lg border border-border bg-surface/95 p-1 shadow-sm backdrop-blur">
        <Tooltip content="Zoom in">
          <Button variant="ghost" size="sm" onClick={() => zoomIn({ duration: 200 })} aria-label="Zoom in">
            <ZoomIn />
          </Button>
        </Tooltip>
        <Tooltip content="Zoom out">
          <Button variant="ghost" size="sm" onClick={() => zoomOut({ duration: 200 })} aria-label="Zoom out">
            <ZoomOut />
          </Button>
        </Tooltip>
        <Tooltip content="Fit to screen">
          <Button variant="ghost" size="sm" onClick={() => fitView({ padding: 0.15, duration: 300 })} aria-label="Fit to screen">
            <Maximize2 />
          </Button>
        </Tooltip>
        <Tooltip content="Tidy layout">
          <Button variant="ghost" size="sm" onClick={relayout} aria-label="Tidy layout">
            <LayoutGrid />
          </Button>
        </Tooltip>
      </div>

      {!selectedId && !compact ? (
        <div className="pointer-events-none absolute bottom-3 left-1/2 z-10 flex -translate-x-1/2 items-center gap-1.5 rounded-full border border-border bg-surface/95 px-3 py-1.5 text-[11.5px] text-fg-3 shadow-sm backdrop-blur">
          <MousePointerClick className="size-3.5" /> Click a class to explain it · hover a line to read it · drag to rearrange
        </div>
      ) : null}

      {selectedClass || selectedEnum ? (
        <ClassExplainer
          cls={selectedClass}
          enumName={selectedEnum?.name}
          enumLiterals={selectedEnum?.literals}
          model={model}
          relationships={graph.relationships}
          onClose={() => setSelectedId(null)}
        />
      ) : null}
    </div>
  )
}

function ClassExplainer({
  cls,
  enumName,
  enumLiterals,
  model,
  relationships,
  onClose,
}: {
  cls?: ModelClass
  enumName?: string
  enumLiterals?: string[]
  model: Props['model']
  relationships: ModelRelationship[]
  onClose: () => void
}) {
  const stereotype = enumName ? 'enumeration' : (cls?.stereotype ?? 'entity')
  const guide = stereotypeGuide[stereotype] ?? stereotypeGuide.entity
  const mine = cls ? relationships.filter((rel) => rel.sourceClassId === cls.id || rel.targetClassId === cls.id) : []
  const parents = cls ? mine.filter((rel) => rel.sourceClassId === cls.id && rel.type === 'inheritance') : []
  const inherited = parents.flatMap((rel) => {
    const parent = model.classes.find((item) => item.id === rel.targetClassId)
    return parent
      ? [...parent.attributes.map((attr) => `${attr.name}: ${attr.type}`), ...parent.methods.map((method) => `${method.name}()`)].map((member) => ({
          member,
          from: parent.name,
        }))
      : []
  })
  const children = cls ? mine.filter((rel) => rel.targetClassId === cls.id && (rel.type === 'inheritance' || rel.type === 'realization')) : []

  return (
    <aside className="absolute bottom-3 right-3 top-3 z-20 flex w-80 max-w-[calc(100%-1.5rem)] flex-col overflow-hidden rounded-xl border border-border-strong bg-surface shadow-xl">
      <div className="flex items-start justify-between gap-2 border-b border-border bg-gradient-to-br from-accent/10 to-accent2/10 px-4 py-3">
        <div>
          <Chip tone={stereotype === 'interface' ? 'ai' : stereotype === 'abstract' ? 'warning' : stereotype === 'enumeration' ? 'sky' : 'accent'}>
            {guide.label}
          </Chip>
          <h3 className={cn('mt-1 font-display text-lg font-bold text-fg', stereotype === 'abstract' && 'italic')}>{cls?.name ?? enumName}</h3>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
          <X />
        </Button>
      </div>
      <div className="grid grid-cols-1 gap-4 overflow-y-auto px-4 py-3 text-[12.5px]">
        <p className="text-fg-2">{guide.meaning}</p>

        {enumLiterals ? (
          <section>
            <h4 className="mb-1 text-[10.5px] font-bold uppercase tracking-[0.1em] text-fg-3">Allowed values</h4>
            <div className="flex flex-wrap gap-1">
              {enumLiterals.map((literal) => (
                <span key={literal} className="rounded-md bg-sky/10 px-1.5 py-0.5 font-mono text-[11px] text-fg-2">
                  {literal}
                </span>
              ))}
            </div>
          </section>
        ) : null}

        {cls && children.length ? (
          <section>
            <h4 className="mb-1 text-[10.5px] font-bold uppercase tracking-[0.1em] text-fg-3">
              {stereotype === 'interface' ? 'Implemented by' : 'Specialised by'}
            </h4>
            <p className="text-fg-2">{children.map((rel) => rel.source).join(', ')}</p>
          </section>
        ) : null}

        {inherited.length ? (
          <section>
            <h4 className="mb-1 text-[10.5px] font-bold uppercase tracking-[0.1em] text-fg-3">Inherited (not redeclared)</h4>
            <ul className="grid grid-cols-1 gap-0.5 font-mono text-[11px] text-fg-3">
              {inherited.map((item) => (
                <li key={`${item.from}-${item.member}`}>
                  {item.member} <span className="font-sans text-[10.5px]">← {item.from}</span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {cls ? (
          <section>
            <h4 className="mb-1 text-[10.5px] font-bold uppercase tracking-[0.1em] text-fg-3">Own members</h4>
            <p className="text-fg-2">
              {cls.attributes.length} attribute{cls.attributes.length === 1 ? '' : 's'} · {cls.methods.length} method
              {cls.methods.length === 1 ? '' : 's'}
            </p>
          </section>
        ) : null}

        {mine.length ? (
          <section>
            <h4 className="mb-1.5 text-[10.5px] font-bold uppercase tracking-[0.1em] text-fg-3">Relationships</h4>
            <ul className="grid grid-cols-1 gap-2">
              {mine.map((rel) => {
                const { headline, detail } = explainRelationship(rel, model.classes)
                return (
                  <li key={rel.id} className="rounded-lg border border-border bg-surface-2 px-2.5 py-2">
                    <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-accent">{relationshipGuide[rel.type].title}</div>
                    <div className="font-semibold text-fg">{headline}</div>
                    {detail ? <div className="mt-0.5 text-[11.5px] text-fg-3">{detail}</div> : null}
                  </li>
                )
              })}
            </ul>
          </section>
        ) : null}
      </div>
    </aside>
  )
}
