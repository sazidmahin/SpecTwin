import { useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import { diagramApi, projectApi } from '../api'
import { DiagramDialog } from '../app/components/DiagramDialog'
import { FilterBar } from '../app/components/FilterBar'
import { DiagramList } from '../app/components/Lists'
import { ErrorState, LoadingState } from '../app/components/PageStates'
import { navigate, routes } from '../app/core/router'
import { useSession } from '../app/core/session'
import { useAsync } from '../app/core/useAsync'
import { Button, PageHeader, Select } from '../shared/ui'

export function DiagramsPage() {
  const { workspaceId, canEdit } = useSession()
  const diagrams = useAsync(() => diagramApi.listWorkspace(workspaceId), [workspaceId], Boolean(workspaceId))
  const projects = useAsync(() => projectApi.list(workspaceId), [workspaceId], Boolean(workspaceId))
  const [query, setQuery] = useState('')
  const [projectId, setProjectId] = useState('')
  const [source, setSource] = useState('')
  const [creating, setCreating] = useState(false)
  const activeProjects = useMemo(() => (projects.data ?? []).filter((item) => item.status === 'active'), [projects.data])
  const projectMap = useMemo(() => new Map(activeProjects.map((item) => [item.id, item])), [activeProjects])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (diagrams.data ?? []).filter(
      (diagram) =>
        (!projectId || diagram.project_id === projectId) &&
        (!source || diagram.source === source) &&
        (!needle || diagram.title.toLowerCase().includes(needle)),
    )
  }, [diagrams.data, query, projectId, source])

  const newButton = canEdit ? (
    <Button onClick={() => setCreating(true)} disabled={!activeProjects.length}>
      <Plus /> New diagram
    </Button>
  ) : null

  return (
    <section className="grid grid-cols-1 gap-5">
      <PageHeader title="Diagrams" description="UML class diagrams from your generations and manual draw.io diagrams." actions={newButton} />
      <FilterBar query={query} onQueryChange={setQuery} placeholder="Search diagrams" projects={activeProjects} projectId={projectId} onProjectChange={setProjectId}>
        <Select inputSize="sm" value={source} onChange={(event) => setSource(event.target.value)} className="h-9.5 sm:w-40" aria-label="Filter by source">
          <option value="">All sources</option>
          <option value="generated">Generated</option>
          <option value="manual">Manual</option>
        </Select>
      </FilterBar>
      {diagrams.loading && !diagrams.data ? (
        <LoadingState rows={3} />
      ) : diagrams.error ? (
        <ErrorState message={diagrams.error} onRetry={diagrams.reload} />
      ) : (
        <DiagramList diagrams={filtered} projects={projectMap} emptyAction={diagrams.data?.length ? undefined : newButton} />
      )}
      <DiagramDialog
        open={creating}
        onOpenChange={setCreating}
        projects={activeProjects}
        defaultProjectId={projectId || undefined}
        onCreated={(diagram) => navigate(routes.diagram(diagram.project_id, diagram.id))}
      />
    </section>
  )
}
