import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Button, Input, Modal, ModalContent } from '../../shared/ui'

type Props = {
  open: boolean
  title: string
  initialValue: string
  onOpenChange: (open: boolean) => void
  onSubmit: (value: string) => Promise<void>
}

export function RenameDialog({ open, title, initialValue, onOpenChange, onSubmit }: Props) {
  return (
    <Modal open={open} onOpenChange={onOpenChange}>
      <ModalContent title={title}>
        <RenameForm initialValue={initialValue} onOpenChange={onOpenChange} onSubmit={onSubmit} />
      </ModalContent>
    </Modal>
  )
}

/** Mounted each time the dialog opens, so it always starts from the current name. */
function RenameForm({ initialValue, onOpenChange, onSubmit }: Pick<Props, 'initialValue' | 'onOpenChange' | 'onSubmit'>) {
  const [value, setValue] = useState(initialValue)
  const [saving, setSaving] = useState(false)

  return (
    <form
      className="grid grid-cols-1 gap-4"
      onSubmit={async (event) => {
        event.preventDefault()
        if (!value.trim()) return
        setSaving(true)
        try {
          await onSubmit(value.trim())
          onOpenChange(false)
        } finally {
          setSaving(false)
        }
      }}
    >
      <Input value={value} autoFocus maxLength={255} onChange={(event) => setValue(event.target.value)} aria-label="Name" />
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={saving}>
          Cancel
        </Button>
        <Button type="submit" disabled={saving || !value.trim() || value.trim() === initialValue}>
          {saving ? <Loader2 className="animate-spin" /> : null} Save
        </Button>
      </div>
    </form>
  )
}
