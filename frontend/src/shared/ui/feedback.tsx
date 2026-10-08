import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react'
import { Button } from './primitives'
import { cn } from './cn'

type ToastTone = 'success' | 'error' | 'info'
type Toast = { id: number; title: string; description?: string; tone: ToastTone }
type ConfirmOptions = { title: string; description?: string; confirmLabel?: string; tone?: 'danger' | 'primary' }

type FeedbackContextValue = {
  toast: (title: string, options?: { description?: string; tone?: ToastTone }) => void
  confirm: (options: ConfirmOptions) => Promise<boolean>
}

const FeedbackContext = createContext<FeedbackContextValue | null>(null)

const toneIcon = { success: CheckCircle2, error: XCircle, info: Info }
const toneClass = {
  success: 'text-success',
  error: 'text-danger',
  info: 'text-accent',
}

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const [pending, setPending] = useState<(ConfirmOptions & { resolve: (value: boolean) => void }) | null>(null)
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => setToasts((current) => current.filter((item) => item.id !== id)), [])

  const toast = useCallback<FeedbackContextValue['toast']>(
    (title, options = {}) => {
      const id = nextId.current++
      setToasts((current) => [...current.slice(-3), { id, title, description: options.description, tone: options.tone ?? 'success' }])
      window.setTimeout(() => dismiss(id), options.tone === 'error' ? 6500 : 3500)
    },
    [dismiss],
  )

  const confirm = useCallback<FeedbackContextValue['confirm']>(
    (options) => new Promise<boolean>((resolve) => setPending({ ...options, resolve })),
    [],
  )

  function settle(value: boolean) {
    pending?.resolve(value)
    setPending(null)
  }

  const value = useMemo(() => ({ toast, confirm }), [toast, confirm])

  return (
    <FeedbackContext.Provider value={value}>
      {children}

      <div
        className="pointer-events-none fixed inset-x-3 bottom-3 z-[60] flex flex-col items-end gap-2 sm:inset-x-auto sm:right-5 sm:bottom-5"
        aria-live="polite"
      >
        {toasts.map((item) => {
          const Icon = toneIcon[item.tone]
          return (
            <div
              key={item.id}
              role={item.tone === 'error' ? 'alert' : 'status'}
              className="pointer-events-auto flex w-full max-w-sm animate-rise-in items-start gap-3 rounded-xl border border-border bg-surface px-4 py-3 shadow-[var(--elev-3)] sm:w-96"
            >
              <Icon className={cn('mt-0.5 size-[18px] shrink-0', toneClass[item.tone])} />
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-semibold text-fg">{item.title}</p>
                {item.description ? <p className="mt-0.5 text-xs text-fg-2">{item.description}</p> : null}
              </div>
              <button
                type="button"
                onClick={() => dismiss(item.id)}
                className="grid size-6 shrink-0 place-items-center rounded-md text-fg-3 transition hover:bg-surface-3 hover:text-fg"
                aria-label="Dismiss notification"
              >
                <X className="size-3.5" />
              </button>
            </div>
          )
        })}
      </div>

      <DialogPrimitive.Root open={pending !== null} onOpenChange={(open) => (!open ? settle(false) : undefined)}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-slate-950/45 backdrop-blur-[3px] data-[state=open]:animate-fade-in" />
          <DialogPrimitive.Content className="fixed left-1/2 top-1/2 z-50 w-[94vw] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-border bg-surface p-6 shadow-[var(--elev-3)] data-[state=open]:animate-rise-in">
            <div className="flex gap-4">
              <span
                className={cn(
                  'grid size-10 shrink-0 place-items-center rounded-xl',
                  pending?.tone === 'primary' ? 'bg-accent/10 text-accent' : 'bg-danger/10 text-danger',
                )}
              >
                <AlertTriangle className="size-5" />
              </span>
              <div className="min-w-0">
                <DialogPrimitive.Title className="font-display text-base font-bold text-fg">{pending?.title}</DialogPrimitive.Title>
                {pending?.description ? (
                  <DialogPrimitive.Description className="mt-1.5 text-[13px] leading-relaxed text-fg-2">
                    {pending.description}
                  </DialogPrimitive.Description>
                ) : null}
              </div>
            </div>
            <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <Button variant="secondary" onClick={() => settle(false)}>
                Cancel
              </Button>
              <Button variant={pending?.tone === 'primary' ? 'primary' : 'destructive'} onClick={() => settle(true)} autoFocus>
                {pending?.confirmLabel ?? 'Delete'}
              </Button>
            </div>
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>
    </FeedbackContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useFeedback() {
  const context = useContext(FeedbackContext)
  if (!context) throw new Error('useFeedback must be used inside FeedbackProvider')
  return context
}
