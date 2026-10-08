import { useMemo, useState } from 'react'
import { GitCompareArrows, Plus } from 'lucide-react'
import { projectApi, srsApi } from '../api'
import { FilterBar } from '../app/components/FilterBar'
import { DocumentList } from '../app/components/Lists'
import { ErrorState, LoadingState } from '../app/components/PageStates'
import { href, routes } from '../app/core/router'
import { useSession } from '../app/core/session'
import { useAsync } from '../app/core/useAsync'
import { LinkButton, PageHeader } from '../shared/ui'

export function DocumentsPage() {
  const { workspaceId, canEdit } = useSession()
  const documents = useAsync(() => srsApi.listWorkspace(workspaceId), [workspaceId], Boolean(workspaceId))
  const projects = useAsync(() => projectApi.list(workspaceId), [workspaceId], Boolean(workspaceId))
  const [query, setQuery] = useState('')
  const [projectId, setProjectId] = useState('')
  const projectMap = useMemo(() => new Map((projects.data ?? []).map((item) => [item.id, item])), [projects.data])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (documents.data ?? []).filter(
      (document) =>
        (!projectId || document.project_id === projectId) &&
        (!needle || document.title.toLowerCase().includes(needle) || document.content_markdown.toLowerCase().includes(needle)),
    )
  }, [documents.data, query, projectId])

  const compareButton =
    (documents.data?.length ?? 0) >= 2 ? (
      <LinkButton variant="secondary" href={href(routes.compareDocuments())}>
        <GitCompareArrows /> Compare
      </LinkButton>
    ) : null

  const newButton = canEdit ? (
    <LinkButton href={href(routes.generate())}>
      <Plus /> Generate SRS
    </LinkButton>
  ) : null

  return (
    <section className="grid grid-cols-1 gap-5">
      <PageHeader title="SRS documents" description="Published software requirements specifications across all projects."
        actions={
          compareButton || newButton ? (
            <div className="flex flex-wrap gap-2">
              {compareButton}
              {newButton}
            </div>
          ) : null
        }
      />
      <FilterBar
        query={query}
        onQueryChange={setQuery}
        placeholder="Search titles and content"
        projects={projects.data?.filter((item) => item.status === 'active')}
        projectId={projectId}
        onProjectChange={setProjectId}
      />
      {documents.loading && !documents.data ? (
        <LoadingState rows={3} />
      ) : documents.error ? (
        <ErrorState message={documents.error} onRetry={documents.reload} />
      ) : (
        <DocumentList documents={filtered} projects={projectMap} emptyAction={documents.data?.length ? undefined : newButton} />
      )}
    </section>
  )
}
