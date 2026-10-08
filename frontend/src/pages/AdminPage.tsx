import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Activity, Bot, Building2, CheckCircle2, FileText, Folder, Network, ShieldCheck, Users, WandSparkles } from 'lucide-react'
import { adminApi } from '../api'
import { ErrorState, LoadingState } from '../app/components/PageStates'
import { RunStatusChip } from '../app/components/StatusChip'
import { href, routes } from '../app/core/router'
import { useSession } from '../app/core/session'
import { useAsync } from '../app/core/useAsync'
import type { AsyncState } from '../app/core/useAsync'
import { ENGINE_LABELS, formatDateTime, humanize } from '../shared/format'
import { Card, Chip, DataTable, EmptyState, Input, PageHeader, StatTile, cn } from '../shared/ui'
import { PromptTemplatesPage } from '../features/promptTemplates/PromptTemplatesPage'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'users', label: 'Users' },
  { id: 'workspaces', label: 'Workspaces' },
  { id: 'projects', label: 'Projects' },
  { id: 'generations', label: 'Generations' },
  { id: 'llm-calls', label: 'LLM calls' },
  { id: 'prompts', label: 'Prompt templates' },
  { id: 'audit', label: 'Audit log' },
] as const

export function AdminPage({ tab }: { tab?: string }) {
  const { isSuperAdmin } = useSession()
  const active = TABS.some((item) => item.id === tab) ? tab! : 'overview'

  if (!isSuperAdmin) {
    return <EmptyState icon={ShieldCheck} title="Platform admins only" description="This area is available to SpecTwin platform administrators." />
  }

  return (
    <section className="grid grid-cols-1 gap-5">
      <PageHeader eyebrow="Platform" title="Admin console" description="Everything happening across SpecTwin. Every list you open is recorded in the audit log." />
      <nav className="-mx-1 flex gap-1 overflow-x-auto border-b border-border px-1" aria-label="Admin sections">
        {TABS.map((item) => (
          <a
            key={item.id}
            href={href(routes.admin(item.id === 'overview' ? undefined : item.id))}
            aria-current={item.id === active ? 'page' : undefined}
            className={cn(
              '-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-[13px] font-semibold transition',
              item.id === active ? 'border-accent text-accent' : 'border-transparent text-fg-3 hover:text-fg',
            )}
          >
            {item.label}
          </a>
        ))}
      </nav>
      {active === 'overview' ? <Overview /> : null}
      {active === 'users' ? <UsersTab /> : null}
      {active === 'workspaces' ? <WorkspacesTab /> : null}
      {active === 'projects' ? <ProjectsTab /> : null}
      {active === 'generations' ? <GenerationsTab /> : null}
      {active === 'llm-calls' ? <LlmCallsTab /> : null}
      {active === 'prompts' ? <PromptTemplatesPage /> : null}
      {active === 'audit' ? <AuditTab /> : null}
    </section>
  )
}

function Overview() {
  const overview = useAsync(() => adminApi.overview(), [])
  if (overview.loading && !overview.data) return <LoadingState rows={2} />
  if (overview.error || !overview.data) return <ErrorState message={overview.error ?? 'Unavailable'} onRetry={overview.reload} />
  const data = overview.data
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatTile label="Users" value={data.users} icon={Users} />
      <StatTile label="Workspaces" value={data.workspaces} icon={Building2} />
      <StatTile label="Active projects" value={data.projects} icon={Folder} />
      <StatTile label="Generations" value={data.pipeline_runs} icon={WandSparkles} />
      <StatTile label="Completed generations" value={data.completed_runs} icon={CheckCircle2} />
      <StatTile label="SRS documents" value={data.srs_documents} icon={FileText} />
      <StatTile label="Diagrams" value={data.diagrams} icon={Network} />
      <StatTile label="LLM calls" value={data.llm_calls} icon={Bot} />
    </div>
  )
}

function TableCard<T>({
  state,
  placeholder,
  matches,
  empty,
  head,
  row,
}: {
  state: AsyncState<T[]>
  placeholder: string
  matches: (item: T, needle: string) => boolean
  empty: string
  head: ReactNode
  row: (item: T) => ReactNode
}) {
  const [query, setQuery] = useState('')
  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (state.data ?? []).filter((item) => !needle || matches(item, needle))
  }, [state.data, query, matches])

  if (state.loading && !state.data) return <LoadingState rows={3} />
  if (state.error) return <ErrorState message={state.error} onRetry={state.reload} />

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border p-3">
        <Input inputSize="sm" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={placeholder} className="max-w-xs" aria-label={placeholder} />
        <span className="text-xs text-fg-3">{rows.length} shown</span>
      </div>
      {rows.length ? (
        <DataTable>
          <thead>{head}</thead>
          <tbody>{rows.map(row)}</tbody>
        </DataTable>
      ) : (
        <p className="px-5 py-10 text-center text-[13px] text-fg-3">{empty}</p>
      )}
    </Card>
  )
}

function UsersTab() {
  const users = useAsync(() => adminApi.users(), [])
  return (
    <TableCard
      state={users}
      placeholder="Search users"
      empty="No users."
      matches={(user, needle) => user.full_name.toLowerCase().includes(needle) || user.email.toLowerCase().includes(needle)}
      head={
        <tr>
          <th>Name</th>
          <th>Email</th>
          <th>Role</th>
          <th>Status</th>
          <th>Joined</th>
        </tr>
      }
      row={(user) => (
        <tr key={user.id}>
          <td className="font-semibold text-fg">{user.full_name}</td>
          <td>{user.email}</td>
          <td>{user.platform_role === 'super_admin' ? <Chip tone="accent">Super admin</Chip> : <Chip tone="muted">User</Chip>}</td>
          <td>
            <Chip tone={user.status === 'active' ? 'success' : 'warning'}>{humanize(user.status)}</Chip>
          </td>
          <td className="whitespace-nowrap">{formatDateTime(user.created_at)}</td>
        </tr>
      )}
    />
  )
}

function WorkspacesTab() {
  const workspaces = useAsync(() => adminApi.workspaces(), [])
  return (
    <TableCard
      state={workspaces}
      placeholder="Search workspaces"
      empty="No workspaces."
      matches={(item, needle) => item.name.toLowerCase().includes(needle) || item.slug.includes(needle)}
      head={
        <tr>
          <th>Name</th>
          <th>Slug</th>
          <th>Type</th>
          <th>Created</th>
        </tr>
      }
      row={(item) => (
        <tr key={item.id}>
          <td className="font-semibold text-fg">{item.name}</td>
          <td className="font-mono text-xs">{item.slug}</td>
          <td>
            <Chip tone={item.type === 'organization' ? 'sky' : 'muted'}>{humanize(item.type)}</Chip>
          </td>
          <td className="whitespace-nowrap">{formatDateTime(item.created_at)}</td>
        </tr>
      )}
    />
  )
}

function ProjectsTab() {
  const projects = useAsync(() => adminApi.projects(), [])
  return (
    <TableCard
      state={projects}
      placeholder="Search projects"
      empty="No projects."
      matches={(item, needle) => item.name.toLowerCase().includes(needle)}
      head={
        <tr>
          <th>Name</th>
          <th>Status</th>
          <th>Updated</th>
        </tr>
      }
      row={(item) => (
        <tr key={item.id}>
          <td>
            <span className="font-semibold text-fg">{item.name}</span>
            {item.description ? <span className="block max-w-md truncate text-xs text-fg-3">{item.description}</span> : null}
          </td>
          <td>
            <Chip tone={item.status === 'active' ? 'success' : 'muted'}>{humanize(item.status)}</Chip>
          </td>
          <td className="whitespace-nowrap">{formatDateTime(item.updated_at)}</td>
        </tr>
      )}
    />
  )
}

function GenerationsTab() {
  const runs = useAsync(() => adminApi.pipelineRuns(), [])
  return (
    <TableCard
      state={runs}
      placeholder="Search generations"
      empty="No generations yet."
      matches={(item, needle) => item.title.toLowerCase().includes(needle)}
      head={
        <tr>
          <th>Title</th>
          <th>Engine</th>
          <th>Stage</th>
          <th>Status</th>
          <th>Updated</th>
        </tr>
      }
      row={(item) => (
        <tr key={item.id}>
          <td className="max-w-xs truncate font-semibold text-fg">{item.title}</td>
          <td>
            {ENGINE_LABELS[item.generation_mode] ?? item.generation_mode}
            {item.model_name ? <span className="block text-xs text-fg-3">{item.model_name}</span> : null}
          </td>
          <td>{humanize(item.current_stage)}</td>
          <td>
            <RunStatusChip status={item.status} />
          </td>
          <td className="whitespace-nowrap">{formatDateTime(item.updated_at)}</td>
        </tr>
      )}
    />
  )
}

function LlmCallsTab() {
  const calls = useAsync(() => adminApi.llmCalls(), [])
  return (
    <TableCard
      state={calls}
      placeholder="Search by provider or model"
      empty="No LLM calls have been made yet."
      matches={(item, needle) => item.provider.toLowerCase().includes(needle) || item.model_name.toLowerCase().includes(needle)}
      head={
        <tr>
          <th>Provider</th>
          <th>Model</th>
          <th>Status</th>
          <th>Tokens</th>
          <th>When</th>
        </tr>
      }
      row={(item) => (
        <tr key={item.id}>
          <td>{humanize(item.provider)}</td>
          <td className="font-mono text-xs">{item.model_name}</td>
          <td>
            <Chip tone={item.status === 'completed' ? 'success' : 'danger'}>{humanize(item.status)}</Chip>
            {item.error_message ? <span className="mt-1 block max-w-xs truncate text-xs text-danger">{item.error_message}</span> : null}
          </td>
          <td className="tabular-nums">{item.total_tokens.toLocaleString()}</td>
          <td className="whitespace-nowrap">{formatDateTime(item.created_at)}</td>
        </tr>
      )}
    />
  )
}

function AuditTab() {
  const logs = useAsync(() => adminApi.auditLogs(), [])
  return (
    <TableCard
      state={logs}
      placeholder="Search actions"
      empty="No audit events."
      matches={(item, needle) => item.action.toLowerCase().includes(needle) || item.target_type.toLowerCase().includes(needle)}
      head={
        <tr>
          <th>Action</th>
          <th>Target</th>
          <th>IP</th>
          <th>When</th>
        </tr>
      }
      row={(item) => (
        <tr key={item.id}>
          <td className="font-mono text-xs text-fg">
            <Activity className="mr-1.5 inline size-3.5 text-fg-3" />
            {item.action}
          </td>
          <td>{humanize(item.target_type)}</td>
          <td className="font-mono text-xs">{item.ip_address ?? '—'}</td>
          <td className="whitespace-nowrap">{formatDateTime(item.created_at)}</td>
        </tr>
      )}
    />
  )
}
