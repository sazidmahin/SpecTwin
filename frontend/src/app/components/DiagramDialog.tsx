import { useState } from 'react'
import type { FormEvent } from 'react'
import { Loader2 } from 'lucide-react'
import { diagramApi, errorMessage } from '../../api'
import type { DiagramDetail, Project } from '../../api'
import { Button, Field, Input, Modal, ModalContent, Select, useFeedback } from '../../shared/ui'
import { useSession } from '../core/session'

export const BLANK_DRAWIO_XML =
  '<mxfile><diagram name="Page-1" id="page-1"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/></root></mxGraphModel></diagram></mxfile>'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  projects: Project[]
  defaultProjectId?: string
  onCreated: (diagram: DiagramDetail) => void
}

export function DiagramDialog({ open, onOpenChange, projects, defaultProjectId, onCreated }: Props) {
  return (
    <Modal open={open} onOpenChange={onOpenChange}>
      <ModalContent title="New diagram" description="Starts a blank draw.io canvas you can edit and version.">
        <DiagramForm projects={projects} defaultProjectId={defaultProjectId} onOpenChange={onOpenChange} onCreated={onCreated} />
      </ModalContent>
    </Modal>
  )
}

function DiagramForm({ onOpenChange, projects, defaultProjectId, onCreated }: Omit<Props, 'open'>) {
  const { workspaceId } = useSession()
  const { toast } = useFeedback()
  const [title, setTitle] = useState('')
  const [type, setType] = useState('class')
  const [projectId, setProjectId] = useState(defaultProjectId ?? projects[0]?.id ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!title.trim() || !projectId) {
      setError(!projectId ? 'Create a project first.' : 'Give the diagram a title.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const created = await diagramApi.create(workspaceId, projectId, {
        title: title.trim(),
        diagram_type: type,
        drawio_xml: BLANK_DRAWIO_XML,
      })
      toast('Diagram created')
      onCreated(created)
      onOpenChange(false)
    } catch (caught) {
      setError(errorMessage(caught, 'Unable to create the diagram'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="grid grid-cols-1 gap-4" onSubmit={submit} noValidate>
      <Field label="Title" htmlFor="diagram-title" required>
        <Input
          id="diagram-title"
          value={title}
          autoFocus
          maxLength={255}
          placeholder="e.g. Checkout sequence"
          onChange={(event) => setTitle(event.target.value)}
        />
      </Field>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Project" htmlFor="diagram-project" required>
          <Select id="diagram-project" value={projectId} onChange={(event) => setProjectId(event.target.value)}>
            {!projects.length ? <option value="">No projects</option> : null}
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Type" htmlFor="diagram-type">
          <Select id="diagram-type" value={type} onChange={(event) => setType(event.target.value)}>
            <option value="class">Class</option>
            <option value="sequence">Sequence</option>
            <option value="flowchart">Flowchart</option>
            <option value="use-case">Use case</option>
            <option value="other">Other</option>
          </Select>
        </Field>
      </div>
      {error ? (
        <p className="text-[13px] font-medium text-danger" role="alert">
          {error}
        </p>
      ) : null}
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={saving}>
          Cancel
        </Button>
        <Button type="submit" disabled={saving}>
          {saving ? <Loader2 className="animate-spin" /> : null} Create diagram
        </Button>
      </div>
    </form>
  )
}
