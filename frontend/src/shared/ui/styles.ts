import { cn } from './cn'

export type Tone =
  | 'neutral'
  | 'accent'
  | 'ai'
  | 'active'
  | 'pending'
  | 'danger'
  | 'muted'
  | 'sky'
  | 'success'
  | 'warning'
  | 'info'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'destructive' | 'ai'
type ButtonSize = 'sm' | 'md' | 'lg'

const buttonBase =
  'inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md font-semibold transition-all duration-150 outline-none select-none focus-visible:ring-4 focus-visible:ring-accent/20 active:translate-y-px disabled:pointer-events-none disabled:opacity-55 [&_svg]:size-4 [&_svg]:shrink-0'

const buttonVariants: Record<ButtonVariant, string> = {
  primary:
    'bg-accent text-fg-invert shadow-[0_1px_2px_rgba(16,24,40,0.12),inset_0_1px_0_rgba(255,255,255,0.12)] hover:bg-accent-dim',
  secondary:
    'border border-border-strong bg-surface text-fg shadow-[var(--elev-1)] hover:bg-surface-2 hover:border-fg-3/40',
  ghost: 'text-fg-2 hover:bg-surface-3 hover:text-fg',
  danger: 'border border-danger/25 bg-danger/10 text-danger hover:bg-danger/15',
  destructive: 'bg-danger text-white shadow-[0_1px_2px_rgba(16,24,40,0.12)] hover:brightness-110 dark:text-slate-950',
  ai: 'bg-gradient-to-r from-accent to-accent2-dim text-white shadow-[0_6px_18px_-6px_color-mix(in_oklab,var(--color-accent)_70%,transparent)] hover:brightness-110',
}

const buttonSizes: Record<ButtonSize, string> = {
  sm: 'min-h-8 px-3 py-1.5 text-xs [&_svg]:size-3.5',
  md: 'min-h-9.5 px-4 py-2 text-[13px]',
  lg: 'min-h-11 px-5 py-2.5 text-sm',
}

export type { ButtonVariant, ButtonSize }

export function buttonClasses(options: { variant?: ButtonVariant; size?: ButtonSize; className?: string } = {}) {
  const { variant = 'primary', size = 'md', className } = options
  return cn(buttonBase, buttonVariants[variant], buttonSizes[size], className)
}

export const chipTones: Record<Tone, string> = {
  neutral: 'bg-surface-3 text-fg-2 border-border',
  muted: 'bg-surface-3 text-fg-2 border-border',
  accent: 'bg-accent/10 text-accent border-accent/20',
  ai: 'bg-accent2/10 text-accent2-dim border-accent2/20 dark:text-accent2',
  active: 'bg-success/10 text-success border-success/20',
  success: 'bg-success/10 text-success border-success/20',
  pending: 'bg-warning/10 text-warning border-warning/20',
  warning: 'bg-warning/10 text-warning border-warning/20',
  danger: 'bg-danger/10 text-danger border-danger/20',
  sky: 'bg-sky/10 text-sky border-sky/20',
  info: 'bg-sky/10 text-sky border-sky/20',
}

const controlBase =
  'w-full rounded-md border border-border-strong bg-surface text-fg shadow-[var(--elev-1)] outline-none transition placeholder:text-fg-3 hover:border-fg-3/50 focus:border-accent focus:ring-4 focus:ring-accent/15 disabled:cursor-not-allowed disabled:opacity-60'

export function inputClasses(options: { size?: 'sm' | 'md'; className?: string } = {}) {
  const { size = 'md', className } = options
  return cn(controlBase, size === 'sm' ? 'px-2.5 py-1.5 text-[12.5px]' : 'px-3 py-2 text-[13.5px]', className)
}
