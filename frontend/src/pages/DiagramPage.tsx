import { useEffect, useRef, useState } from 'react'
import type { Ref } from 'react'
import {
  ArrowLeft,
  Columns2,
  Download,
  FileCode2,
  History,
  ImageDown,
  Loader2,
  MoreHorizontal,
  Network,
  Pencil,
  RotateCcw,
  Save,
  Trash2,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { diagramApi, errorMessage, projectApi } from '../api'
import type { ClassModelerResult, DiagramVersion } from '../api'
import { ErrorState, LoadingState } from '../app/components/PageStates'
import { RenameDialog } from '../app/components/RenameDialog'
import { href, navigate, routes } from '../app/core/router'
import { useSession } from '../app/core/session'
import { useAsync } from '../app/core/useAsync'
import { ClassDiagramCanvas } from '../features/classModeler/diagram/ClassDiagramCanvas'
import type { ClassDiagramHandle } from '../features/classModeler/diagram/ClassDiagramCanvas'
import { RelationshipLegend } from '../features/classModeler/RelationshipLegend'
import { DrawioEmbed } from '../features/diagram/DrawioEmbed'
import type { DrawioEmbedHandle } from '../features/diagram/DrawioEmbed'
import { useDrawioClassModel } from '../features/diagram/useDrawioClassModel'
import { downloadDataUrl, downloadTextFile } from '../shared/download'
import { formatDateTime, relativeTime } from '../shared/format'
import {
  Button,
  Card,
  Chip,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  cn,
  useFeedback,
} from '../shared/ui'

type ClassModel = ClassModelerResult['model']

/** The same drawing, three ways to look at it. The interactive canvas reads its
 * model out of the stored draw.io XML (see features/diagram/drawioModel.ts), so
 * every view shows exactly what is on the canvas right now - the version being
 * previewed included, and edits not yet saved. Editing stays in draw.io. */
type ViewId = 'interactive' | 'drawio' | 'split'

const VIEWS: { id: ViewId; label: string; icon: LucideIcon }[] = [
  { id: 'interactive', label: 'Interactive', icon: Network },
  { id: 'drawio', label: 'draw.io', icon: FileCode2 },
  { id: 'split', label: 'Side by side', icon: Columns2 },
]

function count(total: number, singular: string, plural = `${singular}s`) {
  return `${total} ${total === 1 ? singular : plural}`
}

function stem(title: string) {
  return title.trim().replace(/[^\w.-]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') || 'diagram'
}

/** The interactive canvas, or an explanation of why there is nothing to draw.
 *
 * A diagram is stored as draw.io XML only, so a drawing that is not a class
 * model (a flowchart, a sketch, boxes without names) yields no model. That is
 * not an error - draw.io still shows it, so say so and point there. */
function CanvasView({
  model,
  parsing,
  className,
  ref,
}: {
  model: ClassModel | null
  parsing: boolean
  className?: string
  ref?: Ref<ClassDiagramHandle>
}) {
  if (model) return <ClassDiagramCanvas ref={ref} model={model} className={className} />
  return (
    <div className={cn('grid place-items-center rounded-xl border border-border bg-surface-2 p-6', className)}>
      {parsing ? (
        <span className="flex items-center gap-2 text-[13px] text-fg-2">
          <Loader2 className="size-4 animate-spin" /> Reading the model…
        </span>
      ) : (
        <p className="max-w-sm text-center text-[13px] leading-relaxed text-fg-2">
          <strong className="block text-fg">No class model in this drawing</strong>
          The interactive view reads classes, attributes and relationships out of the diagram. This one holds shapes it cannot
          read as a class model — open the <strong className="text-fg">draw.io</strong> view to see and edit it.
        </p>
      )}
    </div>
  )
}

export function DiagramPage({ projectId, diagramId }: { projectId: string; diagramId: string }) {
  const { workspaceId, canEdit } = useSession()
  const { toast, confirm } = useFeedback()
  const diagram = useAsync(() => diagramApi.get(workspaceId, projectId, diagramId), [workspaceId, projectId, diagramId], Boolean(workspaceId))
  const versions = useAsync(() => diagramApi.versions(workspaceId, projectId, diagramId), [workspaceId, projectId, diagramId], Boolean(workspaceId))
  const project = useAsync(() => projectApi.get(workspaceId, projectId), [workspaceId, projectId], Boolean(workspaceId))
  const embed = useRef<DrawioEmbedHandle>(null)
  const canvas = useRef<ClassDiagramHandle>(null)

  const [xml, setXml] = useState('')
  const [savedXml, setSavedXml] = useState('')
  const [syncedVersionId, setSyncedVersionId] = useState<string | null>(null)
  const [viewing, setViewing] = useState<DiagramVersion | null>(null)
  const [saving, setSaving] = useState(false)
  const [exporting, setExporting] = useState<string | null>(null)
  const [renaming, setRenaming] = useState(false)
  // A class diagram opens on the canvas; anything else only draw.io can draw.
  const [view, setView] = useState<ViewId | null>(null)

  // Load the canvas from the server's current version whenever that version changes.
  const current = diagram.data?.current
  if (current && current.id !== syncedVersionId) {
    setSyncedVersionId(current.id)
    setXml(current.drawio_xml)
    setSavedXml(current.drawio_xml)
    setViewing(null)
  }

  const dirty = xml !== savedXml && !viewing
  const activeView: ViewId = view ?? (diagram.data?.diagram_type === 'class' ? 'interactive' : 'drawio')
  const showsCanvas = activeView === 'interactive' || activeView === 'split'
  const showsDrawio = activeView === 'drawio' || activeView === 'split'
  const { pending: parsing, result: parsed } = useDrawioClassModel(xml, showsCanvas)
  const model = parsed?.model ?? null

  useEffect(() => {
    if (!dirty) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  async function saveVersion(sourceXml = xml) {
    if (!diagram.data) return
    setSaving(true)
    try {
      const version = await diagramApi.saveVersion(workspaceId, projectId, diagram.data.id, sourceXml)
      diagram.setData({ ...diagram.data, current_version: version.version_number, current: version, updated_at: version.created_at })
      versions.setData((current) => [...(current ?? []), version])
      setSavedXml(sourceXml)
      setXml(sourceXml)
      setViewing(null)
      toast(`Saved version ${version.version_number}`)
    } catch (caught) {
      toast('Save failed', { description: errorMessage(caught), tone: 'error' })
    } finally {
      setSaving(false)
    }
  }

  async function runExport(label: string, download: () => Promise<void> | void) {
    setExporting(label)
    try {
      await download()
    } catch (caught) {
      toast('Export failed', { description: errorMessage(caught), tone: 'error' })
    } finally {
      setExporting(null)
    }
  }

  function exportFromDrawio(format: 'png' | 'jpeg') {
    return runExport(`drawio-${format}`, async () => {
      if (!embed.current || !diagram.data) throw new Error('Open the draw.io view first.')
      downloadDataUrl(`${stem(diagram.data.title)}.${format === 'jpeg' ? 'jpg' : 'png'}`, await embed.current.exportImage(format))
    })
  }

  function exportFromCanvas(format: 'png' | 'svg') {
    return runExport(`canvas-${format}`, async () => {
      if (!canvas.current || !diagram.data) throw new Error('Open the interactive view first.')
      const name = `${stem(diagram.data.title)}.${format}`
      if (format === 'png') downloadDataUrl(name, await canvas.current.exportPng())
      else downloadTextFile(name, canvas.current.exportSvg().svg, 'image/svg+xml')
    })
  }

  async function remove() {
    if (!diagram.data) return
    const ok = await confirm({ title: `Delete “${diagram.data.title}”?`, description: 'The diagram and its version history are removed from the project.' })
    if (!ok) return
    try {
      await diagramApi.remove(workspaceId, projectId, diagram.data.id)
      toast('Diagram deleted')
      navigate(routes.diagrams())
    } catch (caught) {
      toast('Delete failed', { description: errorMessage(caught), tone: 'error' })
    }
  }

  async function openVersion(version: DiagramVersion) {
    if (dirty && !(await confirm({ title: 'Discard unsaved changes?', description: 'Opening an older version replaces what is on the canvas.', confirmLabel: 'Discard' }))) return
    if (version.version_number === diagram.data?.current_version) {
      setViewing(null)
      setXml(savedXml)
    } else {
      setViewing(version)
      setXml(version.drawio_xml)
    }
  }

  if (diagram.loading && !diagram.data) return <LoadingState rows={3} />
  if (diagram.error || !diagram.data) return <ErrorState message={diagram.error ?? 'Diagram not found'} onRetry={diagram.reload} />

  const data = diagram.data
  const orderedVersions = [...(versions.data ?? [])].sort((a, b) => b.version_number - a.version_number)

  return (
    <section className="grid grid-cols-1 gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <a
            href={href(project.data ? routes.project(projectId, 'diagrams') : routes.diagrams())}
            className="mb-2 inline-flex items-center gap-1.5 text-xs font-semibold text-fg-3 transition hover:text-accent"
          >
            <ArrowLeft className="size-3.5" /> {project.data?.name ?? 'Diagrams'}
          </a>
          <h1 className="font-display text-[22px] font-extrabold leading-tight tracking-tight text-fg sm:text-[26px]">{data.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-fg-3">
            <Chip tone={data.source === 'generated' ? 'ai' : 'muted'}>{data.source === 'generated' ? 'Generated' : 'Manual'}</Chip>
            <Chip tone="muted">{data.diagram_type}</Chip>
            <span>
              Version {data.current_version} · {relativeTime(data.updated_at)}
            </span>
            {dirty ? <Chip tone="warning">Unsaved changes</Chip> : null}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {canEdit ? (
            viewing ? (
              <Button onClick={() => void saveVersion(viewing.drawio_xml)} disabled={saving}>
                {saving ? <Loader2 className="animate-spin" /> : <RotateCcw />} Restore v{viewing.version_number}
              </Button>
            ) : (
              <Button onClick={() => void saveVersion()} disabled={saving || !dirty}>
                {saving ? <Loader2 className="animate-spin" /> : <Save />} Save version
              </Button>
            )
          ) : null}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="secondary">
                <Download /> Export
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {/* Each view renders the diagram itself, so each exports its own
                  picture - the canvas through React, draw.io through its editor. */}
              {showsCanvas && model ? (
                <>
                  <DropdownMenuItem onSelect={() => void exportFromCanvas('png')} disabled={exporting !== null}>
                    <ImageDown /> PNG · interactive view
                  </DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => void exportFromCanvas('svg')} disabled={exporting !== null}>
                    <ImageDown /> SVG · interactive view
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                </>
              ) : null}
              {showsDrawio ? (
                <>
                  <DropdownMenuItem onSelect={() => void exportFromDrawio('png')} disabled={exporting !== null}>
                    <ImageDown /> PNG · draw.io
                  </DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => void exportFromDrawio('jpeg')} disabled={exporting !== null}>
                    <ImageDown /> JPG · draw.io
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                </>
              ) : null}
              <DropdownMenuItem onSelect={() => downloadTextFile(`${stem(data.title)}.drawio`, xml, 'application/xml;charset=utf-8')}>
                <Download /> draw.io file
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          {canEdit ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="secondary" className="px-2.5" aria-label="More actions">
                  <MoreHorizontal />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => setRenaming(true)}>
                  <Pencil /> Rename
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => void remove()} className="text-danger data-[highlighted]:text-danger">
                  <Trash2 /> Delete diagram
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : null}
        </div>
      </div>

      {viewing ? (
        <Card className="flex flex-col gap-2 border-warning/30 bg-warning/[0.06] px-4 py-3 text-[13px] text-fg sm:flex-row sm:items-center">
          <History className="size-4 shrink-0 text-warning" />
          <span className="flex-1">
            Viewing version {viewing.version_number} from {formatDateTime(viewing.created_at)}. Restore it to make it the current version.
          </span>
          <Button size="sm" variant="secondary" onClick={() => void openVersion(orderedVersions[0])}>
            Back to latest
          </Button>
        </Card>
      ) : null}

      <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-[minmax(0,1fr)_16rem]">
        <Tabs value={activeView} onValueChange={(next) => setView(next as ViewId)} className="grid min-w-0 grid-cols-1 gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <TabsList className="overflow-x-auto">
              {VIEWS.map((item) => {
                const Icon = item.icon
                return (
                  <TabsTrigger key={item.id} value={item.id} className="flex items-center gap-1.5 whitespace-nowrap">
                    <Icon className="size-3.5" />
                    {item.label}
                  </TabsTrigger>
                )
              })}
            </TabsList>
            {showsCanvas && model ? (
              <p className="text-[11.5px] text-fg-3">
                {[
                  count(model.classes.length, 'class', 'classes'),
                  count(model.relationships.length, 'relationship'),
                  model.enums.length ? count(model.enums.length, 'enum') : null,
                  parsed?.skipped ? `${count(parsed.skipped, 'other shape')} not shown` : null,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
            ) : null}
          </div>

          <TabsContent value="interactive" className="grid min-w-0 grid-cols-1 gap-4 2xl:grid-cols-[minmax(0,1fr)_18rem]">
            <CanvasView model={model} parsing={parsing} ref={canvas} className="h-[min(72vh,44rem)] min-h-[26rem]" />
            {model ? <RelationshipLegend model={model} className="content-start 2xl:max-h-[38rem] 2xl:overflow-y-auto 2xl:pr-1" /> : null}
          </TabsContent>

          <TabsContent value="split" className="grid min-w-0 grid-cols-1 gap-4 2xl:grid-cols-2">
            <CanvasView model={model} parsing={parsing} ref={canvas} className="h-[min(56vh,34rem)] min-h-[22rem]" />
            {/* Editing happens here even in the split view; the canvas on the
                left re-reads the model as draw.io autosaves. */}
            <DrawioEmbed
              ref={embed}
              xml={xml}
              title={`${data.title} editor`}
              className="h-[min(56vh,34rem)] min-h-[22rem]"
              onChange={canEdit && !viewing ? setXml : undefined}
            />
          </TabsContent>

          <TabsContent value="drawio" className="min-w-0">
            <DrawioEmbed
              ref={embed}
              xml={xml}
              title={`${data.title} editor`}
              className="h-[min(72vh,44rem)] min-h-[26rem]"
              onChange={canEdit && !viewing ? setXml : undefined}
            />
          </TabsContent>
        </Tabs>
        <Card className="p-3">
          <p className="mb-2 flex items-center gap-1.5 px-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-fg-3">
            <History className="size-3.5" /> Versions
          </p>
          <ul className="grid max-h-[28rem] grid-cols-1 gap-1 overflow-y-auto">
            {orderedVersions.map((version) => {
              const current = version.version_number === data.current_version
              const shown = viewing ? viewing.id === version.id : current
              return (
                <li key={version.id}>
                  <button
                    type="button"
                    onClick={() => void openVersion(version)}
                    className={cn(
                      'flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left transition',
                      shown ? 'bg-accent/10 text-accent' : 'text-fg-2 hover:bg-surface-2 hover:text-fg',
                    )}
                  >
                    <span className="min-w-0">
                      <span className="block text-[13px] font-semibold">Version {version.version_number}</span>
                      <span className="block truncate text-[11px] text-fg-3">{formatDateTime(version.created_at)}</span>
                    </span>
                    {current ? <Chip tone="success">Current</Chip> : null}
                  </button>
                </li>
              )
            })}
            {!orderedVersions.length ? <li className="px-2.5 py-2 text-[13px] text-fg-3">No versions yet.</li> : null}
          </ul>
        </Card>
      </div>

      <RenameDialog
        open={renaming}
        title="Rename diagram"
        initialValue={data.title}
        onOpenChange={setRenaming}
        onSubmit={async (title) => {
          try {
            const renamed = await diagramApi.rename(workspaceId, projectId, data.id, title)
            diagram.setData({ ...data, title: renamed.title })
            toast('Diagram renamed')
          } catch (caught) {
            toast('Rename failed', { description: errorMessage(caught), tone: 'error' })
            throw caught
          }
        }}
      />
    </section>
  )
}
