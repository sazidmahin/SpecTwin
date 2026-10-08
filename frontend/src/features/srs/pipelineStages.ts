import type { PipelineStage } from '../../api'

export const PIPELINE_STAGES: Array<{ id: PipelineStage; label: string; help: string }> = [
  { id: 'input', label: 'Input', help: 'Review the source text before clarifications are generated.' },
  { id: 'clarifications', label: 'Clarifications', help: 'Answer or skip the ambiguity questions.' },
  { id: 'final-story', label: 'Final story', help: 'Check the refined user stories.' },
  { id: 'requirements', label: 'Requirements', help: 'Review functional and non-functional requirements.' },
  { id: 'class-model', label: 'Class model', help: 'Edit classes, attributes, methods and relationships.' },
  { id: 'xml', label: 'Diagram', help: 'Preview the generated UML class diagram.' },
]
