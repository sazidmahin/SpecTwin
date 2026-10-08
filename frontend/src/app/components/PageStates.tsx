import { AlertCircle, RefreshCw } from 'lucide-react'
import { Button, Card, cn } from '../../shared/ui'

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-lg bg-surface-3', className)} />
}

export function LoadingState({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn('grid grid-cols-1 gap-3', className)} aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, index) => (
        <Card key={index} className="flex items-center gap-3 p-4">
          <Skeleton className="size-10 shrink-0 rounded-xl" />
          <div className="grid flex-1 grid-cols-1 gap-2">
            <Skeleton className="h-3.5 w-2/5" />
            <Skeleton className="h-3 w-3/5" />
          </div>
        </Card>
      ))}
    </div>
  )
}

export function ErrorState({ message, onRetry, className }: { message: string; onRetry?: () => void; className?: string }) {
  return (
    <Card className={cn('flex flex-col items-center gap-3 px-6 py-10 text-center', className)} role="alert">
      <span className="grid size-11 place-items-center rounded-xl bg-danger/10 text-danger">
        <AlertCircle className="size-5" />
      </span>
      <div>
        <p className="font-display text-sm font-bold text-fg">Something went wrong</p>
        <p className="mt-1 max-w-md text-[13px] text-fg-2">{message}</p>
      </div>
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          <RefreshCw /> Try again
        </Button>
      ) : null}
    </Card>
  )
}
