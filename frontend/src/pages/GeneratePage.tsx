import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowRight, Cpu, KeyRound, Loader2, Play, Plus, Server, Sparkles, WandSparkles } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { aiSettingsApi, errorMessage, pipelineApi, projectApi } from '../api'
import type { GenerationMode, Project } from '../api'
import { ProjectDialog } from '../app/components/ProjectDialog'
import { RunStatusChip } from '../app/components/StatusChip'
import { href, navigate, routes, useRoute } from '../app/core/router'
import { useSession } from '../app/core/session'
import { useAsync } from '../app/core/useAsync'
import { ENGINE_LABELS, relativeTime } from '../shared/format'
import { Button, Card, EmptyState, Field, Input, PageHeader, Select, Textarea, cn, useFeedback } from '../shared/ui'

const EXAMPLES: Array<{ label: string; text: string }> = [
  {
    label: 'Library',
    text:
      'A library management system lets members borrow and reserve books. A librarian can add, update and remove books. ' +
      'Each book has a title, an author and an ISBN. A member has a name, an email and a membership id. ' +
      'A member can borrow up to five books at a time. The system calculates a fine for each overdue loan. ' +
      'The system must respond to searches within 2 seconds.',
  },
  {
    label: 'Clinic',
    text:
      'A clinic appointment system lets patients book, reschedule and cancel appointments with doctors. ' +
      'A doctor has a name, a specialty and a schedule. A receptionist can confirm appointments and register new patients. ' +
      'Patients receive a reminder before each appointment. Only authorised staff can view medical records. ' +
      'The system must be available 99.5% of the time.',
  },
  {
    label: 'Online shop',
    text:
      'Customers can browse products, add products to a cart and place orders. A product has a name, a price and a stock quantity. ' +
      'An order has an order date, a status and a total amount. An admin can add, update and delete products. ' +
      'Customers pay by card and receive an email confirmation. Checkout must complete within 3 seconds.',
  },
]

type EngineOption = { id: GenerationMode; title: string; description: string; icon: LucideIcon; badge: string }

const ENGINES: EngineOption[] = [
  {
    id: 'rule_based',
    title: 'Rule-Based',
    description: 'Deterministic NLP rules. Instant, offline and explainable.',
    icon: Cpu,
    badge: 'No key needed',
  },
  {
    id: 'ollama',
    title: 'Local AI (Ollama)',
    description: 'An open model running in Ollama on your machine. Works without a GPU; each stage takes longer.',
    icon: Server,
    badge: 'No key needed',
  },
  {
    id: 'ai',
    title: 'AI generation',
    description: 'A hosted AI model writes every stage. Fast, high quality and ready to use.',
    icon: WandSparkles,
    badge: 'No key needed',
  },
  {
    id: 'byok',
    title: 'Your AI provider',
    description: 'OpenAI, Anthropic or Gemini using the API key you add in Settings.',
    icon: KeyRound,
    badge: 'Your API key',
  },
]

function defaultTitle(raw: string, projectName?: string) {
  const first = raw.trim().split(/[.!?\n]/)[0]?.trim()
  return (first && first.length > 8 ? first.slice(0, 90) : null) ?? `${projectName ?? 'Project'} requirements`
}

export function GeneratePage() {
  const { workspaceId, canEdit } = useSession()
  const { query } = useRoute()
  const { toast } = useFeedback()
  const projects = useAsync(() => projectApi.list(workspaceId), [workspaceId], Boolean(workspaceId))
  const hosted = useAsync(() => aiSettingsApi.hosted(), [])
  const providers = useAsync(() => aiSettingsApi.providers(), [])
  const recent = useAsync(() => pipelineApi.listWorkspace(workspaceId), [workspaceId], Boolean(workspaceId))

  const [chosenProjectId, setProjectId] = useState('')
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [mode, setMode] = useState<GenerationMode>('rule_based')
  const [creatingProject, setCreatingProject] = useState(false)
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const activeProjects = useMemo(() => (projects.data ?? []).filter((item) => item.status === 'active'), [projects.data])
  const hostedAvailable = Boolean(hosted.data?.available)
  const byokProvider = providers.data?.find((item) => item.credential?.is_default && item.credential.status === 'valid')

  // An explicit choice wins, then ?project= from the link that opened this page, then the first project.
  const requestedProjectId = query.get('project') ?? ''
  const projectId =
    [chosenProjectId, requestedProjectId].find((id) => id && activeProjects.some((item) => item.id === id)) ?? activeProjects[0]?.id ?? ''

  const selectedProject = activeProjects.find((item) => item.id === projectId)
  const blockReason = !canEdit
    ? 'Viewers cannot start generations in this workspace.'
    : !selectedProject
    ? 'Choose a project for this SRS.'
    : !text.trim()
    ? 'Describe the system you want to specify.'
    : text.trim().length < 20
    ? 'Add a little more detail (at least a sentence or two).'
    : mode === 'ai' && !hostedAvailable
    ? 'AI generation is not available right now. Pick another engine.'
    : mode === 'byok' && !byokProvider
    ? 'Add and verify an API key in Settings → AI providers first.'
    : null

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (blockReason || !selectedProject) {
      setError(blockReason)
      return
    }
    setStarting(true)
    setError(null)
    try {
      const run = await pipelineApi.create(workspaceId, selectedProject.id, {
        title: title.trim() || defaultTitle(text, selectedProject.name),
        raw_text: text.trim(),
        generation_mode: mode,
      })
      toast('Generation started', { description: 'Review each stage, then accept it to continue.' })
      navigate(routes.run(selectedProject.id, run.id))
    } catch (caught) {
      setError(errorMessage(caught, 'Unable to start the generation'))
    } finally {
      setStarting(false)
    }
  }

  function onProjectCreated(project: Project) {
    projects.setData((current) => [project, ...(current ?? [])])
    setProjectId(project.id)
  }

  const recentRuns = (recent.data ?? []).slice(0, 5)

  return (
    <section className="grid grid-cols-1 gap-6">
      <PageHeader
        title="Generate SRS"
        description="Describe the system in plain language. SpecTwin turns it into clarifications, user stories, requirements, a class model and a UML diagram — you review every step."
      />

      <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-[minmax(0,1fr)_21rem]">
        <Card className="p-5 sm:p-6">
          <form className="grid grid-cols-1 gap-5" onSubmit={start} noValidate>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Project" htmlFor="generate-project" required>
                <div className="flex gap-2">
                  <Select
                    id="generate-project"
                    value={projectId}
                    onChange={(event) => setProjectId(event.target.value)}
                    disabled={projects.loading || !activeProjects.length}
                  >
                    {!activeProjects.length ? <option value="">{projects.loading ? 'Loading…' : 'No projects yet'}</option> : null}
                    {activeProjects.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </Select>
                  <Button variant="secondary" onClick={() => setCreatingProject(true)} aria-label="New project" className="shrink-0 px-3">
                    <Plus />
                    <span className="hidden sm:inline">New</span>
                  </Button>
                </div>
              </Field>
              <Field label="Title" htmlFor="generate-title" hint="Optional — taken from your first sentence if left blank.">
                <Input
                  id="generate-title"
                  value={title}
                  maxLength={255}
                  placeholder={text ? defaultTitle(text, selectedProject?.name) : 'e.g. Library management SRS'}
                  onChange={(event) => setTitle(event.target.value)}
                />
              </Field>
            </div>

            <Field label="Requirements" htmlFor="generate-text" required>
              <Textarea
                id="generate-text"
                className="min-h-52 leading-relaxed"
                value={text}
                maxLength={200000}
                placeholder="Who uses the system, what should they be able to do, what data does it keep, and what quality constraints apply?"
                onChange={(event) => setText(event.target.value)}
              />
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-xs text-fg-3">Try an example:</span>
                  {EXAMPLES.map((example) => (
                    <button
                      key={example.label}
                      type="button"
                      onClick={() => setText(example.text)}
                      className="rounded-full border border-border bg-surface px-2.5 py-1 text-xs font-semibold text-fg-2 transition hover:border-accent/40 hover:text-accent"
                    >
                      {example.label}
                    </button>
                  ))}
                </div>
                <span className="text-xs tabular-nums text-fg-3">{text.trim().length.toLocaleString()} characters</span>
              </div>
            </Field>

            <fieldset className="grid grid-cols-1 gap-2">
              <legend className="mb-2 text-[12.5px] font-semibold text-fg">Engine</legend>
              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
                {ENGINES.map((engine) => {
                  const Icon = engine.icon
                  const hostedOff = engine.id === 'ai' && !hosted.loading && !hostedAvailable
                  const byokMissing = engine.id === 'byok' && !providers.loading && !byokProvider
                  const selected = mode === engine.id
                  return (
                    <label
                      key={engine.id}
                      className={cn(
                        'relative flex cursor-pointer flex-col gap-2 rounded-xl border-[1.5px] bg-surface p-4 transition',
                        selected ? 'border-accent bg-accent/[0.05] shadow-[var(--ring-accent)]' : 'border-border hover:border-border-strong',
                      )}
                    >
                      <input
                        type="radio"
                        name="engine"
                        value={engine.id}
                        checked={selected}
                        onChange={() => setMode(engine.id)}
                        className="sr-only"
                      />
                      <div className="flex items-center justify-between gap-2">
                        <span className={cn('grid size-9 place-items-center rounded-lg', selected ? 'bg-accent text-white' : 'bg-surface-3 text-fg-2')}>
                          <Icon className="size-[18px]" />
                        </span>
                        <span className="rounded-full bg-surface-3 px-2 py-0.5 text-[10.5px] font-semibold text-fg-2">{engine.badge}</span>
                      </div>
                      <span className="text-[13.5px] font-semibold text-fg">{engine.title}</span>
                      <span className="text-xs leading-relaxed text-fg-3">
                        {engine.id === 'byok' && byokProvider?.credential
                          ? `Uses ${byokProvider.label} · ${byokProvider.credential.selected_model}`
                          : engine.description}
                      </span>
                      {hostedOff ? (
                        <span className="text-xs font-semibold text-fg-3">Not available right now</span>
                      ) : byokMissing ? (
                        <a href={href(routes.settings('ai'))} className="text-xs font-semibold text-accent hover:underline">
                          Add your API key →
                        </a>
                      ) : null}
                    </label>
                  )
                })}
              </div>
            </fieldset>

            <div className="flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center">
              <Button type="submit" size="lg" disabled={starting || Boolean(blockReason)} className="sm:w-auto">
                {starting ? <Loader2 className="animate-spin" /> : <Play />}
                {starting ? 'Starting…' : 'Start generation'}
              </Button>
              {error ? (
                <p className="text-[13px] font-medium text-danger" role="alert">
                  {error}
                </p>
              ) : blockReason ? (
                <p className="text-xs text-fg-3">{blockReason}</p>
              ) : (
                <p className="flex items-center gap-1.5 text-xs text-fg-3">
                  <Sparkles className="size-3.5 text-accent" /> {ENGINE_LABELS[mode]} · six reviewable stages
                </p>
              )}
            </div>
          </form>
        </Card>

        <Card className="p-5">
          <PageHeader
            size="section"
            title="Recent generations"
            actions={
              <a href={href(routes.generations())} className="text-xs font-semibold text-accent hover:text-accent-dim">
                View all
              </a>
            }
          />
          {recent.loading ? (
            <p className="mt-4 text-[13px] text-fg-3">Loading…</p>
          ) : recentRuns.length === 0 ? (
            <EmptyState className="mt-4" title="No generations yet" description="Your runs will appear here so you can continue them later." />
          ) : (
            <ul className="mt-3 grid grid-cols-1 gap-1">
              {recentRuns.map((run) => (
                <li key={run.id}>
                  <a
                    href={href(routes.run(run.project_id, run.id))}
                    className="group flex items-center gap-3 rounded-lg px-2 py-2.5 transition hover:bg-surface-2"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[13px] font-semibold text-fg group-hover:text-accent">{run.title}</div>
                      <div className="truncate text-xs text-fg-3">
                        {run.project_name} · {relativeTime(run.updated_at)}
                      </div>
                    </div>
                    <RunStatusChip status={run.status} />
                    <ArrowRight className="size-4 shrink-0 text-fg-3 transition group-hover:translate-x-0.5 group-hover:text-accent" />
                  </a>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <ProjectDialog open={creatingProject} onOpenChange={setCreatingProject} onSaved={onProjectCreated} />
    </section>
  )
}
