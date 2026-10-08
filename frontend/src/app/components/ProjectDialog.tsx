import { useState } from 'react'
import type { FormEvent } from 'react'
import { Loader2 } from 'lucide-react'
import { errorMessage, projectApi } from '../../api'
import type { Project } from '../../api'
import { Button, Field, Input, Modal, ModalContent, Textarea, useFeedback } from '../../shared/ui'
import { useSession } from '../core/session'

type Props = {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Pass a project to edit it; omit to create a new one. */
  project?: Project
  onSaved: (project: Project) => void
}

export function ProjectDialog({ open, onOpenChange, project, onSaved }: Props) {
  return (
    <Modal open={open} onOpenChange={onOpenChange}>
      <ModalContent
        title={project ? 'Edit project' : 'New project'}
        description={project ? 'Update the project name and description.' : 'A project groups SRS generations, documents and diagrams.'}
      >
        <ProjectForm project={project} onOpenChange={onOpenChange} onSaved={onSaved} />
      </ModalContent>
    </Modal>
  )
}

function ProjectForm({ project, onOpenChange, onSaved }: Omit<Props, 'open'>) {
  const { workspaceId } = useSession()
  const { toast } = useFeedback()
  const [name, setName] = useState(project?.name ?? '')
  const [description, setDescription] = useState(project?.description ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!name.trim()) {
      setError('Give the project a name.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const payload = { name: name.trim(), description: description.trim() || null }
      const saved = project ? await projectApi.update(workspaceId, project.id, payload) : await projectApi.create(workspaceId, payload)
      toast(project ? 'Project updated' : 'Project created', { description: saved.name })
      onSaved(saved)
      onOpenChange(false)
    } catch (caught) {
      setError(errorMessage(caught, 'Unable to save the project'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="grid grid-cols-1 gap-4" onSubmit={submit} noValidate>
      <Field label="Name" htmlFor="project-name" required>
        <Input
          id="project-name"
          value={name}
          autoFocus
          maxLength={255}
          placeholder="e.g. Hospital management system"
          onChange={(event) => setName(event.target.value)}
        />
      </Field>
      <Field label="Description" htmlFor="project-description" hint="Optional — what the system is for.">
        <Textarea
          id="project-description"
          rows={3}
          value={description}
          maxLength={5000}
          placeholder="Short summary of the system"
          onChange={(event) => setDescription(event.target.value)}
        />
      </Field>
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
          {saving ? <Loader2 className="animate-spin" /> : null}
          {project ? 'Save changes' : 'Create project'}
        </Button>
      </div>
    </form>
  )
}
