import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { errorMessage, invitationApi } from '../../api'
import type { InvitationPreview } from '../../api'
import { navigate, routes } from '../../app/core/router'
import { useSession } from '../../app/core/session'
import { useAsync } from '../../app/core/useAsync'
import { humanize } from '../../shared/format'
import { Button, useFeedback } from '../../shared/ui'
import { Alert, AuthView } from '../auth/AuthView'
import { AuthFrame, AuthPanelHeader } from '../auth/components/AuthFrame'

const UNAVAILABLE: Record<string, string> = {
  accepted: 'This invitation has already been accepted.',
  revoked: 'This invitation was cancelled by the workspace admin.',
  expired: 'This invitation has expired. Ask the workspace admin to send a new one.',
}

function InviteSummary({ invite }: { invite: InvitationPreview }) {
  return (
    <>
      <strong className="text-fg">{invite.inviter_name}</strong> invited <strong className="text-fg">{invite.email}</strong> to join{' '}
      <strong className="text-fg">{invite.workspace_name}</strong> as {humanize(invite.role).toLowerCase()}.
    </>
  )
}

/**
 * Landing page for the emailed `#/invite/<token>` link. Signed-out visitors sign in (existing
 * account) or register (new email) right here; once signed in with the invited email they join.
 */
export function InvitePage({ token }: { token: string }) {
  const session = useSession()
  const { toast } = useFeedback()
  const preview = useAsync(() => invitationApi.preview(token), [token])
  const [joining, setJoining] = useState(false)
  const [joinError, setJoinError] = useState<string | null>(null)

  const invite = preview.data
  const leave = () => navigate(routes.dashboard(), undefined, { replace: true })

  if (preview.loading || (session.status === 'loading' && invite)) {
    return (
      <AuthFrame artwork="mail">
        <div className="grid place-items-center py-10">
          <Loader2 className="size-5 animate-spin text-fg-3" aria-label="Loading invitation" />
        </div>
      </AuthFrame>
    )
  }

  if (!invite || invite.status !== 'pending') {
    const message = invite ? UNAVAILABLE[invite.status] : preview.error ?? 'This invitation link is not valid.'
    return (
      <AuthFrame artwork="mail">
        <AuthPanelHeader title="Invitation unavailable" subtitle="This link can no longer be used." />
        <div className="grid gap-5">
          <Alert>{message}</Alert>
          <Button size="lg" onClick={leave}>
            {session.status === 'signed-out' ? 'Go to sign in' : 'Go to dashboard'}
          </Button>
        </div>
      </AuthFrame>
    )
  }

  if (session.status === 'signed-out') {
    return (
      <AuthView
        key={invite.account_exists ? 'login' : 'register'}
        initialView={invite.account_exists ? 'login' : 'register'}
        initialEmail={invite.email}
        notice={
          <Alert tone="info">
            <InviteSummary invite={invite} />{' '}
            {invite.account_exists ? 'Sign in with that email to accept.' : 'Create an account with that email to accept.'}
          </Alert>
        }
      />
    )
  }

  const emailMatches = session.user?.email.trim().toLowerCase() === invite.email

  async function join() {
    setJoining(true)
    setJoinError(null)
    try {
      const membership = await invitationApi.accept(token)
      await session.refresh()
      session.selectWorkspace(membership.workspace.id)
      toast('Welcome aboard', { description: `You joined ${membership.workspace.name}.` })
      leave()
    } catch (caught) {
      setJoinError(errorMessage(caught, 'Could not accept the invitation'))
    } finally {
      setJoining(false)
    }
  }

  return (
    <AuthFrame artwork="home">
      <AuthPanelHeader title={`Join ${invite.workspace_name}`} subtitle="You have been invited to a SpecTwin workspace." />
      <div className="grid gap-5">
        <Alert tone="info">
          <InviteSummary invite={invite} />
        </Alert>
        {emailMatches ? null : (
          <Alert>
            You are signed in as {session.user?.email}. Sign out and sign in as {invite.email} to accept this invitation.
          </Alert>
        )}
        {joinError ? <Alert>{joinError}</Alert> : null}
        {emailMatches ? (
          <Button size="lg" onClick={() => void join()} disabled={joining}>
            {joining ? <Loader2 className="animate-spin" /> : null} Join workspace
          </Button>
        ) : (
          <Button size="lg" onClick={session.signOut}>
            Sign out
          </Button>
        )}
        <Button variant="ghost" onClick={leave}>
          Not now
        </Button>
      </div>
    </AuthFrame>
  )
}
