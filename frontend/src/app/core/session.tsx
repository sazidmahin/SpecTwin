import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { UNAUTHORIZED_EVENT, authApi, setAccessToken } from '../../api'
import type { AuthSession, AuthUser, WorkspaceMembership } from '../../api'

const SESSION_KEY = 'spl3.auth.session'
const WORKSPACE_KEY = 'spl3.workspace.active'

function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStorage(key: string, value: string | null) {
  try {
    if (value === null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch {
    // Storage may be unavailable (private mode); the session still works for this tab.
  }
}

function readStoredSession(): AuthSession | null {
  const stored = readStorage(SESSION_KEY)
  if (!stored) return null
  try {
    return JSON.parse(stored) as AuthSession
  } catch {
    writeStorage(SESSION_KEY, null)
    return null
  }
}

type SessionContextValue = {
  status: 'loading' | 'signed-out' | 'ready'
  user: AuthUser | null
  workspaces: WorkspaceMembership[]
  workspace: WorkspaceMembership | null
  workspaceId: string
  isSuperAdmin: boolean
  canManageWorkspace: boolean
  canEdit: boolean
  signIn: (session: AuthSession) => Promise<void>
  signOut: () => void
  selectWorkspace: (workspaceId: string) => void
  refresh: () => Promise<void>
  expiredNotice: boolean
}

const SessionContext = createContext<SessionContextValue | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(() => {
    const stored = readStoredSession()
    setAccessToken(stored?.access_token ?? null)
    return stored
  })
  const [user, setUser] = useState<AuthUser | null>(session?.user ?? null)
  const [workspaces, setWorkspaces] = useState<WorkspaceMembership[]>([])
  const [loaded, setLoaded] = useState(false)
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(() => readStorage(WORKSPACE_KEY))
  const [expiredNotice, setExpiredNotice] = useState(false)

  const signOut = useCallback(() => {
    writeStorage(SESSION_KEY, null)
    writeStorage(WORKSPACE_KEY, null)
    setActiveWorkspaceId(null)
    setAccessToken(null)
    setSession(null)
    setUser(null)
    setWorkspaces([])
    setLoaded(false)
  }, [])

  const load = useCallback(async () => {
    const me = await authApi.me()
    setUser(me.user)
    setWorkspaces(me.workspaces)
    setLoaded(true)
  }, [])

  useEffect(() => {
    if (!session) return
    let cancelled = false
    authApi
      .me()
      .then((me) => {
        if (cancelled) return
        setUser(me.user)
        setWorkspaces(me.workspaces)
      })
      .catch(() => {
        // A 401 is handled by the unauthorized listener; anything else keeps the cached user.
      })
      .finally(() => {
        if (!cancelled) setLoaded(true)
      })
    return () => {
      cancelled = true
    }
  }, [session])

  useEffect(() => {
    const onUnauthorized = () => {
      if (readStoredSession()) setExpiredNotice(true)
      signOut()
    }
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [signOut])

  const signIn = useCallback(async (next: AuthSession) => {
    writeStorage(SESSION_KEY, JSON.stringify(next))
    setAccessToken(next.access_token)
    setExpiredNotice(false)
    setUser(next.user)
    setLoaded(false)
    setSession(next)
  }, [])

  const selectWorkspace = useCallback((workspaceId: string) => {
    writeStorage(WORKSPACE_KEY, workspaceId)
    setActiveWorkspaceId(workspaceId)
  }, [])

  const workspace = useMemo(
    () =>
      workspaces.find((item) => item.workspace.id === activeWorkspaceId) ??
      workspaces.find((item) => item.workspace.type === 'personal') ??
      workspaces[0] ??
      null,
    [workspaces, activeWorkspaceId],
  )

  const value = useMemo<SessionContextValue>(() => {
    const role = workspace?.role
    return {
      status: !session ? 'signed-out' : loaded && user ? 'ready' : 'loading',
      user,
      workspaces,
      workspace,
      workspaceId: workspace?.workspace.id ?? '',
      isSuperAdmin: user?.platform_role === 'super_admin',
      canManageWorkspace: workspace?.workspace.type === 'organization' && (role === 'owner' || role === 'admin'),
      canEdit: role !== 'viewer',
      signIn,
      signOut,
      selectWorkspace,
      refresh: load,
      expiredNotice,
    }
  }, [session, loaded, user, workspaces, workspace, signIn, signOut, selectWorkspace, load, expiredNotice])

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useSession() {
  const context = useContext(SessionContext)
  if (!context) throw new Error('useSession must be used inside SessionProvider')
  return context
}
