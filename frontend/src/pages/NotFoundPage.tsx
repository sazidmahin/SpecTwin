import { Compass } from 'lucide-react'
import { href, routes } from '../app/core/router'
import { EmptyState, LinkButton } from '../shared/ui'

export function NotFoundPage({ message = 'This page does not exist or was moved.' }: { message?: string }) {
  return (
    <EmptyState
      icon={Compass}
      title="Nothing here"
      description={message}
      action={<LinkButton href={href(routes.dashboard())}>Go to dashboard</LinkButton>}
    />
  )
}
