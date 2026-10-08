import { cn } from './cn'
import { initials } from './initials'

/** SpecTwin logo mark: two stacked "spec" sheets, the twin offset behind. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'relative grid size-8 shrink-0 place-items-center rounded-[10px] bg-gradient-to-br from-accent to-accent2-dim text-white shadow-[0_6px_16px_-6px_color-mix(in_oklab,var(--color-accent)_80%,transparent)]',
        className,
      )}
      aria-hidden="true"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="size-[58%]">
        <path d="M8 3h8l4 4v10a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" opacity="0.55" transform="translate(-2 2)" />
        <path d="M10 3h6l4 4v10a2 2 0 0 1-2 2h-8a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" fill="currentColor" fillOpacity="0.18" />
        <path d="M11 10h6M11 13.5h4" />
      </svg>
    </span>
  )
}

export function Avatar({ name, className }: { name: string; className?: string }) {
  return (
    <span
      className={cn(
        'grid size-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-accent2 to-accent text-[11px] font-bold text-white ring-2 ring-white/10',
        className,
      )}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  )
}
