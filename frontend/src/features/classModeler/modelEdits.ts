/** Edits to a class model, as pure functions.
 *
 * Every surface that can change the model - the Classes editor, and draw.io
 * through the parser - goes through one of these, so the invariants the canvas
 * and the XML generator rely on hold in one place rather than at each call site:
 *
 * - ids are unique, and stable across unrelated edits so the canvas keeps its
 *   arrangement when something else changes
 * - a relationship carries the *names* of its ends as well as their ids, so
 *   renaming a class has to update every edge that touches it
 * - deleting a class deletes the edges that would otherwise dangle
 */
import type {
  ClassModelerResult,
  ModelAttribute,
  ModelClass,
  ModelEnum,
  ModelMethod,
  ModelRelationship,
} from '../../api'

export type ClassModel = ClassModelerResult['model']

export const STEREOTYPES = ['entity', 'abstract', 'interface'] as const
export const VISIBILITIES = ['public', 'private', 'protected', 'package'] as const
export const RELATIONSHIP_TYPES: ModelRelationship['type'][] = [
  'association',
  'aggregation',
  'composition',
  'inheritance',
  'realization',
  'dependency',
]

let sequence = 0

/** A fresh id that cannot collide with a generated one or with another edit in
 * the same millisecond. */
function newId(prefix: string): string {
  sequence += 1
  return `${prefix}_${Date.now().toString(36)}${sequence.toString(36)}`
}

function uniqueName(base: string, taken: string[]): string {
  if (!taken.includes(base)) return base
  for (let suffix = 2; ; suffix += 1) {
    const candidate = `${base}${suffix}`
    if (!taken.includes(candidate)) return candidate
  }
}

/** Relationship ends carry both the id and the name; the name is what the
 * canvas, the legend and the plain-words explanations read. */
function withNames(model: ClassModel): ClassModel {
  const names = new Map<string, string>([
    ...model.classes.map((cls) => [cls.id, cls.name] as const),
    ...model.enums.map((item) => [item.id, item.name] as const),
  ])
  return {
    ...model,
    relationships: model.relationships.map((rel) => ({
      ...rel,
      source: names.get(rel.sourceClassId) ?? rel.source,
      target: names.get(rel.targetClassId) ?? rel.target,
    })),
  }
}

// ---------------------------------------------------------------- classes ---

export function addClass(model: ClassModel, stereotype: string = 'entity'): ClassModel {
  const name = uniqueName('NewClass', [...model.classes.map((cls) => cls.name), ...model.enums.map((item) => item.name)])
  const cls: ModelClass = { id: newId('cls'), name, stereotype, attributes: [], methods: [], sourceSentences: [] }
  return { ...model, classes: [...model.classes, cls] }
}

export function updateClass(model: ClassModel, classId: string, patch: Partial<ModelClass>): ClassModel {
  return withNames({
    ...model,
    classes: model.classes.map((cls) => (cls.id === classId ? { ...cls, ...patch } : cls)),
  })
}

export function removeClass(model: ClassModel, classId: string): ClassModel {
  return {
    ...model,
    classes: model.classes.filter((cls) => cls.id !== classId),
    // An edge with only one end left would be dropped by the canvas and the XML
    // generator anyway; remove it here so what the user sees is what is stored.
    relationships: model.relationships.filter((rel) => rel.sourceClassId !== classId && rel.targetClassId !== classId),
  }
}

// ------------------------------------------------------------- attributes ---

export function addAttribute(model: ClassModel, classId: string): ClassModel {
  const owner = model.classes.find((cls) => cls.id === classId)
  if (!owner) return model
  const attribute: ModelAttribute = {
    id: newId('attr'),
    name: uniqueName('newAttribute', owner.attributes.map((item) => item.name)),
    type: 'String',
    visibility: 'private',
  }
  return updateClass(model, classId, { attributes: [...owner.attributes, attribute] })
}

export function updateAttribute(
  model: ClassModel,
  classId: string,
  attributeId: string,
  patch: Partial<ModelAttribute>,
): ClassModel {
  const owner = model.classes.find((cls) => cls.id === classId)
  if (!owner) return model
  return updateClass(model, classId, {
    attributes: owner.attributes.map((item) => (item.id === attributeId ? { ...item, ...patch } : item)),
  })
}

export function removeAttribute(model: ClassModel, classId: string, attributeId: string): ClassModel {
  const owner = model.classes.find((cls) => cls.id === classId)
  if (!owner) return model
  return updateClass(model, classId, { attributes: owner.attributes.filter((item) => item.id !== attributeId) })
}

// ---------------------------------------------------------------- methods ---

export function addMethod(model: ClassModel, classId: string): ClassModel {
  const owner = model.classes.find((cls) => cls.id === classId)
  if (!owner) return model
  const method: ModelMethod = {
    id: newId('meth'),
    name: uniqueName('newMethod', owner.methods.map((item) => item.name)),
    parameters: [],
    returnType: 'void',
    visibility: 'public',
  }
  return updateClass(model, classId, { methods: [...owner.methods, method] })
}

export function updateMethod(model: ClassModel, classId: string, methodId: string, patch: Partial<ModelMethod>): ClassModel {
  const owner = model.classes.find((cls) => cls.id === classId)
  if (!owner) return model
  return updateClass(model, classId, {
    methods: owner.methods.map((item) => (item.id === methodId ? { ...item, ...patch } : item)),
  })
}

export function removeMethod(model: ClassModel, classId: string, methodId: string): ClassModel {
  const owner = model.classes.find((cls) => cls.id === classId)
  if (!owner) return model
  return updateClass(model, classId, { methods: owner.methods.filter((item) => item.id !== methodId) })
}

/** Parameters are edited as the one string the diagram shows, `name: Type, …`,
 * rather than as a row each - it is the notation the user already reads on the
 * card, and anything unparseable still round-trips as a bare name. */
export function parseParameterText(text: string): ModelMethod['parameters'] {
  const parts: string[] = []
  let depth = 0
  let current = ''
  for (const character of text) {
    if ('<(['.includes(character)) depth += 1
    else if ('>)]'.includes(character)) depth = Math.max(0, depth - 1)
    if (character === ',' && depth === 0) {
      parts.push(current)
      current = ''
      continue
    }
    current += character
  }
  parts.push(current)
  return parts
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const separator = part.indexOf(':')
      if (separator === -1) return { name: part, type: 'String' }
      return { name: part.slice(0, separator).trim(), type: part.slice(separator + 1).trim() || 'String' }
    })
}

export function parameterText(method: ModelMethod): string {
  return method.parameters.map((parameter) => `${parameter.name}: ${parameter.type}`).join(', ')
}

// ------------------------------------------------------------------ enums ---

export function addEnum(model: ClassModel): ClassModel {
  const name = uniqueName('NewEnum', [...model.classes.map((cls) => cls.name), ...model.enums.map((item) => item.name)])
  const item: ModelEnum = { id: newId('enum'), name, literals: ['VALUE_ONE'] }
  return { ...model, enums: [...model.enums, item] }
}

export function updateEnum(model: ClassModel, enumId: string, patch: Partial<ModelEnum>): ClassModel {
  return withNames({ ...model, enums: model.enums.map((item) => (item.id === enumId ? { ...item, ...patch } : item)) })
}

export function removeEnum(model: ClassModel, enumId: string): ClassModel {
  return {
    ...model,
    enums: model.enums.filter((item) => item.id !== enumId),
    relationships: model.relationships.filter((rel) => rel.sourceClassId !== enumId && rel.targetClassId !== enumId),
  }
}

/** Literals are edited as one comma-separated field, as they read on the card. */
export function parseLiterals(text: string): string[] {
  return [...new Set(text.split(',').map((part) => part.trim()).filter(Boolean))]
}

// ---------------------------------------------------------- relationships ---

export function addRelationship(model: ClassModel): ClassModel {
  const ends = model.classes
  if (ends.length < 2) return model
  const [source, target] = ends
  const relationship: ModelRelationship = {
    id: newId('rel'),
    sourceClassId: source.id,
    targetClassId: target.id,
    source: source.name,
    target: target.name,
    type: 'association',
    label: '',
    sourceMultiplicity: '1',
    targetMultiplicity: '0..*',
    multiplicityAssumed: false,
  }
  return { ...model, relationships: [...model.relationships, relationship] }
}

export function updateRelationship(model: ClassModel, relationshipId: string, patch: Partial<ModelRelationship>): ClassModel {
  return withNames({
    ...model,
    relationships: model.relationships.map((rel) => {
      if (rel.id !== relationshipId) return rel
      const next = { ...rel, ...patch }
      // Only association, aggregation and composition carry multiplicities; the
      // XML generator drops them for the rest, so clear them rather than keep a
      // value the diagram will not show.
      if (!['association', 'aggregation', 'composition'].includes(next.type)) {
        return { ...next, sourceMultiplicity: null, targetMultiplicity: null }
      }
      return next
    }),
  })
}

export function removeRelationship(model: ClassModel, relationshipId: string): ClassModel {
  return { ...model, relationships: model.relationships.filter((rel) => rel.id !== relationshipId) }
}
