/* eslint-disable react-refresh/only-export-components -- this module re-exports Radix primitives next to their styled wrappers */
import type { ComponentPropsWithoutRef, ReactNode } from 'react'
import { forwardRef } from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import * as TabsPrimitive from '@radix-ui/react-tabs'
import * as SwitchPrimitive from '@radix-ui/react-switch'
import * as DropdownPrimitive from '@radix-ui/react-dropdown-menu'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import * as PopoverPrimitive from '@radix-ui/react-popover'
import { X } from 'lucide-react'
import { cn } from './cn'

/* ── Sheet (right-side slide-over, built on Dialog) ───── */

export const Sheet = DialogPrimitive.Root
export const SheetTrigger = DialogPrimitive.Trigger
export const SheetClose = DialogPrimitive.Close

type SheetContentProps = ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
  title: string
  description?: string
  footer?: ReactNode
  width?: string
}

export function SheetContent({ title, description, footer, width = 'w-[420px]', className, children, ...props }: SheetContentProps) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-slate-950/45 backdrop-blur-[3px] data-[state=open]:animate-fade-in" />
      <DialogPrimitive.Content
        className={cn(
          'fixed inset-y-0 right-0 z-50 flex max-w-[94vw] flex-col border-l border-border bg-surface shadow-[var(--elev-3)] transition-transform duration-300 ease-out data-[state=closed]:translate-x-full',
          width,
          className,
        )}
        {...props}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4">
          <div>
            <DialogPrimitive.Title className="font-display text-[17px] font-bold text-fg">{title}</DialogPrimitive.Title>
            {description ? (
              <DialogPrimitive.Description className="mt-1 text-xs text-fg-2">{description}</DialogPrimitive.Description>
            ) : null}
          </div>
          <DialogPrimitive.Close
            className="grid size-8 shrink-0 place-items-center rounded-md text-fg-2 transition hover:bg-surface-3 hover:text-fg"
            aria-label="Close"
          >
            <X className="size-4" />
          </DialogPrimitive.Close>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>
        {footer ? <div className="flex gap-2.5 border-t border-border px-5 py-4">{footer}</div> : null}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
}

/* ── Modal (centered dialog) ─────────────────────────── */

export const Modal = DialogPrimitive.Root
export const ModalTrigger = DialogPrimitive.Trigger
export const ModalClose = DialogPrimitive.Close

type ModalContentProps = ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
  title: string
  description?: string
}

export function ModalContent({ title, description, className, children, ...props }: ModalContentProps) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-slate-950/45 backdrop-blur-[3px] data-[state=open]:animate-fade-in" />
      <DialogPrimitive.Content
        className={cn(
          'fixed left-1/2 top-1/2 z-50 max-h-[90svh] w-[94vw] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-2xl border border-border bg-surface p-6 shadow-[var(--elev-3)] data-[state=open]:animate-rise-in',
          className,
        )}
        {...props}
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <DialogPrimitive.Title className="font-display text-lg font-bold text-fg">{title}</DialogPrimitive.Title>
            {description ? (
              <DialogPrimitive.Description className="mt-1 text-[13px] text-fg-2">{description}</DialogPrimitive.Description>
            ) : null}
          </div>
          <DialogPrimitive.Close
            className="grid size-8 shrink-0 place-items-center rounded-md text-fg-2 transition hover:bg-surface-3 hover:text-fg"
            aria-label="Close"
          >
            <X className="size-4" />
          </DialogPrimitive.Close>
        </div>
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  )
}

/* ── Tabs (pill switcher) ────────────────────────────── */

export const Tabs = TabsPrimitive.Root
export const TabsContent = TabsPrimitive.Content

export const TabsList = forwardRef<HTMLDivElement, ComponentPropsWithoutRef<typeof TabsPrimitive.List>>(
  function TabsList({ className, ...props }, ref) {
    return (
      <TabsPrimitive.List
        ref={ref}
        className={cn('inline-flex max-w-full items-center gap-0.5 overflow-x-auto rounded-lg border border-border bg-surface-3 p-1', className)}
        {...props}
      />
    )
  },
)

export const TabsTrigger = forwardRef<HTMLButtonElement, ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>>(
  function TabsTrigger({ className, ...props }, ref) {
    return (
      <TabsPrimitive.Trigger
        ref={ref}
        className={cn(
          'whitespace-nowrap rounded-md px-3.5 py-1.5 text-[13px] font-semibold text-fg-3 outline-none transition hover:text-fg focus-visible:ring-2 focus-visible:ring-accent/40',
          'data-[state=active]:bg-surface data-[state=active]:text-fg data-[state=active]:shadow-[var(--elev-1)]',
          className,
        )}
        {...props}
      />
    )
  },
)

/* ── Switch ──────────────────────────────────────────── */

export const Switch = forwardRef<HTMLButtonElement, ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>>(
  function Switch({ className, ...props }, ref) {
    return (
      <SwitchPrimitive.Root
        ref={ref}
        className={cn(
          'relative h-[22px] w-9 shrink-0 rounded-full border border-border bg-surface-3 outline-none transition focus-visible:ring-2 focus-visible:ring-accent/40 data-[state=checked]:border-accent data-[state=checked]:bg-accent',
          className,
        )}
        {...props}
      >
        <SwitchPrimitive.Thumb className="block size-4 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-[18px]" />
      </SwitchPrimitive.Root>
    )
  },
)

/* ── DropdownMenu ────────────────────────────────────── */

export const DropdownMenu = DropdownPrimitive.Root
export const DropdownMenuTrigger = DropdownPrimitive.Trigger
export const DropdownMenuSeparator = () => <DropdownPrimitive.Separator className="my-1 h-px bg-border" />

export const DropdownMenuContent = forwardRef<HTMLDivElement, ComponentPropsWithoutRef<typeof DropdownPrimitive.Content>>(
  function DropdownMenuContent({ className, sideOffset = 6, ...props }, ref) {
    return (
      <DropdownPrimitive.Portal>
        <DropdownPrimitive.Content
          ref={ref}
          sideOffset={sideOffset}
          className={cn(
            'z-50 min-w-[11rem] rounded-lg border border-border bg-surface p-1 shadow-[var(--elev-3)] data-[state=open]:animate-fade-in',
            className,
          )}
          {...props}
        />
      </DropdownPrimitive.Portal>
    )
  },
)

export const DropdownMenuItem = forwardRef<HTMLDivElement, ComponentPropsWithoutRef<typeof DropdownPrimitive.Item>>(
  function DropdownMenuItem({ className, ...props }, ref) {
    return (
      <DropdownPrimitive.Item
        ref={ref}
        className={cn(
          'flex cursor-pointer items-center gap-2 rounded-md px-2.5 py-2 text-[13px] text-fg-2 outline-none transition data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[highlighted]:bg-surface-3 data-[highlighted]:text-fg [&_svg]:size-4',
          className,
        )}
        {...props}
      />
    )
  },
)

/* ── Tooltip ─────────────────────────────────────────── */

export const TooltipProvider = TooltipPrimitive.Provider

export function Tooltip({ content, children }: { content: ReactNode; children: ReactNode }) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          sideOffset={6}
          className="z-50 rounded-md bg-slate-900 px-2 py-1 text-[11px] font-medium text-white shadow-[var(--elev-2)] dark:bg-slate-700"
        >
          {content}
          <TooltipPrimitive.Arrow className="fill-slate-900 dark:fill-slate-700" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  )
}

/* ── Popover ─────────────────────────────────────────── */

export const Popover = PopoverPrimitive.Root
export const PopoverTrigger = PopoverPrimitive.Trigger

export const PopoverContent = forwardRef<HTMLDivElement, ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>>(
  function PopoverContent({ className, sideOffset = 6, ...props }, ref) {
    return (
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          ref={ref}
          sideOffset={sideOffset}
          className={cn(
            'z-50 rounded-lg border border-border bg-surface p-3 shadow-[var(--elev-3)] data-[state=open]:animate-fade-in',
            className,
          )}
          {...props}
        />
      </PopoverPrimitive.Portal>
    )
  },
)
