import type { ReactNode } from 'react'
import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import { Boxes, Building2, FileText, Folder, History, LayoutDashboard, Loader2, Network, Settings, ShieldCheck, Users, WandSparkles } from 'lucide-react'
import { AuthView } from '../features/auth/AuthView'
import { FooterSection } from '../features/footer/FooterSection'
import { InvitePage } from '../features/invitations/InvitePage'
import { DashboardPage } from '../pages/DashboardPage'
import { DiagramsPage } from '../pages/DiagramsPage'
import { DocumentsPage } from '../pages/DocumentsPage'
import { GeneratePage } from '../pages/GeneratePage'
import { GenerationsPage } from '../pages/GenerationsPage'
import { MembersPage } from '../pages/MembersPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { ProjectDetailPage } from '../pages/ProjectDetailPage'
import { ProjectsPage } from '../pages/ProjectsPage'
import { SettingsPage } from '../pages/SettingsPage'
import { BrandMark, EmptyState, FeedbackProvider, LinkButton, TooltipProvider } from '../shared/ui'
const AdminPage = lazy(() => import('../pages/AdminPage').then((module) => ({ default: module.AdminPage })))
const ClassModelerRoute = lazy(() => import('../pages/ClassModelerRoute').then((module) => ({ default: module.ClassModelerRoute })))
const DiagramPage = lazy(() => import('../pages/DiagramPage').then((module) => ({ default: module.DiagramPage })))
const DocumentComparePage = lazy(() => import('../pages/DocumentComparePage').then((module) => ({ default: module.DocumentComparePage })))
const DocumentPage = lazy(() => import('../pages/DocumentPage').then((module) => ({ default: module.DocumentPage })))
const RunPage = lazy(() => import('../pages/RunPage').then((module) => ({ default: module.RunPage })))
import { Sidebar } from './Sidebar'
import type { NavGroup } from './Sidebar'
import { Topbar } from './Topbar'
import { LoadingState } from './components/PageStates'
import { href, navigate, routes, useRoute } from './core/router'
import type { Route } from './core/router'
import { SessionProvider, useSession } from './core/session'

type Resolved = { section: string; label: string; element: ReactNode }

/** Map the hash route to a page. `section` decides which sidebar item is highlighted. */
function resolve(route: Route): Resolved {
  const [first, second, third] = route.segments
  switch (first) {
    case undefined:
      return { section: 'dashboard', label: 'Dashboard', element: <DashboardPage /> }
    case 'projects':
      return second
        ? { section: 'projects', label: 'Project', element: <ProjectDetailPage key={second} projectId={second} tab={third} /> }
        : { section: 'projects', label: 'Projects', element: <ProjectsPage /> }
    case 'generate':
      return second && third
        ? { section: 'generations', label: 'Generation', element: <RunPage key={third} projectId={second} runId={third} /> }
        : { section: 'generate', label: 'Generate SRS', element: <GeneratePage /> }
    case 'generations':
      return { section: 'generations', label: 'Generations', element: <GenerationsPage /> }
    case 'documents':
      if (second === 'compare') {
        const leftId = route.query.get('a') ?? ''
        const rightId = route.query.get('b') ?? ''
        return { section: 'documents', label: 'Compare SRS documents', element: <DocumentComparePage leftId={leftId} rightId={rightId} /> }
      }
      return second && third
        ? { section: 'documents', label: 'SRS document', element: <DocumentPage key={third} projectId={second} documentId={third} /> }
        : { section: 'documents', label: 'SRS documents', element: <DocumentsPage /> }
    case 'diagrams':
      return second && third
        ? { section: 'diagrams', label: 'Diagram', element: <DiagramPage key={third} projectId={second} diagramId={third} /> }
        : { section: 'diagrams', label: 'Diagrams', element: <DiagramsPage /> }
    case 'class-modeler':
      return { section: 'class-modeler', label: 'Class modeler', element: <ClassModelerRoute /> }
    case 'settings':
      return { section: 'settings', label: 'Settings', element: <SettingsPage tab={second} /> }
    case 'members':
      return { section: 'members', label: 'Members', element: <MembersPage /> }
    case 'admin':
      return { section: 'admin', label: 'Admin', element: <AdminPage tab={second} /> }
    default:
      return { section: '', label: 'Not found', element: <NotFoundPage /> }
  }
}

function Shell() {
  const session = useSession()
  const route = useRoute()
  // The drawer closes itself on navigation because it is only open for the path it was opened on.
  const [navOpenedAt, setNavOpenedAt] = useState<string | null>(null)
  const mobileNavOpen = navOpenedAt === route.path
  const setMobileNavOpen = (open: boolean) => setNavOpenedAt(open ? route.path : null)
  const resolved = resolve(route)

  useEffect(() => {
    window.scrollTo({ top: 0 })
  }, [route.path])

  // Old bookmarks used `#projects` style hashes; route them to the new paths.
  useEffect(() => {
    const legacy: Record<string, string> = {
      '/overview': routes.dashboard(),
      '/srs': routes.documents(),
      '/diagram-editor': routes.diagrams(),
      '/class-diagram-generation': routes.classModeler(),
      '/generate-srs': routes.generate(),
      '/ai-jobs': routes.generations(),
      '/ai-settings': routes.settings('ai'),
      '/profile': routes.settings(),
    }
    if (legacy[route.path]) navigate(legacy[route.path], undefined, { replace: true })
  }, [route.path])

  const groups = useMemo<NavGroup[]>(() => {
    const result: NavGroup[] = [
      {
        items: [
          { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, path: routes.dashboard() },
          { id: 'projects', label: 'Projects', icon: Folder, path: routes.projects() },
        ],
      },
      {
        title: 'Specify',
        items: [
          { id: 'generate', label: 'Generate SRS', icon: WandSparkles, path: routes.generate() },
          { id: 'generations', label: 'Generations', icon: History, path: routes.generations() },
          { id: 'documents', label: 'SRS documents', icon: FileText, path: routes.documents() },
        ],
      },
      {
        title: 'Model',
        items: [
          { id: 'diagrams', label: 'Diagrams', icon: Network, path: routes.diagrams() },
          { id: 'class-modeler', label: 'Class modeler', icon: Boxes, path: routes.classModeler() },
        ],
      },
    ]
    const manage = [
      ...(session.canManageWorkspace ? [{ id: 'members', label: 'Members', icon: Users, path: routes.members() }] : []),
      ...(session.isSuperAdmin ? [{ id: 'admin', label: 'Admin console', icon: ShieldCheck, path: routes.admin() }] : []),
      { id: 'settings', label: 'Settings', icon: Settings, path: routes.settings() },
    ]
    result.push({ title: 'Manage', items: manage })
    return result
  }, [session.canManageWorkspace, session.isSuperAdmin])

  if (session.status === 'loading' || !session.user) {
    return (
      <div className="grid min-h-svh place-items-center bg-bg">
        <div className="flex flex-col items-center gap-4">
          <BrandMark className="size-12" />
          <Loader2 className="size-5 animate-spin text-fg-3" aria-label="Loading your workspace" />
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-svh bg-bg bg-[image:var(--app-glow)] bg-no-repeat">
      <Sidebar
        user={session.user}
        roleLabel={session.isSuperAdmin ? 'Platform admin' : session.workspace?.role ?? 'member'}
        groups={groups}
        activeSection={resolved.section}
        workspaces={session.workspaces}
        activeWorkspace={session.workspace ?? undefined}
        mobileOpen={mobileNavOpen}
        onMobileClose={() => setMobileNavOpen(false)}
        onSelectWorkspace={(workspaceId) => {
          session.selectWorkspace(workspaceId)
          navigate(routes.dashboard())
        }}
        onSignOut={session.signOut}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          workspaceId={session.workspaceId}
          workspaceName={session.workspace?.workspace.name ?? 'Workspace'}
          sectionLabel={resolved.label}
          user={session.user}
          onOpenNav={() => setMobileNavOpen(true)}
          onSignOut={session.signOut}
        />
        <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
          <div key={`${session.workspaceId}:${route.path}`} className="animate-fade-in">
            <Suspense fallback={<LoadingState rows={3} />}>
              {session.workspaceId || resolved.section === 'admin' || resolved.section === 'settings' ? resolved.element : <NoWorkspace />}
            </Suspense>
          </div>
          <FooterSection />
        </main>
      </div>
    </div>
  )
}

function NoWorkspace() {
  return (
    <EmptyState
      icon={Building2}
      title="You are not in a workspace yet"
      description="Create an organization workspace to start projects, or ask a teammate to add you to theirs."
      action={<LinkButton href={href(routes.settings('workspaces'))}>Create a workspace</LinkButton>}
    />
  )
}

function Gate() {
  const session = useSession()
  const route = useRoute()
  // The emailed invite link works signed in or out, so it sits outside the app shell.
  if (route.segments[0] === 'invite' && route.segments[1]) return <InvitePage key={route.segments[1]} token={route.segments[1]} />
  if (session.status === 'signed-out') return <AuthView />
  return <Shell />
}

export function App() {
  return (
    <TooltipProvider delayDuration={200}>
      <FeedbackProvider>
        <SessionProvider>
          <Gate />
        </SessionProvider>
      </FeedbackProvider>
    </TooltipProvider>
  )
}
