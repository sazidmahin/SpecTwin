import type { ModelClass, ModelRelationship } from '../../api'

export type RelationshipKind = ModelRelationship['type']

export const relationshipGuide: Record<
  RelationshipKind,
  { title: string; reads: string; meaning: string; line: string; end: string }
> = {
  inheritance: {
    title: 'Inheritance',
    reads: 'is a',
    meaning: 'The child is a more specific kind of the parent. It gets every attribute and method of the parent and can add its own.',
    line: 'Solid line',
    end: 'Hollow triangle at the parent',
  },
  realization: {
    title: 'Interface realization',
    reads: 'implements',
    meaning: 'The interface is a contract: it only names methods. The class promises to provide every one of them.',
    line: 'Dashed line',
    end: 'Hollow triangle at the interface',
  },
  composition: {
    title: 'Composition',
    reads: 'owns',
    meaning: 'Strong "part of": the part lives and dies with its whole. Delete the whole and its parts go too.',
    line: 'Solid line',
    end: 'Filled diamond at the whole',
  },
  aggregation: {
    title: 'Aggregation',
    reads: 'has',
    meaning: 'Weak "has": the whole groups the parts, but a part can exist on its own or move to another whole.',
    line: 'Solid line',
    end: 'Hollow diamond at the whole',
  },
  association: {
    title: 'Association',
    reads: 'works with',
    meaning: 'The two classes know about each other; the label is the verb that connects them.',
    line: 'Solid line',
    end: 'Open arrow shows the reading direction',
  },
  dependency: {
    title: 'Dependency',
    reads: 'uses',
    meaning: 'A temporary "uses": one class needs the other only for a moment (for example as a method parameter).',
    line: 'Dashed line',
    end: 'Open arrow at the class being used',
  },
}

export const stereotypeGuide: Record<string, { label: string; meaning: string }> = {
  entity: { label: 'Class', meaning: 'A concrete thing in the domain with its own data (attributes) and behaviour (methods).' },
  abstract: {
    label: 'Abstract class',
    meaning: 'A general parent that is never created on its own - only its subclasses are. Name shown in italics.',
  },
  interface: {
    label: 'Interface',
    meaning: 'A contract listing methods without data. Classes that implement it must provide those methods.',
  },
  enumeration: { label: 'Enumeration', meaning: 'A fixed list of allowed values, used as the type of an attribute.' },
}

/** "0..5" -> "up to 5", "1..*" -> "one or more". */
export function describeMultiplicity(value: string | null | undefined): string | null {
  if (!value) return null
  const text = value.trim()
  if (text === '1') return 'exactly one'
  if (text === '0..1') return 'at most one'
  if (text === '*' || text === '0..*') return 'any number of'
  if (text === '1..*') return 'one or more'
  let match = /^0\.\.(\d+)$/.exec(text)
  if (match) return `up to ${match[1]}`
  match = /^(\d+)\.\.\*$/.exec(text)
  if (match) return `at least ${match[1]}`
  match = /^(\d+)\.\.(\d+)$/.exec(text)
  if (match) return `between ${match[1]} and ${match[2]}`
  if (/^\d+$/.test(text)) return `exactly ${text}`
  return text
}

function plural(name: string, count: string | null) {
  if (!count || count === 'exactly one' || count === 'at most one') return name
  return name.endsWith('s') ? name : `${name}s`
}

/** One plain-English sentence explaining an edge, e.g. "Each Member borrows up to 5 Books." */
export function explainRelationship(rel: ModelRelationship, classes: ModelClass[]): { headline: string; detail: string } {
  const source = rel.source
  const target = rel.target
  const targetClass = classes.find((cls) => cls.id === rel.targetClassId)
  switch (rel.type) {
    case 'inheritance':
      return {
        headline: `${source} is a ${target}`,
        detail: `${source} inherits ${target}'s attributes and methods${
          targetClass && (targetClass.attributes.length || targetClass.methods.length)
            ? ` (${[...targetClass.attributes.map((attr) => attr.name), ...targetClass.methods.map((method) => `${method.name}()`)].slice(0, 4).join(', ')})`
            : ''
        } and adds its own.`,
      }
    case 'realization': {
      const methods = targetClass?.methods.map((method) => `${method.name}()`) ?? []
      return {
        headline: `${source} implements ${target}`,
        detail: methods.length
          ? `${target} is a contract; ${source} must provide ${methods.join(', ')}.`
          : `${target} is a contract that ${source} promises to fulfil.`,
      }
    }
    default: {
      const forward = describeMultiplicity(rel.targetMultiplicity)
      const backward = describeMultiplicity(rel.sourceMultiplicity)
      const verb =
        rel.type === 'composition' ? 'owns' : rel.type === 'aggregation' ? 'has' : rel.type === 'dependency' ? 'uses' : rel.label || 'is linked to'
      const headline = `Each ${source} ${verb} ${forward ? `${forward} ` : ''}${plural(target, forward)}`
      const extra =
        rel.type === 'composition'
          ? `A ${target} cannot exist without its ${source}.`
          : rel.type === 'aggregation'
            ? `A ${target} can also exist on its own.`
            : backward
              ? `Each ${target} belongs to ${backward} ${plural(source, backward)}.`
              : ''
      const assumed = rel.multiplicityAssumed ? ' (The count was not stated in the text, so it is assumed.)' : ''
      return { headline: `${headline}.`, detail: `${extra}${assumed}`.trim() }
    }
  }
}
