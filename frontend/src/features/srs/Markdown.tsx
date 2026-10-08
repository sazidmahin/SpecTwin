import { Children, isValidElement } from 'react'
import type { ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '../../shared/ui'
import { slugifyHeading } from './markdownHeadings'

function textOf(node: ReactNode): string {
  return Children.toArray(node)
    .map((child) => {
      if (typeof child === 'string' || typeof child === 'number') return String(child)
      if (isValidElement<{ children?: ReactNode }>(child)) return textOf(child.props.children)
      return ''
    })
    .join('')
}

function heading(level: 1 | 2 | 3 | 4) {
  const Tag = `h${level}` as const
  return function MarkdownHeading({ children }: { children?: ReactNode }) {
    return <Tag id={slugifyHeading(textOf(children))}>{children}</Tag>
  }
}

export function Markdown({ content, className }: { content: string; className?: string }) {
  return (
    <div className={cn('srs-prose', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: heading(1),
          h2: heading(2),
          h3: heading(3),
          h4: heading(4),
          table: ({ children }) => (
            <div className="srs-table-wrap">
              <table>{children}</table>
            </div>
          ),
          a: ({ children, href }) => (
            <a href={href} target={href?.startsWith('#') ? undefined : '_blank'} rel="noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
