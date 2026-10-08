/** draw.io XML back into the class model the interactive canvas draws.
 *
 * A saved diagram stores only `drawio_xml`, so the interactive view has to read
 * the model out of it. The shape is the one the backend writes in
 * `app/rule_engine/pipeline.py::generate_drawio_xml`:
 *
 * - a class is a `swimlane` vertex whose value is the header (`«interface» Book`)
 * - its rows live in two child text vertices, `<id>_attributes` and `<id>_methods`,
 *   with the rows joined by `<br>`
 * - a relationship is an edge whose type is recoverable from its arrow style, and
 *   whose multiplicities are child `edgeLabel` vertices
 *
 * Diagrams edited by hand in diagrams.net drift from that, so every step falls
 * back to something reasonable rather than giving up: a row is a method when it
 * has parentheses and an attribute otherwise, and row blocks are found by
 * position once the generator's ids are gone. Parsing is best-effort by design -
 * `skipped` reports the vertices that could not be read as boxes, so the UI can
 * say the drawing holds more than the model shows.
 */
import type {
  ClassModelerResult,
  ModelAttribute,
  ModelClass,
  ModelEnum,
  ModelMethod,
  ModelParameter,
  ModelRelationship,
} from '../../api'

type ClassModel = ClassModelerResult['model']

export type DrawioParseResult = {
  model: ClassModel
  /** Vertices that are not class or enum boxes (notes, shapes, free text). */
  skipped: number
}

const ATTRIBUTE_VISIBILITY: Record<string, string> = { '+': 'public', '-': 'private', '#': 'protected', '~': 'package' }
const BREAK = /<br\s*\/?>/i
// "- title: String" / "title: String" / "title"
const ATTRIBUTE_ROW = /^([+\-#~])?\s*([^:()]+?)\s*(?::\s*(.*))?$/
// "+ borrow(book: Book): void"
const METHOD_ROW = /^([+\-#~])?\s*([^\s(]+)\s*\(([^)]*)\)\s*(?::\s*(.*))?$/
// "«interface» Book", and the plain-text "<<interface>> Book" diagrams.net writes
const STEREOTYPE_ROW = /^(?:«\s*([A-Za-z]+)\s*»|<<\s*([A-Za-z]+)\s*>>)\s*/

function attributeOf(element: Element | undefined, name: string): string {
  return element?.getAttribute(name) ?? ''
}

/** One level of HTML unescaping, plus markup stripping for hand-edited labels.
 *
 * A value is escaped twice on the way out (for HTML by the generator, then for
 * XML by the writer) and the XML parser undoes the outer layer, so exactly one
 * pass is left to do here. `&amp;` goes last so a legitimately escaped entity
 * such as `&amp;lt;` decodes to `&lt;` and no further. */
function decodeText(value: string): string {
  return value
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&(?:apos|#0?39);/gi, "'")
    .replace(/&amp;/gi, '&')
    .replace(/\s+/g, ' ')
    .trim()
}

/** The rows of a stacked text cell. Split before decoding, so an escaped
 * `&lt;br&gt;` inside a name is never mistaken for a row separator. */
function textRows(value: string): string[] {
  return value.split(BREAK).map(decodeText).filter(Boolean)
}

function parseHeader(value: string): { name: string; stereotype: string } {
  const text = decodeText(value.split(BREAK)[0] ?? '')
  const match = STEREOTYPE_ROW.exec(text)
  if (!match) return { name: text, stereotype: 'entity' }
  return { name: text.slice(match[0].length).trim(), stereotype: (match[1] ?? match[2] ?? '').toLowerCase() }
}

/** Split a parameter list on the commas that separate parameters, not the ones
 * inside a generic type - `Map<String, Int> q` is one parameter, not two. */
function splitParameters(raw: string): string[] {
  const parts: string[] = []
  let depth = 0
  let current = ''
  for (const character of raw) {
    if (character === '<' || character === '(' || character === '[') depth += 1
    else if (character === '>' || character === ')' || character === ']') depth = Math.max(0, depth - 1)
    if (character === ',' && depth === 0) {
      parts.push(current)
      current = ''
      continue
    }
    current += character
  }
  parts.push(current)
  return parts.map((part) => part.trim()).filter(Boolean)
}

function parseParameters(raw: string): ModelParameter[] {
  return splitParameters(raw).map((part) => {
    const separator = part.indexOf(':')
    if (separator === -1) return { name: part, type: 'String' }
    return { name: part.slice(0, separator).trim(), type: part.slice(separator + 1).trim() || 'String' }
  })
}

function parseAttribute(id: string, row: string): ModelAttribute {
  const [, visibility, name, type] = ATTRIBUTE_ROW.exec(row) ?? []
  return {
    id,
    name: (name ?? row).trim(),
    type: (type ?? '').trim() || 'String',
    visibility: ATTRIBUTE_VISIBILITY[visibility ?? ''] ?? 'private',
  }
}

function parseMethod(id: string, row: string): ModelMethod | null {
  const match = METHOD_ROW.exec(row)
  if (!match) return null
  const [, visibility, name, parameters, returnType] = match
  return {
    id,
    name: name.trim(),
    parameters: parseParameters(parameters ?? ''),
    returnType: (returnType ?? '').trim() || 'void',
    visibility: ATTRIBUTE_VISIBILITY[visibility ?? ''] ?? 'public',
  }
}

/** The UML relationship an edge's arrow style encodes - the inverse of
 * `relationship_drawio_style` in the rule engine. */
function parseRelationshipType(style: string): ModelRelationship['type'] {
  const lowered = style.toLowerCase()
  const dashed = /dashed=1/.test(lowered)
  if (/startarrow=diamondthin/.test(lowered)) return /startfill=1/.test(lowered) ? 'composition' : 'aggregation'
  if (/endarrow=block/.test(lowered)) return dashed ? 'realization' : 'inheritance'
  if (dashed) return 'dependency'
  return 'association'
}

// Shapes that are never a class, so a flowchart does not read as a thin model.
const NON_CLASS_SHAPE = /\b(?:ellipse|rhombus|triangle|hexagon|cylinder|cloud|actor|umlActor|note|parallelogram|step|card|document|process|line|image)\b|mxgraph\./i

/** The generator always writes swimlanes, and so does the UML class shape in
 * diagrams.net - that covers both generated and hand-built class diagrams.
 *
 * A plain rectangle is accepted too, but only when it carries members under its
 * name: a lone labelled box ("Start") says nothing about a class model, and
 * reading it as one would turn every flowchart into a one-class diagram. */
function isClassBox(style: string, value: string): boolean {
  if (/\bswimlane\b/i.test(style)) return true
  if (!value.trim() || /\b(?:text|edgeLabel)\b/i.test(style) || NON_CLASS_SHAPE.test(style)) return false
  return value.split(BREAK).length > 1
}

export function parseDrawioClassModel(xml: string): DrawioParseResult | null {
  if (!xml.trim()) return null
  let parsed: Document
  try {
    parsed = new DOMParser().parseFromString(xml, 'application/xml')
  } catch {
    return null
  }
  if (parsed.getElementsByTagName('parsererror').length) return null

  const cells = Array.from(parsed.getElementsByTagName('mxCell'))
  if (!cells.length) return null

  const childrenOf = new Map<string, Element[]>()
  for (const cell of cells) {
    const parent = attributeOf(cell, 'parent')
    if (!parent) continue
    const siblings = childrenOf.get(parent)
    if (siblings) siblings.push(cell)
    else childrenOf.set(parent, [cell])
  }

  const classes: ModelClass[] = []
  const enums: ModelEnum[] = []
  const nameById = new Map<string, string>()
  let skipped = 0

  for (const cell of cells) {
    const id = attributeOf(cell, 'id')
    if (!id || attributeOf(cell, 'vertex') !== '1') continue
    // A row block and a multiplicity label are parts of their parent, not boxes.
    const parent = attributeOf(cell, 'parent')
    if (parent && parent !== '0' && parent !== '1') continue

    const style = attributeOf(cell, 'style')
    const value = attributeOf(cell, 'value')
    const { name, stereotype } = isClassBox(style, value) ? parseHeader(value) : { name: '', stereotype: '' }
    if (!name) {
      skipped += 1
      continue
    }

    const sections = childrenOf.get(id) ?? []
    const stacked = sections.filter((child) => /\btext\b/i.test(attributeOf(child, 'style')))
    const rowsOf = (suffix: string, fallbackIndex: number) => {
      const byId = sections.find((child) => attributeOf(child, 'id') === `${id}_${suffix}`)
      return textRows(attributeOf(byId ?? stacked[fallbackIndex], 'value'))
    }
    const attributeRows = rowsOf('attributes', 0)
    const methodRows = rowsOf('methods', 1)

    nameById.set(id, name)
    if (stereotype === 'enumeration') {
      enums.push({ id, name, literals: attributeRows.map((row) => row.replace(/^[+\-#~]\s*/, '')) })
      continue
    }

    const attributes: ModelAttribute[] = []
    const methods: ModelMethod[] = []
    // A box whose rows were never split into sections lists both kinds together;
    // parentheses are what separate an operation from a field.
    for (const [index, row] of [...attributeRows, ...methodRows].entries()) {
      const method = row.includes('(') ? parseMethod(`${id}_m${index}`, row) : null
      if (method) methods.push(method)
      else attributes.push(parseAttribute(`${id}_a${index}`, row))
    }
    classes.push({ id, name, stereotype, attributes, methods, sourceSentences: [] })
  }

  const boxIds = new Set([...classes.map((cls) => cls.id), ...enums.map((item) => item.id)])
  const relationships: ModelRelationship[] = []

  for (const cell of cells) {
    if (attributeOf(cell, 'edge') !== '1') continue
    const id = attributeOf(cell, 'id')
    const sourceClassId = attributeOf(cell, 'source')
    const targetClassId = attributeOf(cell, 'target')
    // The canvas only draws edges between boxes it has, so an edge left dangling
    // by a delete in diagrams.net is dropped here rather than silently later.
    if (!boxIds.has(sourceClassId) || !boxIds.has(targetClassId)) continue

    const labels = childrenOf.get(id) ?? []
    const geometryX = (label: Element) => Number(attributeOf(label.getElementsByTagName('mxGeometry')[0], 'x') || '0')
    const multiplicity = (suffix: string, side: 'source' | 'target') => {
      const byId = labels.find((label) => attributeOf(label, 'id') === `${id}_${suffix}`)
      if (byId) return decodeText(attributeOf(byId, 'value')) || null
      // Hand-placed labels have their own ids. The generator puts the source
      // multiplicity at a negative offset along the edge and the target at a
      // positive one, which diagrams.net keeps when the label is dragged.
      const positioned = labels.find(
        (label) =>
          /edgeLabel/i.test(attributeOf(label, 'style')) && (side === 'source' ? geometryX(label) < 0 : geometryX(label) > 0),
      )
      return positioned ? decodeText(attributeOf(positioned, 'value')) || null : null
    }

    relationships.push({
      id,
      sourceClassId,
      targetClassId,
      source: nameById.get(sourceClassId) ?? '',
      target: nameById.get(targetClassId) ?? '',
      type: parseRelationshipType(attributeOf(cell, 'style')),
      label: decodeText(attributeOf(cell, 'value')),
      sourceMultiplicity: multiplicity('source_multiplicity', 'source'),
      targetMultiplicity: multiplicity('target_multiplicity', 'target'),
      multiplicityAssumed: false,
    })
  }

  if (!classes.length && !enums.length) return null
  return { model: { classes, relationships, enums }, skipped }
}

/** A cheap identity for a parsed model, so a draw.io edit that only moves a box
 * does not hand the canvas a new object and reset its layout. */
export function classModelSignature(model: ClassModel): string {
  return JSON.stringify([
    model.classes.map((cls) => [
      cls.id,
      cls.name,
      cls.stereotype,
      cls.attributes.map((attr) => [attr.name, attr.type, attr.visibility]),
      cls.methods.map((method) => [
        method.name,
        method.returnType,
        method.visibility,
        method.parameters.map((parameter) => [parameter.name, parameter.type]),
      ]),
    ]),
    model.relationships.map((rel) => [
      rel.id,
      rel.sourceClassId,
      rel.targetClassId,
      rel.type,
      rel.label,
      rel.sourceMultiplicity,
      rel.targetMultiplicity,
    ]),
    model.enums.map((item) => [item.id, item.name, item.literals]),
  ])
}
