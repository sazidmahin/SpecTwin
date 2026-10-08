import { BrainCircuit, Check, CircleHelp, Eye, EyeOff, FileText, GitBranch, Home, LockKeyhole, Mail, Moon, Network, Plus, ShieldCheck, Sparkles, Sun, User, Users, Wand2, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useId, useState } from 'react'
import type { ReactNode } from 'react'
import { useTheme } from '../../../shared/theme'
import { BrandMark, cn } from '../../../shared/ui'

type AuthArtwork = 'lock' | 'profile' | 'mail' | 'question' | 'key' | 'home'
type AuthIconName = 'user' | 'mail' | 'lock' | 'eye' | 'home' | 'check' | 'plus' | 'help' | 'cube'

export function AuthFrame({ artwork, children }: { artwork: AuthArtwork; children: ReactNode }) {
  const { theme, toggleTheme } = useTheme()
  return (
    <main className="relative grid grid-cols-1 min-h-svh bg-bg bg-[image:var(--app-glow)] bg-no-repeat lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <section className="relative flex flex-col px-5 py-6 sm:px-10 lg:px-16">
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <BrandMark className="size-9" />
            <div className="font-display text-[19px] font-extrabold tracking-tight text-fg">SpecTwin</div>
          </div>
          <button
            type="button"
            onClick={toggleTheme}
            className="grid size-9 place-items-center rounded-lg border border-border bg-surface text-fg-2 shadow-[var(--elev-1)] transition hover:text-fg"
            aria-label="Toggle colour theme"
          >
            {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </button>
        </header>
        <div className="flex flex-1 items-center justify-center py-10">
          <div className="w-full max-w-[26rem] animate-rise-in">{children}</div>
        </div>
        <footer className="text-center text-xs text-fg-3 lg:text-left">&copy; {new Date().getFullYear()} SpecTwin</footer>
      </section>
      <AuthVisualPanel artwork={artwork} />
    </main>
  )
}

function AuthVisualPanel({ artwork }: { artwork: AuthArtwork }) {
  const isProfile = artwork === 'profile'
  return (
    <aside
      className="relative m-3 hidden overflow-hidden rounded-[28px] bg-[#0f1027] p-10 text-white lg:flex lg:flex-col lg:justify-between xl:p-14"
      aria-label="SpecTwin highlights"
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(600px_400px_at_85%_10%,rgba(139,92,246,0.45),transparent_60%),radial-gradient(500px_400px_at_0%_100%,rgba(79,70,229,0.5),transparent_60%)]" />
      <div className="pointer-events-none absolute inset-0 opacity-[0.07] [background-image:linear-gradient(rgba(255,255,255,0.6)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.6)_1px,transparent_1px)] [background-size:32px_32px] [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_75%)]" />

      <div className="relative">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[11px] font-semibold tracking-wide backdrop-blur">
          <Sparkles className="size-3.5 text-indigo-200" />
          AI-assisted requirements engineering
        </span>
      </div>

      <section className="relative my-10 grid grid-cols-1 gap-3" aria-hidden="true">
        <article className="rounded-2xl border border-white/10 bg-white/[0.07] p-5 backdrop-blur-md">
          <div className="flex items-center gap-2.5">
            <span className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-indigo-400 to-violet-500">
              <Wand2 className="size-4" />
            </span>
            <div>
              <strong className="block text-sm">AI Generation</strong>
              <span className="text-xs text-white/60">Generating SRS document…</span>
            </div>
            <span className="ml-auto rounded-full bg-emerald-400/15 px-2 py-0.5 text-[11px] font-semibold text-emerald-300">72%</span>
          </div>
          <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/10">
            <i className="block h-full w-[72%] rounded-full bg-gradient-to-r from-indigo-400 to-violet-400" />
          </div>
        </article>
        <div className="grid grid-cols-3 gap-3">
          <PreviewCard icon={FileText} label="SRS versions" value="v1.2" />
          <PreviewCard icon={GitBranch} label="Requirements" value="24" />
          <PreviewCard icon={Network} label="UML classes" value="18" />
        </div>
      </section>

      <div className="relative">
        <h2 className="max-w-md font-display text-3xl font-extrabold leading-tight tracking-tight xl:text-[34px]">
          {isProfile ? 'Write better SRS, faster with AI.' : 'All your SRS work, smarter with AI.'}
        </h2>
        <p className="mt-3 max-w-md text-sm leading-6 text-white/65">
          Capture requirements, generate IEEE-style SRS documents and turn them into UML class diagrams — in one workspace.
        </p>
        <div className="mt-8 grid grid-cols-2 gap-3 xl:grid-cols-4">
          {(isProfile ? signupFeatures : loginFeatures).map((feature) => (
            <FeatureChip {...feature} key={feature.title} />
          ))}
        </div>
      </div>
    </aside>
  )
}

function PreviewCard({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return (
    <article className="grid grid-cols-1 gap-1.5 rounded-2xl border border-white/10 bg-white/[0.06] p-4 backdrop-blur-md">
      <Icon className="size-4 text-indigo-200" />
      <strong className="font-display text-xl">{value}</strong>
      <small className="text-[11px] text-white/55">{label}</small>
    </article>
  )
}

const loginFeatures = [
  { icon: BrainCircuit, title: 'AI-Powered', label: 'Generation' },
  { icon: Network, title: 'Smart', label: 'Diagrams' },
  { icon: ShieldCheck, title: 'Version', label: 'Control' },
  { icon: Users, title: 'Team', label: 'Collaboration' },
]
const signupFeatures = [
  { icon: BrainCircuit, title: 'AI Writing', label: 'Generate & refine' },
  { icon: Network, title: 'Diagrams', label: 'Auto UML' },
  { icon: Users, title: 'Collaboration', label: 'Work together' },
  { icon: ShieldCheck, title: 'Enterprise', label: 'Secure & scalable' },
]

function FeatureChip({ icon: Icon, title, label }: { icon: LucideIcon; title: string; label: string }) {
  return (
    <span className="grid grid-cols-1 gap-1 rounded-xl border border-white/10 bg-white/[0.05] p-3">
      <Icon className="size-4 text-indigo-200" />
      <strong className="text-xs">{title}</strong>
      <small className="text-[10.5px] leading-4 text-white/55">{label}</small>
    </span>
  )
}

export function AuthField({ label, icon, type = 'text', value, placeholder, autoComplete, inputMode, required, minLength, error, onChange }: { label: string; icon: AuthIconName; type?: string; value: string; placeholder: string; autoComplete?: string; inputMode?: 'email' | 'numeric'; required?: boolean; minLength?: number; error?: string; onChange: (value: string) => void }) {
  const [isPasswordVisible, setIsPasswordVisible] = useState(false)
  const isPasswordField = type === 'password'
  const id = useId()
  return (
    <div className="grid grid-cols-1 gap-1.5">
      <label htmlFor={id} className="text-[13px] font-semibold text-fg">
        {label}
      </label>
      <span
        className={cn(
          'flex h-11 items-center gap-2.5 rounded-lg border bg-surface px-3 shadow-[var(--elev-1)] transition',
          error
            ? 'border-danger/60 ring-4 ring-danger/10'
            : 'border-border-strong hover:border-fg-3/50 focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/15',
        )}
      >
        <span className="text-fg-3">
          <AuthIcon name={icon} />
        </span>
        <input
          id={id}
          className="min-w-0 flex-1 bg-transparent text-sm text-fg outline-none placeholder:text-fg-3"
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
          autoComplete={autoComplete}
          inputMode={inputMode}
          minLength={minLength}
          placeholder={placeholder}
          required={required}
          type={isPasswordField && isPasswordVisible ? 'text' : type}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
        {isPasswordField ? (
          <button
            className="grid size-7 place-items-center rounded-md text-fg-3 transition hover:bg-surface-3 hover:text-fg"
            type="button"
            aria-label={isPasswordVisible ? 'Hide password' : 'Show password'}
            onClick={(event) => {
              event.preventDefault()
              setIsPasswordVisible((visible) => !visible)
            }}
          >
            {isPasswordVisible ? <EyeOff size={17} /> : <Eye size={17} />}
          </button>
        ) : null}
      </span>
      {error ? (
        <small id={`${id}-error`} className="text-xs font-medium text-danger">
          {error}
        </small>
      ) : null}
    </div>
  )
}

const authIcons: Record<AuthIconName, LucideIcon> = { check: Check, cube: X, eye: Eye, help: CircleHelp, home: Home, lock: LockKeyhole, mail: Mail, plus: Plus, user: User }
export function AuthIcon({ name }: { name: AuthIconName }) {
  const Icon = authIcons[name]
  return <Icon size={17} aria-hidden="true" />
}
export function AuthLinkButton({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button className="text-[13px] font-semibold text-accent transition hover:text-accent-dim hover:underline hover:underline-offset-4" type="button" onClick={onClick}>
      {children}
    </button>
  )
}
export function AuthPanelHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <header className="mb-7">
      <h1 className="font-display text-[28px] font-extrabold leading-tight tracking-tight text-fg sm:text-[32px]">{title}</h1>
      <p className="mt-2 text-sm leading-6 text-fg-2">{subtitle}</p>
    </header>
  )
}
