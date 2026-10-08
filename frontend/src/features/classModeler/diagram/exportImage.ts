import type { ClassModelerResult, ModelClass, ModelEnum } from '../../../api'
import { methodSignature } from './layout'

/**
 * Standalone image export of the diagram as currently arranged on the canvas.
 * A downloaded SVG/PNG cannot use the app's Tailwind classes, so the image
 * carries its own presentation attributes; colours mirror the theme tokens.
 */

export type PlacedNode = { id: string; x: number; y: number; width: number; height: number }

const color = {
  fg: '#0d1117',
  fg2: '#4a5568',
  fg3: '#8896aa',
  line: '#5b6678',
  border: '#d6dbe4',
  surface: '#ffffff',
  canvas: '#f7f9fd',
  accent: '#4f46e5',
  accentSoft: '#e0e7ff',
  accent2: '#7c3aed',
  accent2Soft: '#ede9fe',
  warningSoft: '#fdf1d3',
  warning: '#d4a015',
  skySoft: '#dcf2fd',
  sky: '#1f9fd6',
}
const SANS = "Poppins, 'Segoe UI', Arial, sans-serif"
const MONO = "'Fira Code', Consolas, monospace"

const esc = (value: string) =>
  value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

function centre(node: PlacedNode) {
  return { x: node.x + node.width / 2, y: node.y + node.height / 2 }
}

function borderPoint(node: PlacedNode, toward: { x: number; y: number }) {
  const c = centre(node)
  const dx = toward.x - c.x
  const dy = toward.y - c.y
  if (!dx && !dy) return c
  const scale = 1 / Math.max(Math.abs(dx) / (node.width / 2 + 2), Math.abs(dy) / (node.height / 2 + 2))
  return { x: c.x + dx * scale, y: c.y + dy * scale }
}

function classBox(cls: ModelClass, node: PlacedNode, parents: string[]) {
  const stereotype = cls.stereotype === 'interface' || cls.stereotype === 'abstract' ? cls.stereotype : 'entity'
  const head = { entity: color.accentSoft, abstract: color.warningSoft, interface: color.accent2Soft }[stereotype]
  const edge = { entity: color.accent, abstract: color.warning, interface: color.accent2 }[stereotype]
  const parts: string[] = []
  const { x, y, width } = node
  let cursor = y + 18
  const headerLines = (stereotype !== 'entity' ? 1 : 0) + 1 + (parents.length ? 1 : 0)
  const headerHeight = 12 + headerLines * 16
  parts.push(
    `<rect x="${x}" y="${y}" width="${width}" height="${node.height}" rx="10" fill="${color.surface}" stroke="${edge}" stroke-width="1.5"${
      stereotype === 'interface' ? ' stroke-dasharray="6 4"' : ''
    }/>`,
    `<path d="M ${x + 1} ${y + headerHeight} V ${y + 10} Q ${x + 1} ${y + 1} ${x + 10} ${y + 1} H ${x + width - 10} Q ${x + width - 1} ${y + 1} ${
      x + width - 1
    } ${y + 10} V ${y + headerHeight} Z" fill="${head}"/>`,
  )
  if (stereotype !== 'entity') {
    parts.push(`<text x="${x + width / 2}" y="${cursor}" text-anchor="middle" font-family="${SANS}" font-size="10" fill="${color.fg2}">«${stereotype}»</text>`)
    cursor += 16
  }
  parts.push(
    `<text x="${x + width / 2}" y="${cursor}" text-anchor="middle" font-family="${SANS}" font-size="14" font-weight="700"${
      stereotype === 'abstract' ? ' font-style="italic"' : ''
    } fill="${color.fg}">${esc(cls.name)}</text>`,
  )
  cursor += 16
  if (parents.length) {
    parts.push(`<text x="${x + width / 2}" y="${cursor}" text-anchor="middle" font-family="${SANS}" font-size="10" fill="${color.fg2}">${esc(parents.join(' · '))}</text>`)
  }
  let rowY = y + headerHeight
  parts.push(`<line x1="${x}" y1="${rowY}" x2="${x + width}" y2="${rowY}" stroke="${color.border}"/>`)
  rowY += 6
  const attributes = cls.attributes.length ? cls.attributes.map((attr) => `- ${attr.name}: ${attr.type}`) : [' ']
  for (const line of attributes) {
    rowY += 16
    parts.push(`<text x="${x + 12}" y="${rowY}" font-family="${MONO}" font-size="11.5" fill="${color.fg2}">${esc(line)}</text>`)
  }
  rowY += 10
  parts.push(`<line x1="${x}" y1="${rowY}" x2="${x + width}" y2="${rowY}" stroke="${color.border}"/>`)
  rowY += 6
  const methods = cls.methods.length ? cls.methods.map((method) => `+ ${methodSignature(method)}`) : [' ']
  for (const line of methods) {
    rowY += 16
    parts.push(`<text x="${x + 12}" y="${rowY}" font-family="${MONO}" font-size="11.5" fill="${color.fg}">${esc(line)}</text>`)
  }
  return parts.join('')
}

function enumBox(item: ModelEnum, node: PlacedNode) {
  const { x, y, width } = node
  const parts = [
    `<rect x="${x}" y="${y}" width="${width}" height="${node.height}" rx="10" fill="${color.surface}" stroke="${color.sky}" stroke-width="1.5"/>`,
    `<path d="M ${x + 1} ${y + 44} V ${y + 10} Q ${x + 1} ${y + 1} ${x + 10} ${y + 1} H ${x + width - 10} Q ${x + width - 1} ${y + 1} ${x + width - 1} ${y + 10} V ${y + 44} Z" fill="${color.skySoft}"/>`,
    `<text x="${x + width / 2}" y="${y + 18}" text-anchor="middle" font-family="${SANS}" font-size="10" fill="${color.fg2}">«enumeration»</text>`,
    `<text x="${x + width / 2}" y="${y + 35}" text-anchor="middle" font-family="${SANS}" font-size="14" font-weight="700" fill="${color.fg}">${esc(item.name)}</text>`,
    `<line x1="${x}" y1="${y + 44}" x2="${x + width}" y2="${y + 44}" stroke="${color.border}"/>`,
  ]
  item.literals.forEach((literal, index) => {
    parts.push(`<text x="${x + 12}" y="${y + 64 + index * 18}" font-family="${MONO}" font-size="11.5" fill="${color.fg2}">${esc(literal)}</text>`)
  })
  return parts.join('')
}

export function buildDiagramSvg(model: ClassModelerResult['model'], placed: PlacedNode[]): { svg: string; width: number; height: number } {
  const byId = new Map(placed.map((node) => [node.id, node]))
  const pad = 48
  const minX = Math.min(...placed.map((node) => node.x)) - pad
  const minY = Math.min(...placed.map((node) => node.y)) - pad
  const maxX = Math.max(...placed.map((node) => node.x + node.width)) + pad + 90
  const maxY = Math.max(...placed.map((node) => node.y + node.height)) + pad
  const width = Math.ceil(maxX - minX)
  const height = Math.ceil(maxY - minY)

  const edges: string[] = []
  const labels: string[] = []
  const label = (x: number, y: number, text: string, mono = false) => {
    const w = text.length * (mono ? 7 : 6.2) + 10
    labels.push(
      `<rect x="${x - w / 2}" y="${y - 9}" width="${w}" height="17" rx="8" fill="${color.surface}" stroke="${mono ? 'none' : color.border}"/>`,
      `<text x="${x}" y="${y + 4}" text-anchor="middle" font-family="${mono ? MONO : SANS}" font-size="10.5" font-weight="600" fill="${color.fg2}">${esc(text)}</text>`,
    )
  }
  const along = (from: { x: number; y: number }, to: { x: number; y: number }, distance: number) => {
    const dx = to.x - from.x
    const dy = to.y - from.y
    const length = Math.hypot(dx, dy) || 1
    return { x: from.x + (dx / length) * distance, y: from.y + (dy / length) * distance }
  }

  for (const rel of model.relationships) {
    const source = byId.get(rel.sourceClassId)
    const target = byId.get(rel.targetClassId)
    if (!source || !target) continue
    const dashed = rel.type === 'realization' || rel.type === 'dependency'
    const markerStart = rel.type === 'composition' ? 'url(#diamond-filled)' : rel.type === 'aggregation' ? 'url(#diamond-open)' : ''
    const markerEnd =
      rel.type === 'inheritance' || rel.type === 'realization'
        ? 'url(#triangle)'
        : rel.type === 'association' || rel.type === 'dependency'
          ? 'url(#arrow)'
          : ''
    let d: string
    let mid: { x: number; y: number }
    let start: { x: number; y: number }
    let end: { x: number; y: number }
    if (source.id === target.id) {
      start = { x: source.x + source.width, y: source.y + source.height * 0.3 }
      end = { x: source.x + source.width, y: source.y + source.height * 0.7 }
      d = `M ${start.x} ${start.y} C ${start.x + 90} ${start.y - 30}, ${end.x + 90} ${end.y + 30}, ${end.x} ${end.y}`
      mid = { x: start.x + 72, y: source.y + source.height / 2 }
    } else {
      start = borderPoint(source, centre(target))
      end = borderPoint(target, centre(source))
      d = `M ${start.x} ${start.y} L ${end.x} ${end.y}`
      mid = { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 }
    }
    edges.push(
      `<path d="${d}" fill="none" stroke="${color.line}" stroke-width="1.4"${dashed ? ' stroke-dasharray="6 4"' : ''}${
        markerStart ? ` marker-start="${markerStart}"` : ''
      }${markerEnd ? ` marker-end="${markerEnd}"` : ''}/>`,
    )
    if (rel.label && rel.type !== 'inheritance' && rel.type !== 'realization') label(mid.x, mid.y, rel.label)
    if (rel.sourceMultiplicity) {
      const at = along(start, end, 22)
      label(at.x, at.y, rel.sourceMultiplicity, true)
    }
    if (rel.targetMultiplicity) {
      const at = along(end, start, 22)
      label(at.x, at.y, rel.targetMultiplicity, true)
    }
  }

  // Dashed link from the owning class to each enumeration it uses as a type.
  for (const item of model.enums) {
    const owner = model.classes.find((cls) => cls.attributes.some((attr) => attr.type === item.name))
    const from = owner ? byId.get(owner.id) : undefined
    const to = byId.get(item.id)
    if (!from || !to) continue
    const start = borderPoint(from, centre(to))
    const end = borderPoint(to, centre(from))
    edges.push(`<path d="M ${start.x} ${start.y} L ${end.x} ${end.y}" fill="none" stroke="${color.line}" stroke-width="1.4" stroke-dasharray="6 4" marker-end="url(#arrow)"/>`)
  }

  const boxes = [
    ...model.classes.map((cls) => {
      const node = byId.get(cls.id)
      if (!node) return ''
      const parents = model.relationships
        .filter((rel) => rel.sourceClassId === cls.id && (rel.type === 'inheritance' || rel.type === 'realization'))
        .map((rel) => `${rel.type === 'inheritance' ? 'extends' : 'implements'} ${rel.target}`)
      return classBox(cls, node, parents)
    }),
    ...model.enums.map((item) => {
      const node = byId.get(item.id)
      return node ? enumBox(item, node) : ''
    }),
  ]

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="${minX} ${minY} ${width} ${height}">
<defs>
<marker id="triangle" viewBox="0 0 20 20" refX="19" refY="10" markerWidth="18" markerHeight="18" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M 1 1 L 19 10 L 1 19 z" fill="${color.surface}" stroke="${color.fg2}" stroke-width="1.5"/></marker>
<marker id="diamond-filled" viewBox="0 0 24 14" refX="1" refY="7" markerWidth="24" markerHeight="14" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M 1 7 L 12 1 L 23 7 L 12 13 z" fill="${color.fg2}" stroke="${color.fg2}"/></marker>
<marker id="diamond-open" viewBox="0 0 24 14" refX="1" refY="7" markerWidth="24" markerHeight="14" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M 1 7 L 12 1 L 23 7 L 12 13 z" fill="${color.surface}" stroke="${color.fg2}"/></marker>
<marker id="arrow" viewBox="0 0 16 16" refX="15" refY="8" markerWidth="14" markerHeight="14" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M 1 1 L 15 8 L 1 15" fill="none" stroke="${color.fg2}" stroke-width="1.5"/></marker>
</defs>
<rect x="${minX}" y="${minY}" width="${width}" height="${height}" fill="${color.canvas}"/>
${edges.join('\n')}
${boxes.join('\n')}
${labels.join('\n')}
</svg>`
  return { svg, width, height }
}

/** Rasterise the SVG at 2x for a crisp PNG data URL. */
export function svgToPng(svg: string, width: number, height: number, scale = 2): Promise<string> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml;charset=utf-8' }))
    image.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = Math.ceil(width * scale)
      canvas.height = Math.ceil(height * scale)
      const context = canvas.getContext('2d')
      if (!context) {
        URL.revokeObjectURL(url)
        reject(new Error('Canvas is not available in this browser'))
        return
      }
      context.scale(scale, scale)
      context.drawImage(image, 0, 0, width, height)
      URL.revokeObjectURL(url)
      resolve(canvas.toDataURL('image/png'))
    }
    image.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('Could not render the diagram image'))
    }
    image.src = url
  })
}
