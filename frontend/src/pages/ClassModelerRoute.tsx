import { projectApi } from '../api'
import { ErrorState, LoadingState } from '../app/components/PageStates'
import { useSession } from '../app/core/session'
import { useAsync } from '../app/core/useAsync'
import { ClassModelerPage } from '../features/classModeler/ClassModelerPage'

export function ClassModelerRoute() {
  const { workspaceId } = useSession()
  const projects = useAsync(() => projectApi.list(workspaceId), [workspaceId], Boolean(workspaceId))
  if (projects.loading && !projects.data) return <LoadingState rows={2} />
  if (projects.error) return <ErrorState message={projects.error} onRetry={projects.reload} />
  return <ClassModelerPage projects={(projects.data ?? []).filter((item) => item.status === 'active')} />
}
