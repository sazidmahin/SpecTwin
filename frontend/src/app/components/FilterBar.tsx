import type { ReactNode } from 'react'
import { Search } from 'lucide-react'
import type { Project } from '../../api'
import { Card, Select } from '../../shared/ui'

type Props = {
  query: string
  onQueryChange: (value: string) => void
  placeholder: string
  projects?: Project[]
  projectId?: string
  onProjectChange?: (projectId: string) => void
  children?: ReactNode
}

export function FilterBar({ query, onQueryChange, placeholder, projects, projectId, onProjectChange, children }: Props) {
  return (
    <Card className="flex flex-col gap-2.5 p-2.5 sm:flex-row sm:items-center">
      <label className="relative flex flex-1 items-center">
        <Search className="pointer-events-none absolute left-3 size-4 text-fg-3" />
        <input
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder={placeholder}
          aria-label={placeholder}
          className="h-9.5 w-full rounded-lg border border-transparent bg-surface-2 pl-9 pr-3 text-[13px] text-fg outline-none transition placeholder:text-fg-3 focus:border-accent focus:bg-surface focus:ring-4 focus:ring-accent/15"
        />
      </label>
      {projects && onProjectChange ? (
        <Select inputSize="sm" value={projectId ?? ''} onChange={(event) => onProjectChange(event.target.value)} className="h-9.5 sm:w-56" aria-label="Filter by project">
          <option value="">All projects</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </Select>
      ) : null}
      {children}
    </Card>
  )
}
