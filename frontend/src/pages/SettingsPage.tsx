import { useState } from 'react'
import type { FormEvent } from 'react'
import { Building2, CheckCircle2, KeyRound, Loader2, Moon, Plus, ShieldCheck, Sun, User } from 'lucide-react'
import { aiSettingsApi, errorMessage, workspaceApi } from '../api'
import type { AiProviderSetting } from '../api'
import { ErrorState, LoadingState } from '../app/components/PageStates'
import { href, navigate, routes } from '../app/core/router'
import { useSession } from '../app/core/session'
import { useAsync } from '../app/core/useAsync'
import { formatDate, humanize, slugify } from '../shared/format'
import { useTheme } from '../shared/theme'
import { Avatar, Button, Card, Chip, Field, Input, PageHeader, Select, cn, initials, useFeedback } from '../shared/ui'

const TABS = [
  { id: 'profile', label: 'Profile', icon: User },
  { id: 'ai', label: 'AI providers', icon: KeyRound },
  { id: 'workspaces', label: 'Workspaces', icon: Building2 },
] as const

export function SettingsPage({ tab }: { tab?: string }) {
  const active = TABS.some((item) => item.id === tab) ? tab : 'profile'
  return (
    <section className="grid grid-cols-1 gap-5">
      <PageHeader title="Settings" description="Your profile, your own AI provider keys and your workspaces." />
      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[13rem_minmax(0,1fr)]">
        <nav className="flex gap-1 overflow-x-auto lg:sticky lg:top-20 lg:flex-col" aria-label="Settings sections">
          {TABS.map((item) => {
            const Icon = item.icon
            const selected = item.id === active
            return (
              <a
                key={item.id}
                href={href(routes.settings(item.id === 'profile' ? undefined : item.id))}
                aria-current={selected ? 'page' : undefined}
                className={cn(
                  'flex shrink-0 items-center gap-2.5 whitespace-nowrap rounded-lg px-3 py-2 text-[13px] font-semibold transition',
                  selected ? 'bg-accent/10 text-accent' : 'text-fg-2 hover:bg-surface-3 hover:text-fg',
                )}
              >
                <Icon className="size-4" />
                {item.label}
              </a>
            )
          })}
        </nav>
        <div className="min-w-0">
          {active === 'profile' ? <ProfileSection /> : null}
          {active === 'ai' ? <AiProvidersSection /> : null}
          {active === 'workspaces' ? <WorkspacesSection /> : null}
        </div>
      </div>
    </section>
  )
}

function ProfileSection() {
  const { user, isSuperAdmin } = useSession()
  const { theme, toggleTheme } = useTheme()
  if (!user) return null
  return (
    <div className="grid grid-cols-1 gap-5">
      <Card className="flex flex-col gap-5 p-6 sm:flex-row sm:items-center">
        <Avatar name={user.full_name} className="size-16 text-xl" />
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-xl font-bold text-fg">{user.full_name}</h2>
          <p className="truncate text-[13.5px] text-fg-2">{user.email}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Chip tone="muted">Member since {formatDate(user.created_at)}</Chip>
            {isSuperAdmin ? (
              <Chip tone="accent">
                <ShieldCheck /> Platform admin
              </Chip>
            ) : null}
          </div>
        </div>
      </Card>
      <Card className="flex flex-col gap-4 p-6 sm:flex-row sm:items-center">
        <div className="min-w-0 flex-1">
          <h3 className="font-display text-[15px] font-bold text-fg">Appearance</h3>
          <p className="mt-0.5 text-[13px] text-fg-2">Switch between the light and dark theme. Your choice is remembered on this device.</p>
        </div>
        <Button variant="secondary" onClick={toggleTheme}>
          {theme === 'dark' ? <Sun /> : <Moon />} {theme === 'dark' ? 'Use light theme' : 'Use dark theme'}
        </Button>
      </Card>
    </div>
  )
}

function AiProvidersSection() {
  const providers = useAsync(() => aiSettingsApi.providers(), [])
  return (
    <div className="grid grid-cols-1 gap-4">
      <Card className="flex gap-3 border-accent/20 bg-accent/[0.05] p-4">
        <KeyRound className="mt-0.5 size-5 shrink-0 text-accent" />
        <p className="text-[13px] leading-relaxed text-fg-2">
          SpecTwin is free. The <strong className="text-fg">Rule-Based</strong>, <strong className="text-fg">local Ollama</strong> and{' '}
          <strong className="text-fg">AI generation</strong> engines all need no key of yours. To run a hosted model on your own account instead, add{' '}
          <em>your own</em> API key below — it is encrypted at rest and only used for your requests. The provider marked{' '}
          <strong className="text-fg">Active</strong> is the one the “Your AI provider” engine uses.
        </p>
      </Card>
      {providers.loading && !providers.data ? (
        <LoadingState rows={3} />
      ) : providers.error ? (
        <ErrorState message={providers.error} onRetry={providers.reload} />
      ) : (
        (providers.data ?? []).map((provider) => (
          <ProviderCard
            key={`${provider.provider}:${provider.credential?.updated_at ?? 'none'}`}
            provider={provider}
            onChanged={() => void providers.reload()}
          />
        ))
      )}
    </div>
  )
}

function ProviderCard({ provider, onChanged }: { provider: AiProviderSetting; onChanged: () => void }) {
  const { toast, confirm } = useFeedback()
  const credential = provider.credential
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState(credential?.selected_model ?? provider.default_model)
  const [models, setModels] = useState(provider.models)
  const [busy, setBusy] = useState<string | null>(null)
  const status = credential?.status ?? 'not configured'
  const modelOptions = Array.from(new Set([model, ...models].filter(Boolean)))

  async function run(label: string, action: () => Promise<void>) {
    setBusy(label)
    try {
      await action()
    } catch (caught) {
      toast(`${provider.label}: ${label} failed`, { description: errorMessage(caught), tone: 'error' })
    } finally {
      setBusy(null)
    }
  }

  const spinner = (label: string) => (busy === label ? <Loader2 className="animate-spin" /> : null)

  return (
    <Card className="grid grid-cols-1 gap-4 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="flex items-center gap-2 font-display text-[15px] font-bold text-fg">
            {provider.label}
            {credential?.is_default ? <Chip tone="accent">Active</Chip> : null}
          </h3>
          <p className="mt-0.5 text-[12.5px] text-fg-2">
            {credential?.configured ? `Key ending •••• ${credential.key_last_four}` : 'No API key saved'}
          </p>
        </div>
        <Chip tone={status === 'valid' ? 'success' : status === 'invalid' ? 'danger' : 'muted'}>{humanize(status)}</Chip>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field label="API key" htmlFor={`key-${provider.provider}`}>
          <Input
            id={`key-${provider.provider}`}
            type="password"
            autoComplete="off"
            value={apiKey}
            placeholder={credential ? 'Paste a new key to replace the saved one' : 'Paste your API key'}
            onChange={(event) => setApiKey(event.target.value)}
          />
        </Field>
        <Field label="Model" htmlFor={`model-${provider.provider}`}>
          <Select id={`model-${provider.provider}`} value={model} onChange={(event) => setModel(event.target.value)}>
            {modelOptions.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          disabled={busy !== null || !apiKey.trim()}
          onClick={() =>
            void run('Save', async () => {
              await aiSettingsApi.save(provider.provider, { api_key: apiKey.trim(), selected_model: model, is_default: credential?.is_default ?? true })
              setApiKey('')
              toast(`${provider.label} key saved`, { description: 'Run “Test connection” to verify it.' })
              onChanged()
            })
          }
        >
          {spinner('Save')} Save key
        </Button>
        {credential ? (
          <>
            <Button
              size="sm"
              variant="secondary"
              disabled={busy !== null}
              onClick={() =>
                void run('Test', async () => {
                  const result = await aiSettingsApi.test(provider.provider)
                  toast(result.status === 'valid' ? `${provider.label} is connected` : `${provider.label} key is not valid`, {
                    tone: result.status === 'valid' ? 'success' : 'error',
                  })
                  onChanged()
                })
              }
            >
              {spinner('Test') ?? <CheckCircle2 />} Test connection
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={busy !== null || model === credential.selected_model}
              onClick={() =>
                void run('Save model', async () => {
                  await aiSettingsApi.patch(provider.provider, { selected_model: model })
                  toast('Model updated', { description: model })
                  onChanged()
                })
              }
            >
              {spinner('Save model')} Save model
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={busy !== null}
              onClick={() =>
                void run('Load models', async () => {
                  const loaded = await aiSettingsApi.models(provider.provider)
                  setModels(loaded)
                  toast(`Loaded ${loaded.length} models`)
                })
              }
            >
              {spinner('Load models')} Refresh model list
            </Button>
            {!credential.is_default ? (
              <Button
                size="sm"
                variant="secondary"
                disabled={busy !== null}
                onClick={() =>
                  void run('Activate', async () => {
                    await aiSettingsApi.patch(provider.provider, { is_default: true })
                    toast(`${provider.label} is now your active provider`)
                    onChanged()
                  })
                }
              >
                {spinner('Activate')} Make active
              </Button>
            ) : null}
            <Button
              size="sm"
              variant="danger"
              disabled={busy !== null}
              onClick={async () => {
                if (!(await confirm({ title: `Remove your ${provider.label} key?`, description: 'Generations using this provider will stop working until you add a key again.', confirmLabel: 'Remove key' }))) return
                void run('Remove', async () => {
                  await aiSettingsApi.remove(provider.provider)
                  toast(`${provider.label} key removed`)
                  onChanged()
                })
              }}
            >
              Remove
            </Button>
          </>
        ) : null}
      </div>
    </Card>
  )
}

function WorkspacesSection() {
  const { workspaces, workspace, selectWorkspace, refresh } = useSession()
  const { toast } = useFeedback()
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [slugTouched, setSlugTouched] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const finalSlug = slug || slugify(name)
    if (!name.trim() || finalSlug.length < 3) {
      setError('Enter a name (the URL slug needs at least 3 characters).')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const created = await workspaceApi.createOrganization({ name: name.trim(), slug: finalSlug })
      await refresh()
      selectWorkspace(created.workspace.id)
      setName('')
      setSlug('')
      setSlugTouched(false)
      toast('Organization created', { description: `Switched to ${created.workspace.name}` })
      navigate(routes.members())
    } catch (caught) {
      setError(errorMessage(caught, 'Unable to create the organization'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="grid grid-cols-1 gap-5">
      <Card className="overflow-hidden">
        <div className="border-b border-border px-5 py-4">
          <h3 className="font-display text-[15px] font-bold text-fg">Your workspaces</h3>
          <p className="text-[13px] text-fg-2">Everything you create belongs to the active workspace.</p>
        </div>
        <ul className="divide-y divide-border">
          {workspaces.map((membership) => {
            const selected = membership.workspace.id === workspace?.workspace.id
            return (
              <li key={membership.workspace.id} className="flex flex-wrap items-center gap-3 px-5 py-3.5">
                <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-sky to-accent text-[11px] font-extrabold text-white">
                  {initials(membership.workspace.name, 'W')}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13.5px] font-semibold text-fg">{membership.workspace.name}</p>
                  <p className="text-xs text-fg-3">
                    {humanize(membership.workspace.type)} · {humanize(membership.role)}
                  </p>
                </div>
                {selected ? (
                  <Chip tone="accent">Active</Chip>
                ) : (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      selectWorkspace(membership.workspace.id)
                      toast(`Switched to ${membership.workspace.name}`)
                    }}
                  >
                    Switch
                  </Button>
                )}
              </li>
            )
          })}
        </ul>
      </Card>

      <Card className="p-5">
        <h3 className="font-display text-[15px] font-bold text-fg">New organization workspace</h3>
        <p className="mb-4 text-[13px] text-fg-2">Invite teammates and share projects, documents and diagrams.</p>
        <form className="grid grid-cols-1 gap-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end" onSubmit={create} noValidate>
          <Field label="Name" htmlFor="org-name">
            <Input
              id="org-name"
              value={name}
              maxLength={255}
              placeholder="Acme Inc."
              onChange={(event) => {
                setName(event.target.value)
                if (!slugTouched) setSlug(slugify(event.target.value))
              }}
            />
          </Field>
          <Field label="URL slug" htmlFor="org-slug">
            <Input
              id="org-slug"
              value={slug}
              maxLength={60}
              placeholder="acme"
              onChange={(event) => {
                setSlugTouched(true)
                setSlug(slugify(event.target.value))
              }}
            />
          </Field>
          <Button type="submit" disabled={saving}>
            {saving ? <Loader2 className="animate-spin" /> : <Plus />} Create
          </Button>
        </form>
        {error ? <p className="mt-3 text-[13px] font-medium text-danger" role="alert">{error}</p> : null}
      </Card>
    </div>
  )
}
