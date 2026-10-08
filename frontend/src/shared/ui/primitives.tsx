import type { AnchorHTMLAttributes, ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react'
import { forwardRef } from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from './cn'
import { buttonClasses, chipTones } from './styles'
import type { ButtonSize, ButtonVariant, Tone } from './styles'

/* ── Card ─────────────────────────────────────────────── */

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-xl border border-border bg-surface shadow-[var(--elev-1)]', className)} {...props} />
}

/* ── Button ───────────────────────────────────────────── */

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize }

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', className, type, ...props },
  ref,
) {
  return <button ref={ref} type={type ?? 'button'} className={buttonClasses({ variant, size, className })} {...props} />
})

type LinkButtonProps = AnchorHTMLAttributes<HTMLAnchorElement> & { variant?: ButtonVariant; size?: ButtonSize }

export function LinkButton({ variant = 'primary', size = 'md', className, ...props }: LinkButtonProps) {
  return <a className={buttonClasses({ variant, size, className })} {...props} />
}

/* ── Chip ─────────────────────────────────────────────── */

type ChipProps = HTMLAttributes<HTMLSpanElement> & { tone?: Tone }

export function Chip({ tone = 'neutral', className, ...props }: ChipProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-semibold leading-4 [&_svg]:size-3',
        chipTones[tone],
        className,
      )}
      {...props}
    />
  )
}

/* ── PageHeader ───────────────────────────────────────── */

type PageHeaderProps = {
  title: string
  description?: ReactNode
  eyebrow?: string
  actions?: ReactNode
  size?: 'page' | 'section'
  className?: string
}

export function PageHeader({ title, description, eyebrow, actions, size = 'page', className }: PageHeaderProps) {
  const section = size === 'section'
  const Heading = section ? 'h2' : 'h1'
  return (
    <div className={cn('flex flex-wrap items-start justify-between gap-x-4 gap-y-3', !section && 'animate-rise-in', className)}>
      <div className="min-w-0">
        {eyebrow ? (
          <span className="mb-1 inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.14em] text-accent">
            {eyebrow}
          </span>
        ) : null}
        <Heading
          className={cn(
            'font-display tracking-tight text-fg',
            section ? 'text-[15px] font-bold' : 'text-[22px] font-extrabold leading-tight sm:text-[26px]',
          )}
        >
          {title}
        </Heading>
        {description ? (
          <p className={cn('max-w-3xl text-fg-2', section ? 'mt-0.5 text-[12.5px]' : 'mt-1.5 text-[13.5px] sm:text-sm')}>{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  )
}

/* ── StatTile ─────────────────────────────────────────── */

type StatTileProps = {
  label: string
  value: string | number
  delta?: string
  deltaDirection?: 'up' | 'down'
  icon?: LucideIcon
  children?: ReactNode
  className?: string
}

export function StatTile({ label, value, delta, deltaDirection = 'up', icon: Icon, children, className }: StatTileProps) {
  return (
    <Card className={cn('group relative overflow-hidden px-4 py-4 transition hover:-translate-y-0.5 hover:shadow-[var(--elev-2)] sm:px-5 sm:py-4.5', className)}>
      <div className="flex items-start justify-between gap-3">
        <span className="text-[12.5px] font-medium text-fg-2">{label}</span>
        {Icon ? (
          <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent/10 text-accent ring-1 ring-accent/10 ring-inset">
            <Icon className="size-4" />
          </span>
        ) : null}
      </div>
      <div className="mt-1 mb-1 font-display text-2xl font-extrabold leading-none sm:text-[28px] tracking-tight text-fg">{value}</div>
      {delta ? (
        <div className={cn('text-[11.5px] font-semibold', deltaDirection === 'up' ? 'text-success' : 'text-danger')}>{delta}</div>
      ) : null}
      {children}
    </Card>
  )
}

/* ── ProgressBar ──────────────────────────────────────── */

export function ProgressBar({ value, className }: { value: number; className?: string }) {
  return (
    <div className={cn('h-1.5 overflow-hidden rounded-full bg-surface-3', className)}>
      <div
        className="h-full rounded-full bg-gradient-to-r from-accent to-accent2 transition-[width] duration-500"
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  )
}

/* ── DataTable ────────────────────────────────────────── */

export function DataTable({ className, children, ...props }: HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="overflow-x-auto">
      <table
        className={cn(
          'w-full border-separate border-spacing-0 text-left',
          '[&_th]:whitespace-nowrap [&_th]:border-b [&_th]:border-border [&_th]:bg-surface-2 [&_th]:px-4 [&_th]:py-2.5 [&_th]:text-[11px] [&_th]:font-semibold [&_th]:uppercase [&_th]:tracking-[0.08em] [&_th]:text-fg-3',
          '[&_td]:border-b [&_td]:border-border [&_td]:px-4 [&_td]:py-3 [&_td]:align-middle [&_td]:text-[13px] [&_td]:text-fg-2',
          '[&_tbody_tr:last-child_td]:border-b-0 [&_tbody_tr]:transition-colors [&_tbody_tr:hover_td]:bg-surface-2',
          className,
        )}
        {...props}
      >
        {children}
      </table>
    </div>
  )
}

/* ── EmptyState ───────────────────────────────────────── */

type EmptyStateProps = {
  title: string
  description?: string
  icon?: LucideIcon
  action?: ReactNode
  className?: string
}

export function EmptyState({ title, description, icon: Icon, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'grid place-items-center gap-2 rounded-xl border border-dashed border-border-strong bg-surface-2/60 px-6 py-10 text-center',
        className,
      )}
    >
      {Icon ? (
        <span className="mb-1 grid size-11 place-items-center rounded-xl bg-surface text-fg-3 shadow-[var(--elev-1)] ring-1 ring-border">
          <Icon className="size-5" />
        </span>
      ) : null}
      <p className="font-display text-sm font-bold text-fg">{title}</p>
      {description ? <p className="max-w-sm text-[12.5px] leading-relaxed text-fg-3">{description}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  )
}

/* ── CompactList ──────────────────────────────────────── */

type CompactListItem = { id: string; title: string; meta: string; value?: string; tone?: Tone }

export function CompactList({ items, emptyText }: { items: CompactListItem[]; emptyText: string }) {
  if (items.length === 0) {
    return <p className="text-[13px] text-fg-3">{emptyText}</p>
  }
  return (
    <div className="grid grid-cols-1 gap-2">
      {items.map((item) => (
        <div
          key={item.id}
          className="flex min-h-14 items-center justify-between gap-3 rounded-lg border border-border bg-surface-2 px-3.5 py-2.5 transition hover:border-border-strong hover:bg-surface"
        >
          <div className="min-w-0">
            <strong className="block truncate text-[13px] font-semibold text-fg">{item.title}</strong>
            <small className="block truncate text-xs text-fg-3">{item.meta}</small>
          </div>
          {item.value ? <Chip tone={item.tone ?? 'muted'}>{item.value}</Chip> : null}
        </div>
      ))}
    </div>
  )
}

/* ── RadioCard ────────────────────────────────────────── */

type RadioCardProps = {
  name: string
  value: string
  checked?: boolean
  defaultChecked?: boolean
  onChange?: (value: string) => void
  disabled?: boolean
  title: ReactNode
  description?: ReactNode
  icon?: LucideIcon
  meta?: ReactNode
  children?: ReactNode
}

export function RadioCard({
  name,
  value,
  checked,
  defaultChecked,
  onChange,
  disabled,
  title,
  description,
  icon: Icon,
  meta,
  children,
}: RadioCardProps) {
  return (
    <label
      className={cn(
        'block rounded-xl border-[1.5px] border-border bg-surface px-4 py-3.5 transition',
        'has-[:checked]:border-accent has-[:checked]:bg-accent/[0.06] has-[:checked]:shadow-[var(--ring-accent)]',
        disabled ? 'cursor-not-allowed opacity-55' : 'cursor-pointer hover:border-border-strong hover:bg-surface-2',
      )}
    >
      <div className="flex items-start gap-3">
        <input
          type="radio"
          name={name}
          value={value}
          checked={checked}
          defaultChecked={defaultChecked}
          disabled={disabled}
          onChange={(event) => onChange?.(event.target.value)}
          className="mt-0.5 size-[15px] shrink-0 accent-accent"
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 text-[13px] font-semibold text-fg">
            {Icon ? <Icon className="size-3.5 text-fg-2" /> : null}
            {title}
          </div>
          {description ? <div className="mt-0.5 text-[11.5px] text-fg-3">{description}</div> : null}
          {children}
        </div>
        {meta ? <div className="flex shrink-0 items-center gap-1">{meta}</div> : null}
      </div>
    </label>
  )
}

/* ── StepTrack ────────────────────────────────────────── */

type StepTrackProps = {
  steps: string[]
  current: number
  className?: string
}

export function StepTrack({ steps, current, className }: StepTrackProps) {
  return (
    <div className={cn('flex items-center overflow-x-auto pb-1 [scrollbar-width:none]', className)}>
      {steps.map((label, index) => {
        const done = index < current
        const active = index === current
        return (
          <div className="flex flex-1 items-center last:flex-none" key={label}>
            <div className="flex flex-col items-center gap-1.5">
              <div
                className={cn(
                  'grid size-8 place-items-center rounded-full border-2 text-xs font-bold transition',
                  done && 'border-accent bg-accent text-fg-invert',
                  active && 'border-accent bg-surface text-accent shadow-[var(--ring-accent)]',
                  !done && !active && 'border-border bg-surface-2 text-fg-3',
                )}
              >
                {done ? '✓' : index + 1}
              </div>
              <span
                className={cn(
                  'whitespace-nowrap text-[11px] font-semibold',
                  !active && 'hidden sm:inline',
                  active ? 'text-accent' : done ? 'text-fg-2' : 'text-fg-3',
                )}
              >
                {label}
              </span>
            </div>
            {index < steps.length - 1 ? (
              <div className={cn('mx-1 mb-4 h-0.5 flex-1', done ? 'bg-accent' : 'bg-border')} />
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
