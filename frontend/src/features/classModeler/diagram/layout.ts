import type { ModelClass, ModelEnum, ModelRelationship } from '../../../api'

export type LayoutBox = { id: string; width: number; height: number }
export type Point = { x: number; y: number }

const CHAR_WIDTH = 7.2
const ROW_HEIGHT = 20
const HEADER_HEIGHT = 44
const SECTION_PADDING = 12
const MIN_WIDTH = 170
const LAYER_GAP = 110
const NODE_GAP = 70

export function methodSignature(method: ModelClass['methods'][number]) {
  const params = method.parameters.map((param) => `${param.name}: ${param.type}`).join(', ')
  return `${method.name}(${params}): ${method.returnType}`
}

/** Size a UML box from its text before React Flow has measured it. */
export function estimateClassBox(cls: ModelClass): LayoutBox {
  const lines = [
    cls.name,
    ...cls.attributes.map((attr) => `- ${attr.name}: ${attr.type}`),
    ...cls.methods.map((method) => `+ ${methodSignature(method)}`),
  ]
  const longest = Math.max(...lines.map((line) => line.length))
  const rows = Math.max(cls.attributes.length, 1) + Math.max(cls.methods.length, 1)
  return {
    id: cls.id,
    width: Math.max(MIN_WIDTH, Math.round(longest * CHAR_WIDTH + 36)),
    height: HEADER_HEIGHT + rows * ROW_HEIGHT + SECTION_PADDING * 2,
  }
}

export function estimateEnumBox(item: ModelEnum): LayoutBox {
  const longest = Math.max(item.name.length, ...item.literals.map((literal) => literal.length))
  return {
    id: item.id,
    width: Math.max(MIN_WIDTH - 20, Math.round(longest * CHAR_WIDTH + 36)),
    height: HEADER_HEIGHT + Math.max(item.literals.length, 1) * ROW_HEIGHT + SECTION_PADDING,
  }
}

/**
 * "u is drawn above v". Parents sit above their children, the whole above
 * its parts, and an association reads top-down from its source.
 */
function aboveEdges(relationships: ModelRelationship[]): [string, string][] {
  return relationships.map((rel) =>
    rel.type === 'inheritance' || rel.type === 'realization'
      ? [rel.targetClassId, rel.sourceClassId]
      : [rel.sourceClassId, rel.targetClassId],
  )
}

/**
 * Layered (Sugiyama-style) layout: break cycles, assign each box to the
 * longest-path layer, order each layer by the barycenter of its neighbours,
 * then centre every layer under the widest one.
 */
export function layoutDiagram(
  boxes: LayoutBox[],
  relationships: ModelRelationship[],
  extraEdges: [string, string][] = [],
): Record<string, Point> {
  const ids = boxes.map((box) => box.id)
  const known = new Set(ids)
  const edges = [...aboveEdges(relationships), ...extraEdges].filter(
    ([from, to]) => from !== to && known.has(from) && known.has(to),
  )

  // 1. Drop back edges found by DFS so the graph is acyclic.
  const out = new Map<string, string[]>(ids.map((id) => [id, []]))
  for (const [from, to] of edges) out.get(from)!.push(to)
  const state = new Map<string, 'visiting' | 'done'>()
  const dag: [string, string][] = []
  const visit = (id: string) => {
    state.set(id, 'visiting')
    for (const next of out.get(id)!) {
      if (state.get(next) === 'visiting') continue
      dag.push([id, next])
      if (!state.has(next)) visit(next)
    }
    state.set(id, 'done')
  }
  const indegree = new Map<string, number>(ids.map((id) => [id, 0]))
  for (const [, to] of edges) indegree.set(to, (indegree.get(to) ?? 0) + 1)
  for (const id of [...ids].sort((a, b) => (indegree.get(a) ?? 0) - (indegree.get(b) ?? 0))) {
    if (!state.has(id)) visit(id)
  }

  // 2. Longest-path layering.
  const layerOf = new Map<string, number>(ids.map((id) => [id, 0]))
  for (let pass = 0; pass < ids.length; pass += 1) {
    let changed = false
    for (const [from, to] of dag) {
      const wanted = layerOf.get(from)! + 1
      if (layerOf.get(to)! < wanted) {
        layerOf.set(to, wanted)
        changed = true
      }
    }
    if (!changed) break
  }
  const layerCount = Math.max(0, ...layerOf.values()) + 1
  let layers: string[][] = Array.from({ length: layerCount }, () => [])
  for (const id of ids) layers[layerOf.get(id)!].push(id)

  // A very wide layer of unrelated boxes wraps onto extra rows.
  const MAX_PER_ROW = 5
  layers = layers.flatMap((layer) => {
    if (layer.length <= MAX_PER_ROW) return [layer]
    const rows: string[][] = []
    for (let index = 0; index < layer.length; index += MAX_PER_ROW) rows.push(layer.slice(index, index + MAX_PER_ROW))
    return rows
  })

  // 3. Barycenter ordering, sweeping down and up a few times.
  const neighbours = new Map<string, string[]>(ids.map((id) => [id, []]))
  for (const [from, to] of edges) {
    neighbours.get(from)!.push(to)
    neighbours.get(to)!.push(from)
  }
  const position = new Map<string, number>()
  layers.forEach((layer) => layer.forEach((id, index) => position.set(id, index)))
  for (let sweep = 0; sweep < 6; sweep += 1) {
    const order = sweep % 2 === 0 ? layers : [...layers].reverse()
    for (const layer of order) {
      const score = (id: string) => {
        const around = neighbours.get(id)!.filter((other) => position.has(other))
        if (!around.length) return position.get(id)!
        return around.reduce((sum, other) => sum + position.get(other)!, 0) / around.length
      }
      layer.sort((a, b) => score(a) - score(b))
      layer.forEach((id, index) => position.set(id, index))
    }
  }

  // 4. Coordinates.
  const size = new Map(boxes.map((box) => [box.id, box]))
  const widths = layers.map((layer) => layer.reduce((sum, id) => sum + size.get(id)!.width, 0) + NODE_GAP * (layer.length - 1))
  const widest = Math.max(0, ...widths)
  const result: Record<string, Point> = {}
  let y = 0
  layers.forEach((layer, layerIndex) => {
    let x = (widest - widths[layerIndex]) / 2
    const rowHeight = Math.max(0, ...layer.map((id) => size.get(id)!.height))
    for (const id of layer) {
      result[id] = { x, y }
      x += size.get(id)!.width + NODE_GAP
    }
    y += rowHeight + LAYER_GAP
  })
  return result
}
