import { useState } from 'react'
import { errorMessage, pipelineApi } from '../../api'
import type { PipelineRunSummary } from '../../api'
import { useFeedback } from '../../shared/ui'
import { useSession } from '../core/session'
import { RenameDialog } from './RenameDialog'

/** Rename / delete handlers for generation runs, plus the dialog they need. */
export function useRunActions(onChanged: () => void) {
  const { workspaceId } = useSession()
  const { toast, confirm } = useFeedback()
  const [renaming, setRenaming] = useState<PipelineRunSummary | null>(null)

  async function remove(run: PipelineRunSummary) {
    const ok = await confirm({
      title: `Delete “${run.title}”?`,
      description: run.srs_document_id
        ? 'The stage history is removed. The published SRS document and diagram are kept.'
        : 'All stages of this generation are removed permanently.',
    })
    if (!ok) return
    try {
      await pipelineApi.remove(workspaceId, run.project_id, run.id)
      toast('Generation deleted')
      onChanged()
    } catch (caught) {
      toast('Delete failed', { description: errorMessage(caught), tone: 'error' })
    }
  }

  const dialog = (
    <RenameDialog
      open={renaming !== null}
      title="Rename generation"
      initialValue={renaming?.title ?? ''}
      onOpenChange={(open) => (!open ? setRenaming(null) : undefined)}
      onSubmit={async (title) => {
        if (!renaming) return
        try {
          await pipelineApi.rename(workspaceId, renaming.project_id, renaming.id, title)
          toast('Generation renamed')
          onChanged()
        } catch (caught) {
          toast('Rename failed', { description: errorMessage(caught), tone: 'error' })
          throw caught
        }
      }}
    />
  )

  return { onRename: setRenaming, onDelete: remove, dialog }
}
