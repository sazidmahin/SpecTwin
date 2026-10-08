export type ClassModelerMode = 'rule_based' | 'llm' | 'ai'

export type ModelAttribute = { id: string; name: string; type: string; visibility: string }
export type ModelParameter = { name: string; type: string }
export type ModelMethod = { id: string; name: string; parameters: ModelParameter[]; returnType: string; visibility: string }

export type ModelClass = {
  id: string
  name: string
  stereotype: 'entity' | 'abstract' | 'interface' | string
  attributes: ModelAttribute[]
  methods: ModelMethod[]
  sourceSentences: number[]
}

export type ModelRelationship = {
  id: string
  sourceClassId: string
  targetClassId: string
  source: string
  target: string
  type: 'association' | 'aggregation' | 'composition' | 'inheritance' | 'dependency' | 'realization'
  label: string
  sourceMultiplicity: string | null
  targetMultiplicity: string | null
  multiplicityAssumed: boolean
}

export type ModelEnum = { id: string; name: string; literals: string[]; owner?: string }

export type SentenceStep = { index: number; text: string; kind: string; findings: string[] }
export type NounDecision = {
  name: string
  decision: 'class' | 'attribute' | 'rejected' | 'merged' | 'value' | string
  reason: string
  mergedInto?: string
  phrases: string[]
  sentences: number[]
}
export type VerbStep = {
  verb: string
  subject: string | null
  object: string | null
  assignedTo: string | null
  method: string | null
  sentence: number | null
  note?: string
}

export type ClassModelerResult = {
  mode: ClassModelerMode
  provider: string | null
  modelName: string | null
  model: { classes: ModelClass[]; relationships: ModelRelationship[]; enums: ModelEnum[] }
  drawioXml: string
  validation: { valid: boolean; errors: string[] }
  analysis: {
    domain: string[]
    sentences: SentenceStep[]
    nouns: NounDecision[]
    verbs: VerbStep[]
    generalisation: string[]
    warnings: string[]
  }
}

export type LlmProvider = 'ollama' | 'byok' | 'ai'

export type OllamaModels = {
  reachable: boolean
  installed: string[]
  suggested: string[]
  defaultModel: string | null
  error: string | null
}
