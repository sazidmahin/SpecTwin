import { useMemo, useState } from 'react'
import { useAsync } from '../../app/core/useAsync'
import { BrainCircuit, FileText, GitBranch, Search, ShieldCheck } from 'lucide-react'
import { adminApi } from '../../api'
import { Card, Chip, EmptyState, Input, PageHeader, StatTile, cn } from '../../shared/ui'

export function PromptTemplatesPage() {
  const state = useAsync(() => adminApi.promptTemplates(), [])
  const templates = useMemo(() => state.data ?? [], [state.data])
  const isLoading = state.loading
  const error = state.error
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase()
    if (!term) return templates
    return templates.filter(
      (template) =>
        template.name.toLowerCase().includes(term) ||
        template.purpose.toLowerCase().includes(term) ||
        template.template_text.toLowerCase().includes(term),
    )
  }, [query, templates])

  const selectedTemplate = filtered.find((template) => template.id === selectedTemplateId) ?? filtered[0] ?? null
  const activeCount = templates.filter((template) => template.status === 'active').length
  const guardrailCount = templates.filter((template) => template.purpose.includes('guardrail')).length

  return (
    <section className="grid grid-cols-1 gap-6" id="prompt-templates">
      <PageHeader
        eyebrow="Prompt library"
        title="Prompt Templates"
        description="Live prompt templates currently active in the SRS generation pipeline, synced from the database on every run."
        actions={
          <div className="relative min-w-[15rem]">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-fg-3" />
            <Input
              className="pl-9"
              placeholder="Search templates…"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-3">
        <StatTile label="Total templates" value={templates.length} icon={FileText} />
        <StatTile label="Active" value={activeCount} icon={BrainCircuit} />
        <StatTile label="Guardrails" value={guardrailCount} icon={ShieldCheck} />
      </div>

      {error ? (
        <Card className="p-5">
          <EmptyState icon={ShieldCheck} title="Unable to load prompt templates" description={error} />
        </Card>
      ) : isLoading ? (
        <Card className="p-5 text-[13px] text-fg-3">Loading prompt templates…</Card>
      ) : templates.length === 0 ? (
        <Card className="p-5">
          <EmptyState
            icon={FileText}
            title="No prompt templates yet"
            description="Templates appear here once the SRS generation pipeline runs at least once and syncs its prompts to the database."
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[22rem_minmax(0,1fr)]">
          <div className="grid grid-cols-1 content-start gap-3" aria-label="Prompt templates">
            {filtered.map((template) => (
              <button
                key={template.id}
                type="button"
                onClick={() => setSelectedTemplateId(template.id)}
                className={cn(
                  'grid grid-cols-[2.75rem_minmax(0,1fr)] gap-3 rounded-lg border bg-surface p-4 text-left shadow-sm transition',
                  selectedTemplate?.id === template.id ? 'border-accent bg-accent/10' : 'border-border hover:border-border-strong',
                )}
              >
                <div className="grid size-11 place-items-center rounded-md bg-accent/15 text-accent">
                  <GitBranch className="size-5" />
                </div>
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <h2 className="text-sm font-bold text-fg">{template.name}</h2>
                    <span className="rounded bg-surface-3 px-1.5 py-0.5 text-xs font-bold text-fg-3">v{template.version}</span>
                  </div>
                  <div className="mt-3 flex items-center justify-between gap-2">
                    <Chip tone={template.status === 'active' ? 'active' : 'pending'} className="capitalize">
                      {template.status}
                    </Chip>
                    <small className="text-xs font-semibold text-fg-3">{template.purpose}</small>
                  </div>
                </div>
              </button>
            ))}
          </div>

          <Card className="overflow-hidden" aria-label="Selected prompt template">
            {selectedTemplate ? (
              <>
                <div className="flex items-start justify-between gap-3 border-b border-border p-5">
                  <div>
                    <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-accent">{selectedTemplate.purpose}</span>
                    <h2 className="mt-1 font-display text-xl font-bold text-fg">{selectedTemplate.name}</h2>
                  </div>
                  <span className="rounded bg-surface-3 px-2 py-1 text-xs text-fg-2">v{selectedTemplate.version}</span>
                </div>
                <p className="p-5 text-[13px] leading-6 text-fg-2">
                  Last updated {new Date(selectedTemplate.updated_at).toLocaleString()}
                </p>
                <pre className="mx-5 mb-5 max-h-[44rem] overflow-auto rounded-lg bg-sidebar p-4 font-mono text-xs leading-5 text-sidebar-fg-active">
                  <code>{selectedTemplate.template_text}</code>
                </pre>
              </>
            ) : (
              <p className="p-5 text-[13px] text-fg-3">No template matches this search.</p>
            )}
          </Card>
        </div>
      )}
    </section>
  )
}
