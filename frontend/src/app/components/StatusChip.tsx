import { Chip } from '../../shared/ui'
import { runStatusLabel, runStatusTone } from '../../shared/format'

const toneMap = { success: 'success', danger: 'danger', info: 'info', accent: 'accent', warning: 'warning', muted: 'muted' } as const

export function RunStatusChip({ status }: { status: string }) {
  return <Chip tone={toneMap[runStatusTone(status)]}>{runStatusLabel(status)}</Chip>
}
