import { useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import {
  AlertTriangle,
  ArrowRight,
  Boxes,
  CheckCircle2,
  Cpu,
  Download,
  FileCode2,
  FileImage,
  GitCompareArrows,
  History,
  ImageDown,
  ListTree,
  Loader2,
  Network,
  RefreshCw,
  Server,
  KeyRound,
  Pencil,
  Eye,
  BrainCircuit,
  Save,
  Sparkles,
  Table2,
  WandSparkles,
} from 'lucide-react'
import { aiSettingsApi, classModelerApi, diagramApi } from '../../api'
import type { ClassModelerMode, ClassModelerResult, LlmProvider, ModelClass, ModelEnum, ModelRelationship, OllamaModels, Project } from '../../api'
import { useSession } from '../../app/core/session'
import { useAsync } from '../../app/core/useAsync'
import { navigate, routes } from '../../app/core/router'
import { downloadDataUrl, downloadTextFile } from '../../shared/download'
import { Button, Chip, Select, Tabs, TabsContent, TabsList, TabsTrigger, Textarea, cn, useFeedback } from '../../shared/ui'
import { DrawioEmbed, type DrawioEmbedHandle } from '../diagram/DrawioEmbed'
import { Breakdown } from './Breakdown'
import { CompareView } from './CompareView'
import { buildDrawioXml } from '../diagram/drawioXml'
import { classModelSignature, parseDrawioClassModel } from '../diagram/drawioModel'
import { ClassModelEditor } from './ClassModelEditor'
import type { ClassModel } from './modelEdits'
import { ClassDiagramCanvas } from './diagram/ClassDiagramCanvas'
import type { ClassDiagramHandle } from './diagram/ClassDiagramCanvas'
import { methodSignature } from './diagram/layout'
import { RelationshipGlyph, RelationshipLegend } from './RelationshipLegend'
import { explainRelationship } from './relationshipGuide'

type Props = {
  projects: Project[]
}

type Engine = ClassModelerMode | 'compare'

/** One generation, kept for the session so any two runs can be compared. */
type Run = {
  id: string
  number: number
  mode: ClassModelerMode
  createdAt: Date
  text: string
  result: ClassModelerResult
  /** What the engine produced, kept so an edit can be taught back to it. */
  generated: ClassModelerResult['model']
  edited: boolean
}

const MAX_RUNS = 12

const MODE_LABELS: Record<ClassModelerMode, string> = { rule_based: 'Rule-based', llm: 'LLM', ai: 'AI generation' }

function ModeIcon({ mode, className }: { mode: ClassModelerMode; className?: string }) {
  const Icon = mode === 'ai' ? WandSparkles : mode === 'llm' ? Sparkles : Cpu
  return <Icon className={className} />
}

function runLabel(run: Run) {
  const engine = run.mode === 'llm' && run.result.modelName ? `LLM (${run.result.modelName})` : MODE_LABELS[run.mode]
  return `#${run.number} ${engine}`
}

function fileStem(result: ClassModelerResult) {
  const first = result.model.classes[0]?.name ?? 'class'
  return `${first.replace(/[^A-Za-z0-9]+/g, '-').toLowerCase()}-diagram-${result.mode === 'rule_based' ? 'rule' : result.mode}`
}

const samples: { label: string; text: string }[] = [
  {
    label: 'Library',
    text:
      'Design a library management system. The library has many books. Each book has a title, an author, an ISBN and a publication year. ' +
      'A book can be available, borrowed or lost. A library member has a name, an email and a membership id. A member can borrow up to five books. ' +
      'Members can also reserve books. A librarian is a kind of staff member. A staff member has an employee id and a salary. ' +
      'The librarian can add, remove and update books. A loan records the borrow date and the due date. Each loan belongs to exactly one member. ' +
      'The system calculates the fine for each loan.',
  },
  {
    label: 'Bank (inheritance)',
    text:
      'Design a banking system. A bank has many customers. A customer has a name, an address and a phone number. A customer can open one or more accounts. ' +
      'There are two types of accounts: savings accounts and current accounts. A savings account has an account number, a balance and an interest rate. ' +
      'A current account has an account number, a balance and an overdraft limit. A customer can deposit money and withdraw money. ' +
      'The bank calculates the interest for each savings account. Each account contains many transactions. A transaction has an amount and a date.',
  },
  {
    label: 'Payments (interface)',
    text:
      'Design a payment system. Payable is an interface with methods pay and refund. Credit card payments and cash payments implement Payable. ' +
      'A credit card payment has a card number, an expiry date and an amount. A cash payment has an amount. ' +
      'Shape is an abstract class. Circles and rectangles are shapes. A circle has a radius. A rectangle has a width and a height. ' +
      'Every shape can calculate its area. Drawable is an interface. Circle implements Drawable.',
  },
  {
    label: 'Online shop',
    text:
      'Develop an online shopping application. Customers can browse products and add products to a shopping cart. A product has a name, a price and a stock quantity. ' +
      'A shopping cart contains one or more cart items. Each cart item has a quantity. An order is placed by a customer. An order has an order date and a total amount. ' +
      'The status of an order can be pending, shipped or delivered. An admin can add, update and delete products. Customers and admins are users. A user has an email and a password.',
  },
  {
    label: 'University',
    text:
      'A university has many departments. Each department offers several courses. A course has a course code, a title and credits. ' +
      'A student has a student id, a name and a GPA. A student can enroll in up to six courses. A teacher teaches one or more courses. ' +
      'Students and teachers are persons. A person has a name and an email. A teacher can grade students.',
  },
]

const engines: { id: Engine; title: string; description: string; icon: LucideIcon; badge: string }[] = [
  {
    id: 'rule_based',
    title: 'Rule-based',
    description: 'Offline noun/verb analysis. Same text, same answer - every decision explained.',
    icon: Cpu,
    badge: 'Instant',
  },
  {
    id: 'llm',
    title: 'LLM-based',
    description: 'A local Ollama model reads the task and designs the model.',
    icon: Sparkles,
    badge: 'Local',
  },
  {
    id: 'ai',
    title: 'AI generation',
    description: 'A hosted AI model reads the task and designs the model. No API key or local setup needed.',
    icon: WandSparkles,
    badge: 'AI',
  },
  {
    id: 'compare',
    title: 'Compare both',
    description: 'Run both engines and see where they agree and differ, side by side.',
    icon: GitCompareArrows,
    badge: 'Side by side',
  },
]

function errorMessage(caught: unknown, fallback: string) {
  return caught instanceof Error && caught.message ? caught.message : fallback
}

export function ClassModelerPage({ projects }: Props) {
  const { workspaceId } = useSession()
  const { toast } = useFeedback()
  const [projectId, setProjectId] = useState(projects[0]?.id ?? '')
  const activeProject = projects.find((item) => item.id === projectId)
  const [text, setText] = useState(samples[0].text)
  const [engine, setEngine] = useState<Engine>('rule_based')
  const [llmProvider, setLlmProvider] = useState<LlmProvider>('ollama')
  const [ollamaModel, setOllamaModel] = useState('')
  const [ollama, setOllama] = useState<OllamaModels | null>(null)
  const [isLoadingModels, setIsLoadingModels] = useState(false)
  const [runs, setRuns] = useState<Run[]>([])
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [comparePair, setComparePair] = useState<[string, string] | null>(null)
  const [errors, setErrors] = useState<Partial<Record<ClassModelerMode, string>>>({})
  const [tab, setTab] = useState('diagram')
  const [running, setRunning] = useState<ClassModelerMode[]>([])
  const [isSaving, setIsSaving] = useState(false)
  const [isRemembering, setIsRemembering] = useState(false)
  const [editing, setEditing] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const drawioRef = useRef<DrawioEmbedHandle>(null)
  const canvasRef = useRef<ClassDiagramHandle>(null)
  const runCounter = useRef(0)
  // The hosted engine is hidden rather than offered-then-refused when the
  // platform ships no key (see GET /users/me/ai-settings/hosted).
  const hosted = useAsync(() => aiSettingsApi.hosted(), [])
  const hostedAvailable = Boolean(hosted.data?.available)

  const needsProject = engine !== 'rule_based' && !activeProject
  // With Ollama chosen, only an installed model can run (nothing is picked
  // until the server has answered with its model list). "Compare both" always
  // pairs the rule engine with Ollama.
  const usesOllama = (engine === 'llm' && llmProvider === 'ollama') || engine === 'compare'
  const ollamaMissing = usesOllama && !ollamaModel
  const hostedMissing = engine === 'ai' && !hosted.loading && !hostedAvailable
  const activeRun = runs.find((run) => run.id === activeRunId) ?? runs[0]
  const result = activeRun?.result
  const isGenerating = running.length > 0
  const canCompare = runs.length >= 2
  const pair = comparePair ?? (runs.length >= 2 ? ([runs[1].id, runs[0].id] as [string, string]) : null)
  const leftRun = pair ? runs.find((run) => run.id === pair[0]) : undefined
  const rightRun = pair ? runs.find((run) => run.id === pair[1]) : undefined

  async function run(mode: ClassModelerMode): Promise<Run | null> {
    setRunning((current) => [...current, mode])
    setErrors((current) => ({ ...current, [mode]: undefined }))
    try {
      const next = await classModelerApi.generate(workspaceId, {
        text,
        mode,
        ...(activeProject ? { project_id: activeProject.id } : {}),
        ...(mode === 'llm'
          ? { llm_provider: llmProvider, ...(llmProvider === 'ollama' && ollamaModel ? { model_name: ollamaModel } : {}) }
          : {}),
      })
      runCounter.current += 1
      const record: Run = {
        id: `run-${runCounter.current}`,
        number: runCounter.current,
        mode,
        createdAt: new Date(),
        text,
        result: next,
        generated: next.model,
        edited: false,
      }
      setRuns((current) => [record, ...current].slice(0, MAX_RUNS))
      return record
    } catch (caught) {
      setErrors((current) => ({ ...current, [mode]: errorMessage(caught, 'Generation failed') }))
      return null
    } finally {
      setRunning((current) => current.filter((item) => item !== mode))
    }
  }

  async function loadOllamaModels() {
    if (!workspaceId) return
    setIsLoadingModels(true)
    try {
      const status = await classModelerApi.ollamaModels(workspaceId)
      setOllama(status)
      setOllamaModel((current) => {
        if (current && status.installed.includes(current)) return current
        if (status.defaultModel && status.installed.includes(status.defaultModel)) return status.defaultModel
        return status.installed[0] ?? status.defaultModel ?? ''
      })
    } catch (caught) {
      setOllama({ reachable: false, installed: [], suggested: [], defaultModel: null, error: errorMessage(caught, 'Could not check Ollama') })
    } finally {
      setIsLoadingModels(false)
    }
  }

  /** Replace the active run's model and keep the draw.io XML in step.
   *
   * `xml` is given only when the change came *from* draw.io: the editor already
   * holds that exact text, so storing it verbatim leaves DrawioEmbed's guard
   * satisfied and the user's layout untouched. A change from the Classes editor
   * has no XML yet, so one is generated - which does reload the editor, because
   * the structure really did change.
   */
  function applyModel(next: ClassModel, xml?: string) {
    setRuns((current) =>
      current.map((item) =>
        item.id !== (activeRun?.id ?? '')
          ? item
          : {
              ...item,
              edited: true,
              result: { ...item.result, model: next, drawioXml: xml ?? buildDrawioXml(next) },
            },
      ),
    )
  }

  /** draw.io autosaves on every change, and most changes are not model changes.
   *
   * Dragging a box is still worth keeping - it is the user's arrangement, and it
   * would otherwise be lost the next time the editor remounts - so the XML is
   * always stored. Only a change to the model itself re-reads the model and
   * counts as an edit, so moving a box never offers to teach the engine a "fix".
   */
  function applyDrawioEdit(xml: string) {
    if (!activeRun) return
    const parsed = parseDrawioClassModel(xml)
    if (parsed && classModelSignature(parsed.model) !== classModelSignature(activeRun.result.model)) {
      applyModel(parsed.model, xml)
      return
    }
    setRuns((current) =>
      current.map((item) => (item.id === activeRun.id ? { ...item, result: { ...item.result, drawioXml: xml } } : item)),
    )
  }

  async function rememberFix() {
    if (!activeRun || !workspaceId || !activeProject) return
    setIsRemembering(true)
    try {
      const { remembered } = await classModelerApi.rememberCorrection(workspaceId, {
        text: activeRun.text,
        project_id: activeProject.id,
        generation_mode: activeRun.result.provider === 'ai' ? 'ai' : activeRun.result.provider === 'ollama' ? 'ollama' : 'byok',
        wrong_model: activeRun.generated,
        corrected_model: activeRun.result.model,
      })
      toast(
        remembered ? 'Fix remembered' : 'Nothing to remember',
        remembered
          ? { description: 'The next model generated from this text will be shown this correction.' }
          : { description: 'Correction memory is switched off on this server, so nothing was stored.', tone: 'error' },
      )
    } catch (caught) {
      toast('Could not save the fix', { description: errorMessage(caught, 'Request failed'), tone: 'error' })
    } finally {
      setIsRemembering(false)
    }
  }

  function chooseEngine(next: Engine) {
    setEngine(next)
    if (((next === 'llm' && llmProvider === 'ollama') || next === 'compare') && !ollama && !isLoadingModels) void loadOllamaModels()
  }

  function chooseProvider(next: LlmProvider) {
    setLlmProvider(next)
    if (next === 'ollama' && !ollama && !isLoadingModels) void loadOllamaModels()
  }

  async function handleGenerate(event: FormEvent) {
    event.preventDefault()
    if (!workspaceId || !text.trim()) return
    setNotice(null)
    if (engine === 'compare') {
      const [rule, llm] = await Promise.all([run('rule_based'), run('llm')])
      const shown = rule ?? llm
      if (shown) setActiveRunId(shown.id)
      if (rule && llm) {
        setComparePair([rule.id, llm.id])
        setTab('compare')
      } else {
        setTab('diagram')
      }
      return
    }
    const next = await run(engine)
    if (next) {
      setActiveRunId(next.id)
      if (tab === 'compare') setTab('diagram')
    }
  }

  async function handleSave() {
    if (!result || !workspaceId || !activeProject) return
    setIsSaving(true)
    try {
      const firstClass = result.model.classes[0]?.name ?? 'Domain'
      const saved = await diagramApi.create(workspaceId, activeProject.id, {
        title: `${firstClass} class model (${MODE_LABELS[result.mode]})`,
        diagram_type: 'class',
        drawio_xml: result.drawioXml,
      })
      setNotice(`Saved to ${activeProject.name} → Diagrams.`)
      toast('Diagram saved', { description: `Open it from ${activeProject.name} → Diagrams.` })
      void saved
    } catch (caught) {
      setErrors((current) => ({ ...current, [result.mode]: errorMessage(caught, 'Unable to save the diagram') }))
    } finally {
      setIsSaving(false)
    }
  }

  function requireCanvas() {
    if (!canvasRef.current) {
      setTab('diagram')
      setNotice('Open the Diagram tab, then download again.')
      return null
    }
    return canvasRef.current
  }

  async function handlePng() {
    if (!result) return
    const canvas = requireCanvas()
    if (!canvas) return
    try {
      downloadDataUrl(`${fileStem(result)}.png`, await canvas.exportPng())
    } catch (caught) {
      setErrors((current) => ({ ...current, [result.mode]: errorMessage(caught, 'Unable to export PNG') }))
    }
  }

  function handleSvg() {
    if (!result) return
    const canvas = requireCanvas()
    if (!canvas) return
    downloadTextFile(`${fileStem(result)}.svg`, canvas.exportSvg().svg, 'image/svg+xml')
  }

  async function handleDrawioPng() {
    if (!result) return
    try {
      const dataUrl = await drawioRef.current?.exportImage('png')
      if (dataUrl) downloadDataUrl(`${fileStem(result)}-drawio.png`, dataUrl)
    } catch (caught) {
      setErrors((current) => ({ ...current, [result.mode]: errorMessage(caught, 'The draw.io preview is not ready yet') }))
    }
  }

  const visibleErrors = Object.entries(errors).filter(([, message]) => message) as [ClassModelerMode, string][]

  return (
    <section className="grid grid-cols-1 gap-6">
      {/* ── Hero ─────────────────────────────────────── */}
      <div className="relative overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-accent/12 via-surface to-accent2/12 px-6 py-7 sm:px-8">
        <div className="pointer-events-none absolute -right-16 -top-20 size-64 rounded-full bg-accent2/15 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 left-1/3 size-56 rounded-full bg-accent/15 blur-3xl" />
        <div className="relative flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-2xl">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-accent/30 bg-surface/70 px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.12em] text-accent-dim backdrop-blur">
              <Boxes className="size-3.5" /> OOP analysis
            </span>
            <h1 className="mt-3 font-display text-3xl font-extrabold tracking-tight text-fg">Class Diagram Generation</h1>
            <p className="mt-2 text-[14px] leading-relaxed text-fg-2">
              Paste an OOP-course style task. It is broken down sentence by sentence into nouns and verbs, then into classes,
              attributes, methods, inheritance, interfaces and relationships - and drawn as a UML class diagram you can explore.
            </p>
          </div>
          <ol className="flex flex-wrap items-center gap-2 text-[12px] font-semibold text-fg-2">
            {['Write the task', 'Pick an engine', 'Explore the diagram'].map((step, index) => (
              <li key={step} className="flex items-center gap-2">
                <span className="flex items-center gap-2 rounded-full border border-border bg-surface/80 px-3 py-1.5 shadow-xs backdrop-blur">
                  <span className="grid size-5 place-items-center rounded-full bg-accent text-[10.5px] font-bold text-fg-invert">{index + 1}</span>
                  {step}
                </span>
                {index < 2 ? <ArrowRight className="size-3.5 text-fg-3" /> : null}
              </li>
            ))}
          </ol>
        </div>
      </div>

      {/* ── Input ────────────────────────────────────── */}
      <form onSubmit={handleGenerate} className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="grid grid-cols-1 gap-3 rounded-2xl border border-border bg-surface p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label htmlFor="class-modeler-text" className="font-display text-[15px] font-bold text-fg">
              Requirement / task statement
            </label>
            <span className="text-[11px] text-fg-3">{text.trim().split(/[.!?]+\s/).filter(Boolean).length} sentences · {text.length} chars</span>
          </div>
          <Textarea
            id="class-modeler-text"
            rows={9}
            value={text}
            onChange={(event) => setText(event.target.value)}
            className="min-h-52 resize-y rounded-xl bg-surface-2 font-mono text-[13px] leading-relaxed"
            placeholder="A library has many books. Each book has a title and an ISBN. A member can borrow up to five books…"
          />
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-[11.5px] font-semibold text-fg-3">Try an example</span>
            {samples.map((sample) => (
              <button
                key={sample.label}
                type="button"
                onClick={() => setText(sample.text)}
                className={cn(
                  'rounded-full border px-3 py-1 text-[12px] font-semibold transition',
                  text === sample.text
                    ? 'border-accent bg-accent/10 text-accent-dim'
                    : 'border-border bg-surface-2 text-fg-2 hover:border-border-strong hover:text-fg',
                )}
              >
                {sample.label}
              </button>
            ))}
          </div>
          <p className="text-[11.5px] text-fg-3">
            Tip: one idea per sentence works best - "A book has a title.", "A librarian is a kind of staff member.",
            "Payable is an interface with methods pay and refund."
          </p>
        </div>

        <div className="grid grid-cols-1 content-start gap-3 rounded-2xl border border-border bg-surface p-5 shadow-sm">
          <span className="font-display text-[15px] font-bold text-fg">Engine</span>
          <div role="radiogroup" className="grid grid-cols-1 gap-2">
            {engines.map((item) => {
              const active = engine === item.id
              const unavailable = item.id === 'ai' && !hosted.loading && !hostedAvailable
              return (
                <button
                  key={item.id}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => chooseEngine(item.id)}
                  className={cn(
                    'group flex items-start gap-3 rounded-xl border-[1.5px] px-3.5 py-3 text-left transition',
                    active ? 'border-accent bg-accent/8 shadow-sm' : 'border-border hover:border-border-strong hover:bg-surface-2',
                  )}
                >
                  <span
                    className={cn(
                      'grid size-9 shrink-0 place-items-center rounded-lg transition',
                      active ? 'bg-accent text-fg-invert' : 'bg-surface-3 text-fg-2 group-hover:text-fg',
                    )}
                  >
                    <item.icon className="size-4.5" />
                  </span>
                  <span className="min-w-0">
                    <span className="flex items-center gap-1.5">
                      <span className="text-[13.5px] font-bold text-fg">{item.title}</span>
                      <span className="rounded-full bg-fg/5 px-1.5 py-px text-[9.5px] font-bold uppercase tracking-[0.06em] text-fg-3">
                        {unavailable ? 'Unavailable' : item.badge}
                      </span>
                    </span>
                    <span className="mt-0.5 block text-[11.5px] leading-snug text-fg-3">{item.description}</span>
                  </span>
                </button>
              )
            })}
          </div>
          {engine === 'llm' ? (
            <div className="grid grid-cols-1 gap-2.5 rounded-xl border border-border bg-surface-2 p-3">
              <span className="text-[11px] font-bold uppercase tracking-[0.08em] text-fg-3">LLM provider</span>
              <div className="grid grid-cols-2 gap-1 rounded-lg bg-surface-3 p-1">
                {(
                  [
                    { id: 'ollama', label: 'Ollama (local)', icon: Server },
                    { id: 'byok', label: 'My AI provider', icon: KeyRound },
                  ] as const
                ).map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => chooseProvider(option.id)}
                    className={cn(
                      'flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-[12px] font-semibold transition',
                      llmProvider === option.id ? 'bg-surface text-fg shadow-sm' : 'text-fg-3 hover:text-fg',
                    )}
                  >
                    <option.icon className="size-3.5" />
                    {option.label}
                  </button>
                ))}
              </div>
              {llmProvider === 'byok' ? (
                <p className="text-[11.5px] leading-snug text-fg-3">
                  Uses the active provider you added and tested in Settings → AI providers (OpenAI, Claude or Gemini).
                </p>
              ) : null}
            </div>
          ) : null}
          {usesOllama ? (
            <div className="grid grid-cols-1 gap-2.5 rounded-xl border border-border bg-surface-2 p-3">
              <span className="text-[11px] font-bold uppercase tracking-[0.08em] text-fg-3">Ollama model</span>
              <div className="grid grid-cols-1 gap-1.5">
                <div className="flex items-center justify-between gap-2">
                  <label htmlFor="ollama-model" className="text-[11.5px] font-semibold text-fg-2">
                    Model
                  </label>
                  <button
                    type="button"
                    onClick={() => void loadOllamaModels()}
                    className="flex items-center gap-1 text-[11px] font-semibold text-fg-3 transition hover:text-fg"
                  >
                    <RefreshCw className={cn('size-3', isLoadingModels && 'animate-spin')} /> Refresh
                  </button>
                </div>
                {ollama?.reachable && ollama.installed.length ? (
                  <Select id="ollama-model" value={ollamaModel} onChange={(event) => setOllamaModel(event.target.value)}>
                    {ollama.installed.map((name) => (
                      <option key={name} value={name}>
                        {name}
                        {name === ollama.defaultModel ? ' (default)' : ''}
                      </option>
                    ))}
                  </Select>
                ) : isLoadingModels ? (
                  <p className="text-[11.5px] text-fg-3">Checking the local Ollama server…</p>
                ) : ollama ? (
                  <p className="flex gap-1.5 rounded-lg border border-warning/30 bg-warning/10 px-2.5 py-2 text-[11.5px] leading-snug text-fg-2">
                    <AlertTriangle className="mt-px size-3.5 shrink-0 text-warning" />
                    <span>
                      {ollama.reachable ? 'Ollama is running but no model is installed.' : 'Ollama is not reachable.'} Start it
                      and pull a model, e.g. <code className="rounded bg-surface px-1 font-mono">ollama pull {ollama.defaultModel ?? 'llama3.2'}</code>,
                      then Refresh.
                    </span>
                  </p>
                ) : null}
                <p className="text-[10.5px] leading-snug text-fg-3">
                  Runs on your machine, no API key. Small models (1-3B) are fast but may miss details; 7B+ gives better class models.
                </p>
              </div>
            </div>
          ) : null}
          <label className="grid grid-cols-1 gap-1.5">
            <span className="text-[12px] font-semibold text-fg">Project</span>
            <Select value={projectId} onChange={(event) => setProjectId(event.target.value)} inputSize="sm" aria-label="Project for saving and LLM logging">
              {!projects.length ? <option value="">No projects yet</option> : null}
              {projects.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </Select>
            {!projects.length ? (
              <button type="button" className="w-max text-[11.5px] font-semibold text-accent hover:underline" onClick={() => navigate(routes.projects(), { new: '1' })}>
                Create a project
              </button>
            ) : null}
          </label>
          {hostedMissing ? (
            <p className="flex gap-1.5 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-[11.5px] text-fg-2">
              <AlertTriangle className="mt-px size-3.5 shrink-0 text-warning" />
              AI generation is not available right now. Pick Rule-based, or an LLM engine.
            </p>
          ) : needsProject ? (
            <p className="flex gap-1.5 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-[11.5px] text-fg-2">
              <AlertTriangle className="mt-px size-3.5 shrink-0 text-warning" />
              Select a project first - LLM calls are logged per project.
            </p>
          ) : engine !== 'rule_based' && activeProject ? (
            <p className="text-[11.5px] text-fg-3">LLM usage is logged under {activeProject.name}.</p>
          ) : null}
          <Button
            type="submit"
            size="lg"
            variant={engine === 'rule_based' ? 'primary' : 'ai'}
            disabled={isGenerating || !workspaceId || !text.trim() || needsProject || ollamaMissing || hostedMissing}
            className="mt-1 w-full"
          >
            {isGenerating ? <Loader2 className="animate-spin" /> : <WandSparkles />}
            {isGenerating
              ? running.length > 1
                ? 'Running both engines…'
                : running[0] === 'llm'
                  ? llmProvider === 'ollama'
                    ? `Asking ${ollamaModel || 'Ollama'}… (local models can take a minute)`
                    : 'Asking the LLM…'
                  : running[0] === 'ai'
                    ? 'Generating with AI…'
                    : 'Analysing…'
              : engine === 'compare'
                ? 'Generate & compare'
                : 'Generate class model'}
          </Button>
        </div>
      </form>

      {visibleErrors.map(([mode, message]) => (
        <p key={mode} className="flex items-start gap-2 rounded-xl border border-danger/25 bg-danger/10 px-4 py-3 text-[13px] text-danger">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <span>
            <strong>{MODE_LABELS[mode]}:</strong> {message}
          </span>
        </p>
      ))}
      {notice ? (
        <p className="flex items-center gap-2 rounded-xl border border-success/25 bg-success/10 px-4 py-3 text-[13px] text-fg">
          <CheckCircle2 className="size-4 text-success" /> {notice}
        </p>
      ) : null}

      {/* ── Results ──────────────────────────────────── */}
      {!result ? (
        isGenerating ? (
          <ResultSkeleton />
        ) : (
          <div className="grid place-items-center gap-3 rounded-2xl border border-dashed border-border-strong bg-surface-2 px-6 py-16 text-center">
            <span className="grid size-12 place-items-center rounded-2xl bg-gradient-to-br from-accent/20 to-accent2/20">
              <Network className="size-6 text-accent-dim" />
            </span>
            <p className="font-display text-base font-bold text-fg">Your class diagram will appear here</p>
            <p className="max-w-md text-[12.5px] text-fg-3">
              Pick an example or paste your own task, choose an engine, and generate. You can compare the rule-based and LLM answers side by side.
            </p>
          </div>
        )
      ) : (
        <div className="grid grid-cols-1 gap-4 rounded-2xl border border-border bg-surface p-4 shadow-sm sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Chip tone={result.mode === 'rule_based' ? 'accent' : 'ai'}>
                <ModeIcon mode={result.mode} className="size-3" />
                {activeRun ? runLabel(activeRun) : 'Result'}
              </Chip>
              <ModelStats model={result.model} />
            </div>
            <div className="flex flex-wrap gap-1.5">
              <Button variant="secondary" size="sm" onClick={handlePng} title="PNG image of the diagram as arranged on screen">
                <FileImage /> PNG
              </Button>
              <Button variant="secondary" size="sm" onClick={handleSvg} title="Scalable vector image">
                <Download /> SVG
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => downloadTextFile(`${fileStem(result)}.xml`, result.drawioXml, 'application/xml')}
                title="draw.io / diagrams.net XML"
              >
                <FileCode2 /> XML
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => downloadTextFile(`${fileStem(result)}.drawio`, result.drawioXml, 'application/xml')}
                title="Open directly in diagrams.net"
              >
                <FileCode2 /> .drawio
              </Button>
              <Button variant="secondary" size="sm" onClick={handleSave} disabled={!activeProject || isSaving}>
                <Save /> {isSaving ? 'Saving…' : activeProject ? 'Save to project' : 'Select a project to save'}
              </Button>
            </div>
          </div>

          {runs.length > 1 ? (
            <div className="flex flex-wrap items-center gap-1.5 rounded-xl border border-border bg-surface-2 px-3 py-2">
              <span className="mr-1 flex items-center gap-1 text-[11.5px] font-semibold text-fg-3">
                <History className="size-3.5" /> Runs
              </span>
              {runs.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => {
                    setActiveRunId(item.id)
                    if (tab === 'compare') setTab('diagram')
                  }}
                  title={item.text.slice(0, 160)}
                  className={cn(
                    'flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11.5px] font-semibold transition',
                    item.id === activeRun?.id
                      ? 'border-accent bg-accent/10 text-fg'
                      : 'border-border bg-surface text-fg-2 hover:border-border-strong hover:text-fg',
                  )}
                >
                  <ModeIcon mode={item.mode} className="size-3" />
                  {runLabel(item)}
                  <span className="font-normal text-fg-3">
                    · {item.result.model.classes.length} classes ·{' '}
                    {item.createdAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </button>
              ))}
            </div>
          ) : null}

          <Tabs value={tab} onValueChange={setTab} className="grid grid-cols-1 gap-4">
            <TabsList className="justify-self-start overflow-x-auto">
              <TabTrigger value="diagram" icon={Network}>Diagram</TabTrigger>
              <TabTrigger value="breakdown" icon={ListTree}>Step-by-step</TabTrigger>
              <TabTrigger value="classes" icon={Table2}>Classes</TabTrigger>
              <TabTrigger value="drawio" icon={FileCode2}>draw.io</TabTrigger>
              {canCompare ? <TabTrigger value="compare" icon={GitCompareArrows}>Compare</TabTrigger> : null}
            </TabsList>

            <TabsContent value="diagram" className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
              {result.validation.valid ? (
                <ClassDiagramCanvas ref={canvasRef} model={result.model} />
              ) : (
                <p className="text-sm text-danger">{result.validation.errors.join(' ')}</p>
              )}
              <RelationshipLegend model={result.model} className="content-start xl:max-h-[38rem] xl:overflow-y-auto xl:pr-1" />
            </TabsContent>

            <TabsContent value="breakdown" className="grid grid-cols-1 gap-6">
              <Breakdown result={result} />
            </TabsContent>

            <TabsContent value="classes" className="grid grid-cols-1 gap-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[12px] text-fg-3">
                  {editing
                    ? 'Changes here update the diagram and the draw.io view as you make them.'
                    : 'The model behind the diagram. Switch to editing to add attributes, methods or relationships.'}
                </p>
                <div className="flex flex-wrap gap-2">
                  {activeRun?.edited && activeRun.mode !== 'rule_based' ? (
                    <Button variant="secondary" size="sm" onClick={() => void rememberFix()} disabled={isRemembering || !activeProject}>
                      {isRemembering ? <Loader2 className="animate-spin" /> : <BrainCircuit />} Teach the engine this fix
                    </Button>
                  ) : null}
                  <Button variant={editing ? 'primary' : 'secondary'} size="sm" onClick={() => setEditing((current) => !current)}>
                    {editing ? <Eye /> : <Pencil />} {editing ? 'Done editing' : 'Edit model'}
                  </Button>
                </div>
              </div>
              {editing ? (
                <ClassModelEditor model={result.model} onChange={applyModel} />
              ) : (
                <>
                  <ClassCards classes={result.model.classes} enums={result.model.enums} relationships={result.model.relationships} />
                  <RelationshipList relationships={result.model.relationships} classes={result.model.classes} />
                </>
              )}
            </TabsContent>

            <TabsContent value="drawio" className="grid grid-cols-1 gap-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[12px] text-fg-3">
                  The same model, editable as a diagram. Adding or renaming a class here updates the Classes tab and the
                  interactive diagram too. Needs an internet connection to preview.
                </p>
                <Button variant="secondary" size="sm" onClick={handleDrawioPng}>
                  <ImageDown /> PNG from draw.io
                </Button>
              </div>
              {tab === 'drawio' && result.validation.valid ? (
                <DrawioEmbed
                  ref={drawioRef}
                  xml={result.drawioXml}
                  title="Generated class diagram"
                  className="h-[36rem]"
                  onChange={applyDrawioEdit}
                />
              ) : null}
            </TabsContent>

            {canCompare ? (
              <TabsContent value="compare" className="grid grid-cols-1 gap-4">
                <div className="grid grid-cols-1 gap-3 rounded-xl border border-border bg-surface-2 p-3 sm:grid-cols-[1fr_auto_1fr] sm:items-end">
                  {(['left', 'right'] as const).map((side, index) => (
                    <div key={side} className={cn('grid grid-cols-1 gap-1', index === 1 && 'sm:order-3')}>
                      <label className="text-[11px] font-bold uppercase tracking-[0.08em] text-fg-3" htmlFor={`compare-${side}`}>
                        {side === 'left' ? 'Compare' : 'With'}
                      </label>
                      <Select
                        id={`compare-${side}`}
                        value={(side === 'left' ? leftRun : rightRun)?.id ?? ''}
                        onChange={(event) => {
                          const chosen = event.target.value
                          setComparePair([side === 'left' ? chosen : (leftRun?.id ?? chosen), side === 'right' ? chosen : (rightRun?.id ?? chosen)])
                        }}
                      >
                        {runs.map((item) => (
                          <option key={item.id} value={item.id}>
                            {runLabel(item)} · {item.result.model.classes.length} classes · {item.text.slice(0, 40)}…
                          </option>
                        ))}
                      </Select>
                    </div>
                  ))}
                  <GitCompareArrows className="mx-auto hidden size-5 text-fg-3 sm:order-2 sm:mb-2.5 sm:block" />
                </div>
                {leftRun && rightRun && leftRun.id !== rightRun.id ? (
                  <CompareView left={{ label: runLabel(leftRun), result: leftRun.result }} right={{ label: runLabel(rightRun), result: rightRun.result }} />
                ) : (
                  <p className="text-[12.5px] text-fg-3">Pick two different runs to compare.</p>
                )}
              </TabsContent>
            ) : null}
          </Tabs>
        </div>
      )}
    </section>
  )
}

function TabTrigger({ value, icon: Icon, children }: { value: string; icon: LucideIcon; children: ReactNode }) {
  return (
    <TabsTrigger value={value} className="flex items-center gap-1.5 whitespace-nowrap">
      <Icon className="size-3.5" />
      {children}
    </TabsTrigger>
  )
}

function ModelStats({ model }: { model: ClassModelerResult['model'] }) {
  const count = (stereotype: string) => model.classes.filter((cls) => cls.stereotype === stereotype).length
  const inheritance = model.relationships.filter((rel) => rel.type === 'inheritance').length
  const realization = model.relationships.filter((rel) => rel.type === 'realization').length
  const items = [
    { label: 'classes', value: model.classes.length - count('interface') },
    { label: 'interfaces', value: count('interface') },
    { label: 'abstract', value: count('abstract') },
    { label: 'inheritance', value: inheritance },
    { label: 'implements', value: realization },
    { label: 'other links', value: model.relationships.length - inheritance - realization },
    { label: 'enums', value: model.enums.length },
  ].filter((item) => item.value > 0)
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span key={item.label} className="rounded-full border border-border bg-surface-2 px-2.5 py-0.5 text-[11.5px] text-fg-2">
          <strong className="text-fg">{item.value}</strong> {item.label}
        </span>
      ))}
    </div>
  )
}

function ResultSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 rounded-2xl border border-border bg-surface p-5">
      <div className="flex gap-2">
        {[1, 2, 3].map((item) => (
          <div key={item} className="h-6 w-24 animate-pulse rounded-full bg-surface-3" />
        ))}
      </div>
      <div className="grid h-[28rem] grid-cols-3 gap-6 rounded-xl bg-surface-2 p-8">
        {[1, 2, 3, 4, 5, 6].map((item) => (
          <div key={item} className="h-28 animate-pulse rounded-xl bg-surface-3" />
        ))}
      </div>
    </div>
  )
}

function ClassCards({
  classes,
  enums,
  relationships,
}: {
  classes: ModelClass[]
  enums: ModelEnum[]
  relationships: ModelRelationship[]
}) {
  const kindStyle: Record<string, string> = {
    entity: 'border-accent/35',
    abstract: 'border-warning/45',
    interface: 'border-dashed border-accent2/50',
  }
  const headStyle: Record<string, string> = {
    entity: 'bg-accent/10',
    abstract: 'bg-warning/12',
    interface: 'bg-accent2/12',
  }
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 2xl:grid-cols-3">
      {classes.map((cls) => {
        const extendsOf = relationships.filter((rel) => rel.sourceClassId === cls.id && rel.type === 'inheritance').map((rel) => rel.target)
        const implementsOf = relationships.filter((rel) => rel.sourceClassId === cls.id && rel.type === 'realization').map((rel) => rel.target)
        const children = relationships.filter((rel) => rel.targetClassId === cls.id && (rel.type === 'inheritance' || rel.type === 'realization'))
        const kind = cls.stereotype in kindStyle ? cls.stereotype : 'entity'
        return (
          <div key={cls.id} className={cn('overflow-hidden rounded-xl border-[1.5px] bg-surface shadow-xs', kindStyle[kind])}>
            <div className={cn('px-4 py-2.5', headStyle[kind])}>
              <div className="flex items-center justify-between gap-2">
                <span className={cn('font-display text-[15px] font-bold text-fg', kind === 'abstract' && 'italic')}>{cls.name}</span>
                {kind !== 'entity' ? (
                  <Chip tone={kind === 'interface' ? 'ai' : 'warning'}>{kind}</Chip>
                ) : null}
              </div>
              {extendsOf.length || implementsOf.length || children.length ? (
                <div className="mt-1 grid grid-cols-1 gap-0.5 text-[11.5px] text-fg-2">
                  {extendsOf.length ? <span>is a <strong>{extendsOf.join(', ')}</strong> - inherits its members</span> : null}
                  {implementsOf.length ? <span>implements <strong>{implementsOf.join(', ')}</strong></span> : null}
                  {children.length ? (
                    <span className="text-fg-3">
                      {kind === 'interface' ? 'implemented by' : 'parent of'} {children.map((rel) => rel.source).join(', ')}
                    </span>
                  ) : null}
                </div>
              ) : null}
            </div>
            <div className="grid grid-cols-1 gap-2 px-4 py-3">
              <div>
                <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-fg-3">Attributes</div>
                {cls.attributes.length ? (
                  <ul className="mt-0.5 font-mono text-[12px] text-fg-2">
                    {cls.attributes.map((attr) => (
                      <li key={attr.id}>
                        - {attr.name}: <span className="text-accent-dim">{attr.type}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[11.5px] text-fg-3">{kind === 'interface' ? 'Interfaces hold no data.' : 'None'}</p>
                )}
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-fg-3">Methods</div>
                {cls.methods.length ? (
                  <ul className="mt-0.5 font-mono text-[12px] text-fg">
                    {cls.methods.map((method) => (
                      <li key={method.id}>+ {methodSignature(method)}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-[11.5px] text-fg-3">None</p>
                )}
              </div>
            </div>
          </div>
        )
      })}
      {enums.map((item) => (
        <div key={item.id} className="overflow-hidden rounded-xl border-[1.5px] border-sky/45 bg-surface shadow-xs">
          <div className="flex items-center justify-between bg-sky/10 px-4 py-2.5">
            <span className="font-display text-[15px] font-bold text-fg">{item.name}</span>
            <Chip tone="sky">enum</Chip>
          </div>
          <div className="flex flex-wrap gap-1 px-4 py-3">
            {item.literals.map((literal) => (
              <span key={literal} className="rounded-md bg-sky/10 px-1.5 py-0.5 font-mono text-[11.5px] text-fg-2">
                {literal}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function RelationshipList({ relationships, classes }: { relationships: ModelRelationship[]; classes: ModelClass[] }) {
  if (!relationships.length) return <p className="text-[12.5px] text-fg-3">No relationships between classes were found.</p>
  return (
    <div className="grid grid-cols-1 gap-2">
      <h3 className="font-display text-[15px] font-bold text-fg">Relationships in plain words</h3>
      <ul className="grid grid-cols-1 gap-2 lg:grid-cols-2">
        {relationships.map((rel) => {
          const { headline, detail } = explainRelationship(rel, classes)
          return (
            <li key={rel.id} className="flex items-start gap-3 rounded-xl border border-border bg-surface-2 px-3.5 py-2.5">
              <RelationshipGlyph kind={rel.type} className="mt-0.5" />
              <div className="min-w-0">
                <div className="text-[13px] font-semibold text-fg">{headline}</div>
                {detail ? <div className="text-[11.5px] text-fg-3">{detail}</div> : null}
                {rel.sourceMultiplicity || rel.targetMultiplicity ? (
                  <div className="mt-0.5 font-mono text-[11px] text-fg-3">
                    {rel.source} [{rel.sourceMultiplicity ?? ' '}] → [{rel.targetMultiplicity ?? ' '}] {rel.target}
                  </div>
                ) : null}
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
