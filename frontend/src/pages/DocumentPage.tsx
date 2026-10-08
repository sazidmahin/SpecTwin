import { useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  Download,
  Eye,
  FileText,
  GitCompareArrows,
  ListTree,
  Loader2,
  MoreHorizontal,
  Network,
  Pencil,
  Printer,
  Save,
  Trash2,
  WandSparkles,
  X,
} from 'lucide-react'
import { errorMessage, projectApi, srsApi } from '../api'
import { ErrorState, LoadingState } from '../app/components/PageStates'
import { href, navigate, routes } from '../app/core/router'
import { useSession } from '../app/core/session'
import { useAsync } from '../app/core/useAsync'
import { Markdown } from '../features/srs/Markdown'
import { extractHeadings } from '../features/srs/markdownHeadings'
import { downloadTextFile } from '../shared/download'
import { ENGINE_LABELS, formatDateTime } from '../shared/format'
import {
  Button,
  Card,
  Chip,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Input,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
  cn,
  useFeedback,
} from '../shared/ui'

function fileName(title: string) {
  return `${title.trim().replace(/[^\w.-]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') || 'srs-document'}.md`
}

export function DocumentPage({ projectId, documentId }: { projectId: string; documentId: string }) {
  const { workspaceId, canEdit } = useSession()
  const { toast, confirm } = useFeedback()
  const doc = useAsync(() => srsApi.get(workspaceId, projectId, documentId), [workspaceId, projectId, documentId], Boolean(workspaceId))
  const project = useAsync(() => projectApi.get(workspaceId, projectId), [workspaceId, projectId], Boolean(workspaceId))

  const [editing, setEditing] = useState(false)
  const [titleDraft, setTitleDraft] = useState('')
  const [contentDraft, setContentDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [activeHeading, setActiveHeading] = useState<string | null>(null)

  const data = doc.data
  const headings = useMemo(() => extractHeadings(data?.content_markdown ?? ''), [data?.content_markdown])
  const requirements = data?.content_json.requirements ?? []
  const functional = requirements.filter((item) => item.type !== 'non_functional').length
  const dirty = editing && data && (titleDraft !== data.title || contentDraft !== data.content_markdown)

  useEffect(() => {
    if (!dirty) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  useEffect(() => {
    if (editing || !headings.length) return
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (visible[0]) setActiveHeading(visible[0].target.id)
      },
      { rootMargin: '-80px 0px -65% 0px' },
    )
    for (const heading of headings) {
      const element = document.getElementById(heading.id)
      if (element) observer.observe(element)
    }
    return () => observer.disconnect()
  }, [headings, editing])

  function startEditing() {
    if (!data) return
    setTitleDraft(data.title)
    setContentDraft(data.content_markdown)
    setEditing(true)
  }

  async function cancelEditing() {
    if (dirty && !(await confirm({ title: 'Discard your changes?', confirmLabel: 'Discard' }))) return
    setEditing(false)
  }

  async function save() {
    if (!data) return
    if (!titleDraft.trim() || !contentDraft.trim()) {
      toast('Title and content are required', { tone: 'error' })
      return
    }
    setSaving(true)
    try {
      const saved = await srsApi.update(workspaceId, projectId, data.id, { title: titleDraft.trim(), content_markdown: contentDraft })
      doc.setData(saved)
      setEditing(false)
      toast('Document saved')
    } catch (caught) {
      toast('Save failed', { description: errorMessage(caught), tone: 'error' })
    } finally {
      setSaving(false)
    }
  }

  async function remove() {
    if (!data) return
    const ok = await confirm({
      title: 'Delete this SRS document?',
      description: 'The document is removed from the project. Its generation run and diagram are kept.',
    })
    if (!ok) return
    try {
      await srsApi.remove(workspaceId, projectId, data.id)
      toast('Document deleted')
      navigate(routes.documents())
    } catch (caught) {
      toast('Delete failed', { description: errorMessage(caught), tone: 'error' })
    }
  }

  function jumpTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    setActiveHeading(id)
  }

  if (doc.loading && !data) return <LoadingState rows={4} />
  if (doc.error || !data) return <ErrorState message={doc.error ?? 'Document not found'} onRetry={doc.reload} />

  const mode = data.content_json.generationMode

  return (
    <section className="grid grid-cols-1 gap-5">
      <div className="print-hidden flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <a
            href={href(project.data ? routes.project(projectId, 'documents') : routes.documents())}
            className="mb-2 inline-flex items-center gap-1.5 text-xs font-semibold text-fg-3 transition hover:text-accent"
          >
            <ArrowLeft className="size-3.5" /> {project.data?.name ?? 'SRS documents'}
          </a>
          <div className="flex flex-wrap items-center gap-2 text-xs text-fg-3">
            <Chip tone="accent">
              <FileText /> SRS
            </Chip>
            {mode ? <Chip tone="ai">{ENGINE_LABELS[mode] ?? mode}</Chip> : null}
            {requirements.length ? (
              <span>
                {functional} functional · {requirements.length - functional} non-functional
              </span>
            ) : null}
            <span>Updated {formatDateTime(data.updated_at)}</span>
            {data.content_json.editedManually ? <Chip tone="muted">Edited</Chip> : null}
          </div>
        </div>

        {editing ? (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => void cancelEditing()} disabled={saving}>
              <X /> Cancel
            </Button>
            <Button onClick={() => void save()} disabled={saving || !dirty}>
              {saving ? <Loader2 className="animate-spin" /> : <Save />} Save
            </Button>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => downloadTextFile(fileName(data.title), data.content_markdown, 'text/markdown;charset=utf-8')}>
              <Download /> <span className="hidden sm:inline">Markdown</span>
            </Button>
            <Button variant="secondary" onClick={() => window.print()}>
              <Printer /> <span className="hidden sm:inline">Print / PDF</span>
            </Button>
            {canEdit ? (
              <Button onClick={startEditing}>
                <Pencil /> Edit
              </Button>
            ) : null}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="secondary" className="px-2.5" aria-label="More actions">
                  <MoreHorizontal />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {data.diagram_id ? (
                  <DropdownMenuItem onSelect={() => navigate(routes.diagram(projectId, data.diagram_id!))}>
                    <Network /> Open class diagram
                  </DropdownMenuItem>
                ) : null}
                {data.pipeline_run_id ? (
                  <DropdownMenuItem onSelect={() => navigate(routes.run(projectId, data.pipeline_run_id!))}>
                    <WandSparkles /> Open generation run
                  </DropdownMenuItem>
                ) : null}
                <DropdownMenuItem onSelect={() => navigate(routes.compareDocuments(), { a: data.id })}>
                  <GitCompareArrows /> Compare with another document
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem disabled={!canEdit} onSelect={() => void remove()} className="text-danger data-[highlighted]:text-danger">
                  <Trash2 /> Delete document
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        )}
      </div>

      {editing ? (
        <Card className="grid grid-cols-1 gap-4 p-4 sm:p-5">
          <Input value={titleDraft} maxLength={255} onChange={(event) => setTitleDraft(event.target.value)} aria-label="Document title" className="text-base font-semibold" />
          <Tabs defaultValue="write" className="grid grid-cols-1 gap-3 xl:hidden">
            <TabsList className="w-max">
              <TabsTrigger value="write">
                <span className="flex items-center gap-1.5">
                  <Pencil className="size-3.5" /> Write
                </span>
              </TabsTrigger>
              <TabsTrigger value="preview">
                <span className="flex items-center gap-1.5">
                  <Eye className="size-3.5" /> Preview
                </span>
              </TabsTrigger>
            </TabsList>
            <TabsContent value="write">
              <Textarea className="min-h-[60vh] font-mono text-[13px] leading-6" value={contentDraft} onChange={(event) => setContentDraft(event.target.value)} spellCheck={false} />
            </TabsContent>
            <TabsContent value="preview" className="rounded-xl border border-border p-4">
              <Markdown content={contentDraft} />
            </TabsContent>
          </Tabs>
          <div className="hidden grid-cols-2 gap-4 xl:grid">
            <Textarea
              className="h-[70vh] resize-none font-mono text-[13px] leading-6"
              value={contentDraft}
              onChange={(event) => setContentDraft(event.target.value)}
              spellCheck={false}
              aria-label="Markdown source"
            />
            <div className="h-[70vh] overflow-y-auto rounded-xl border border-border p-5">
              <Markdown content={contentDraft} />
            </div>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-[minmax(0,1fr)_15rem]">
          <Card className="print-area min-w-0 px-5 py-6 sm:px-10 sm:py-10">
            <Markdown content={data.content_markdown} className="mx-auto max-w-3xl" />
          </Card>
          {headings.length ? (
            <nav className="print-hidden hidden xl:sticky xl:top-20 xl:block" aria-label="Table of contents">
              <p className="mb-2 flex items-center gap-1.5 px-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-fg-3">
                <ListTree className="size-3.5" /> On this page
              </p>
              <ul className="grid max-h-[calc(100vh-8rem)] grid-cols-1 gap-0.5 overflow-y-auto border-l border-border">
                {headings.map((heading) => (
                  <li key={heading.id}>
                    <button
                      type="button"
                      onClick={() => jumpTo(heading.id)}
                      className={cn(
                        '-ml-px block w-full truncate border-l-2 py-1 text-left text-[12.5px] transition',
                        heading.level === 3 ? 'pl-6' : 'pl-3',
                        activeHeading === heading.id
                          ? 'border-accent font-semibold text-accent'
                          : 'border-transparent text-fg-3 hover:border-border-strong hover:text-fg',
                      )}
                    >
                      {heading.text}
                    </button>
                  </li>
                ))}
              </ul>
            </nav>
          ) : null}
        </div>
      )}
    </section>
  )
}
