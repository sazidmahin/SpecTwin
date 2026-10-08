import type { InputHTMLAttributes, LabelHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { forwardRef } from 'react'
import { cn } from './cn'
import { inputClasses } from './styles'

type InputProps = InputHTMLAttributes<HTMLInputElement> & { inputSize?: 'sm' | 'md' }

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ inputSize = 'md', className, ...props }, ref) {
  return <input ref={ref} className={inputClasses({ size: inputSize, className })} {...props} />
})

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement>

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea({ className, ...props }, ref) {
  return <textarea ref={ref} className={inputClasses({ className: cn('resize-y', className) })} {...props} />
})

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & { inputSize?: 'sm' | 'md' }

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select({ inputSize = 'md', className, ...props }, ref) {
  return <select ref={ref} className={inputClasses({ size: inputSize, className: cn('cursor-pointer', className) })} {...props} />
})

type FieldProps = {
  label: ReactNode
  htmlFor?: string
  hint?: ReactNode
  required?: boolean
  children: ReactNode
  className?: string
}

export function Field({ label, htmlFor, hint, required, children, className }: FieldProps) {
  return (
    <div className={cn('grid gap-1.5', className)}>
      <label htmlFor={htmlFor} className="text-[12.5px] font-semibold text-fg">
        {label}
        {required ? <span className="text-danger"> *</span> : null}
      </label>
      {children}
      {hint ? <p className="text-[11.5px] text-fg-3">{hint}</p> : null}
    </div>
  )
}

export function Label({ className, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn('text-[12.5px] font-semibold text-fg-2', className)} {...props} />
}
