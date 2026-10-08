import { useMemo, useState } from 'react'
import { Plus } from 'lucide-react'
import { pipelineApi, projectApi } from '../api'
import { FilterBar } from '../app/components/FilterBar'
import { RunList } from '../app/components/Lists'
import { ErrorState, LoadingState } from '../app/components/PageStates'
import { useRunActions } from '../app/components/useRunActions'
import { href, routes } from '../app/core/router'
import { useSession } from '../app/core/session'
import { useAsync } from '../app/core/useAsync'
import { LinkButton, PageHeader, Select } from '../shared/ui'

const STATUS_FILTERS = [
  { value: '', label: 'All statuses' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
]

export function GenerationsPage() {
  const { workspaceId, canEdit } = useSession()
  const runs = useAsync(() => pipelineApi.listWorkspace(workspaceId), [workspaceId], Boolean(workspaceId))
  const projects = useAsync(() => projectApi.list(workspaceId), [workspaceId], Boolean(workspaceId))
  const actions = useRunActions(() => void runs.reload())
  const [query, setQuery] = useState('')
  const [projectId, setProjectId] = useState('')
  const [status, setStatus] = useState('')

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (runs.data ?? []).filter((run) => {
      if (projectId && run.project_id !== projectId) return false
      if (status === 'completed' && run.status !== 'completed') return false
      if (status === 'failed' && run.status !== 'failed') return false
      if (status === 'in_progress' && (run.status === 'completed' || run.status === 'failed')) return false
      return !needle || run.title.toLowerCase().includes(needle) || (run.project_name ?? '').toLowerCase().includes(needle)
    })
  }, [runs.data, query, projectId, status])

  const newButton = canEdit ? (
    <LinkButton href={href(routes.generate())}>
      <Plus /> New generation
    </LinkButton>
  ) : null

  return (
    <section className="grid grid-cols-1 gap-5">
      <PageHeader
        title="Generations"
        description="Every SRS generation in this workspace. Open one to continue reviewing where you left off."
        actions={newButton}
      />
      <FilterBar
        query={query}
        onQueryChange={setQuery}
        placeholder="Search generations"
        projects={projects.data?.filter((item) => item.status === 'active')}
        projectId={projectId}
        onProjectChange={setProjectId}
      >
        <Select inputSize="sm" value={status} onChange={(event) => setStatus(event.target.value)} className="h-9.5 sm:w-44" aria-label="Filter by status">
          {STATUS_FILTERS.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </Select>
      </FilterBar>
      {runs.loading && !runs.data ? (
        <LoadingState rows={4} />
      ) : runs.error ? (
        <ErrorState message={runs.error} onRetry={runs.reload} />
      ) : (
        <RunList
          runs={filtered}
          canEdit={canEdit}
          onRename={actions.onRename}
          onDelete={actions.onDelete}
          emptyAction={runs.data?.length ? undefined : newButton}
        />
      )}
      {actions.dialog}
    </section>
  )
}
