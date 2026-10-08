import { useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Check, Info, Loader2 } from 'lucide-react'
import { authApi, errorMessage } from '../../api'
import { navigate } from '../../app/core/router'
import { useSession } from '../../app/core/session'
import { cn, useFeedback } from '../../shared/ui'
import { AuthField, AuthFrame, AuthLinkButton, AuthPanelHeader } from './components/AuthFrame'

export type AuthViewName = 'login' | 'register' | 'verify' | 'forgot' | 'sent' | 'reset'
type View = AuthViewName

const submitClass =
  'inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-accent to-accent2-dim px-4 text-sm font-semibold text-white shadow-[0_10px_24px_-10px_color-mix(in_oklab,var(--color-accent)_90%,transparent)] transition hover:brightness-110 active:translate-y-px disabled:cursor-not-allowed disabled:opacity-55'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function SubmitButton({ busy, children }: { busy: boolean; children: ReactNode }) {
  return (
    <button className={submitClass} type="submit" disabled={busy}>
      {busy ? <Loader2 className="size-4 animate-spin" /> : null}
      {children}
    </button>
  )
}

export function Alert({ tone = 'error', children }: { tone?: 'error' | 'info'; children: ReactNode }) {
  return (
    <p
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn(
        'flex items-start gap-2 rounded-lg border px-3 py-2.5 text-[13px] leading-relaxed',
        tone === 'error' ? 'border-danger/25 bg-danger/[0.07] font-medium text-danger' : 'border-accent/20 bg-accent/[0.06] text-fg-2',
      )}
    >
      {tone === 'info' ? <Info className="mt-0.5 size-4 shrink-0 text-accent" /> : null}
      <span>{children}</span>
    </p>
  )
}

type AuthViewProps = {
  initialView?: AuthViewName
  initialEmail?: string
  /** Reset token taken from the emailed password reset link. */
  initialResetToken?: string
  /** Shown above the sign-in and sign-up forms, e.g. which workspace an invite is for. */
  notice?: ReactNode
}

export function AuthView({ initialView = 'login', initialEmail = '', initialResetToken = '', notice }: AuthViewProps = {}) {
  const { signIn, expiredNotice } = useSession()
  const { toast } = useFeedback()
  const [view, setView] = useState<View>(initialView)
  const [email, setEmail] = useState(initialEmail)
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [code, setCode] = useState('')
  const [devCode, setDevCode] = useState<string | null>(null)
  const [resetToken, setResetToken] = useState(initialResetToken)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function go(next: View) {
    setView(next)
    setErrors({})
    setFormError(null)
    setPassword('')
    setConfirmPassword('')
  }

  function clearError(field: string) {
    if (errors[field]) setErrors((current) => ({ ...current, [field]: '' }))
  }

  async function attempt(action: () => Promise<void>, fallback: string) {
    setBusy(true)
    setFormError(null)
    try {
      await action()
    } catch (caught) {
      setFormError(errorMessage(caught, fallback))
    } finally {
      setBusy(false)
    }
  }

  function validateEmail(next: Record<string, string>) {
    if (!email.trim()) next.email = 'Enter your email'
    else if (!EMAIL_PATTERN.test(email.trim())) next.email = 'Enter a valid email address'
  }

  function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const next: Record<string, string> = {}
    validateEmail(next)
    if (!password) next.password = 'Enter your password'
    setErrors(next)
    if (Object.values(next).some(Boolean)) return
    void attempt(async () => {
      await signIn(await authApi.login({ email: email.trim(), password }))
    }, 'Sign in failed')
  }

  function submitRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const next: Record<string, string> = {}
    if (!fullName.trim()) next.fullName = 'Enter your full name'
    validateEmail(next)
    if (password.length < 8) next.password = 'Use at least 8 characters'
    if (confirmPassword !== password) next.confirmPassword = 'Passwords do not match'
    setErrors(next)
    if (Object.values(next).some(Boolean)) return
    void attempt(async () => {
      const result = await authApi.register({ email: email.trim(), password, full_name: fullName.trim() })
      setDevCode(result.verification_code)
      setCode('')
      go('verify')
      toast('Check your email', { description: 'We sent you a 6-digit verification code.', tone: 'info' })
    }, 'Could not create your account')
  }

  function submitVerify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!/^\d{6}$/.test(code)) {
      setErrors({ code: 'Enter the 6-digit code' })
      return
    }
    void attempt(async () => {
      await signIn(await authApi.verifyEmail({ email: email.trim(), code }))
    }, 'Verification failed')
  }

  function resendCode() {
    void attempt(async () => {
      const result = await authApi.resendVerification(email.trim())
      setDevCode(result.verification_code)
      toast('A new code is on its way', { tone: 'info' })
    }, 'Could not resend the code')
  }

  function submitForgot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const next: Record<string, string> = {}
    validateEmail(next)
    setErrors(next)
    if (Object.values(next).some(Boolean)) return
    void attempt(async () => {
      const result = await authApi.forgotPassword(email.trim())
      // The token only comes back in local console mode; otherwise it is in the emailed link.
      if (result.reset_token) {
        setResetToken(result.reset_token)
        go('reset')
        toast('Development mode', { description: 'Reset token filled in from the console email.', tone: 'info' })
      } else {
        go('sent')
      }
    }, 'Could not request a password reset')
  }

  function submitReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const next: Record<string, string> = {}
    if (!resetToken.trim()) next.token = 'Enter the reset token'
    if (password.length < 8) next.password = 'Use at least 8 characters'
    if (confirmPassword !== password) next.confirmPassword = 'Passwords do not match'
    setErrors(next)
    if (Object.values(next).some(Boolean)) return
    void attempt(async () => {
      await authApi.resetPassword({ token: resetToken.trim(), new_password: password })
      // Leave the emailed link's route so a refresh doesn't reopen the spent token.
      if (initialResetToken) navigate('/', undefined, { replace: true })
      go('login')
      toast('Password updated', { description: 'Sign in with your new password.' })
    }, 'Could not reset your password')
  }

  if (view === 'verify') {
    return (
      <AuthFrame artwork="mail">
        <AuthPanelHeader title="Verify your email" subtitle={`Enter the 6-digit code we sent to ${email || 'your email'}.`} />
        <form className="grid gap-5" onSubmit={submitVerify} noValidate>
          <AuthField
            autoComplete="one-time-code"
            icon="lock"
            inputMode="numeric"
            label="Verification code"
            placeholder="123456"
            value={code}
            error={errors.code}
            onChange={(value) => {
              setCode(value.replace(/\D/g, '').slice(0, 6))
              clearError('code')
            }}
          />
          {devCode ? <Alert tone="info">Development mode: your code is <strong className="font-mono text-fg">{devCode}</strong>.</Alert> : null}
          {formError ? <Alert>{formError}</Alert> : null}
          <SubmitButton busy={busy}>Verify and continue</SubmitButton>
        </form>
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <AuthLinkButton onClick={resendCode}>Resend code</AuthLinkButton>
          <AuthLinkButton onClick={() => go('register')}>Use a different email</AuthLinkButton>
        </div>
      </AuthFrame>
    )
  }

  if (view === 'forgot') {
    return (
      <AuthFrame artwork="question">
        <AuthPanelHeader title="Forgot your password?" subtitle="Enter your account email and we'll send you a link to reset your password." />
        <form className="grid gap-5" onSubmit={submitForgot} noValidate>
          <AuthField
            autoComplete="email"
            icon="mail"
            inputMode="email"
            label="Email address"
            placeholder="you@example.com"
            type="email"
            value={email}
            error={errors.email}
            onChange={(value) => {
              setEmail(value)
              clearError('email')
            }}
          />
          {formError ? <Alert>{formError}</Alert> : null}
          <SubmitButton busy={busy}>Send reset link</SubmitButton>
        </form>
        <footer className="mt-7 text-center">
          <AuthLinkButton onClick={() => go('login')}>Back to sign in</AuthLinkButton>
        </footer>
      </AuthFrame>
    )
  }

  if (view === 'sent') {
    return (
      <AuthFrame artwork="mail">
        <AuthPanelHeader title="Check your email" subtitle={`If an account exists for ${email || 'that email'}, we sent a link to reset your password.`} />
        <Alert tone="info">The link expires soon. Didn't get it? Check your spam folder or request another one.</Alert>
        <footer className="mt-7 flex flex-wrap items-center justify-between gap-3">
          <AuthLinkButton onClick={() => go('forgot')}>Send another link</AuthLinkButton>
          <AuthLinkButton onClick={() => go('login')}>Back to sign in</AuthLinkButton>
        </footer>
      </AuthFrame>
    )
  }

  if (view === 'reset') {
    const rules = [
      { label: 'At least 8 characters', passed: password.length >= 8 },
      { label: 'Upper and lower case letters', passed: /[a-z]/.test(password) && /[A-Z]/.test(password) },
      { label: 'A number or symbol', passed: /[0-9\W_]/.test(password) },
    ]
    return (
      <AuthFrame artwork="key">
        <AuthPanelHeader title="Set a new password" subtitle="Paste the reset token from your email and choose a new password." />
        <form className="grid gap-4" onSubmit={submitReset} noValidate>
          <AuthField
            icon="lock"
            label="Reset token"
            placeholder="Paste your reset token"
            value={resetToken}
            error={errors.token}
            onChange={(value) => {
              setResetToken(value)
              clearError('token')
            }}
          />
          <AuthField
            autoComplete="new-password"
            icon="lock"
            label="New password"
            placeholder="Create a strong password"
            type="password"
            value={password}
            error={errors.password}
            onChange={(value) => {
              setPassword(value)
              clearError('password')
            }}
          />
          <ul className="grid gap-1.5 rounded-lg border border-border bg-surface-2 p-3 text-xs text-fg-3">
            {rules.map((rule) => (
              <li key={rule.label} className={cn('flex items-center gap-2', rule.passed && 'font-semibold text-success')}>
                <span className={cn('grid size-4 place-items-center rounded-full', rule.passed ? 'bg-success/15' : 'bg-surface-3')}>
                  <Check size={11} strokeWidth={3} />
                </span>
                {rule.label}
              </li>
            ))}
          </ul>
          <AuthField
            autoComplete="new-password"
            icon="lock"
            label="Confirm new password"
            placeholder="Repeat the new password"
            type="password"
            value={confirmPassword}
            error={errors.confirmPassword}
            onChange={(value) => {
              setConfirmPassword(value)
              clearError('confirmPassword')
            }}
          />
          {formError ? <Alert>{formError}</Alert> : null}
          <SubmitButton busy={busy}>Update password</SubmitButton>
        </form>
        <footer className="mt-7 text-center">
          <AuthLinkButton onClick={() => go('login')}>Back to sign in</AuthLinkButton>
        </footer>
      </AuthFrame>
    )
  }

  const registering = view === 'register'

  return (
    <AuthFrame artwork={registering ? 'profile' : 'lock'}>
      <AuthPanelHeader
        title={registering ? 'Create your account' : 'Welcome back'}
        subtitle={registering ? 'Free for everyone — start turning ideas into specifications.' : 'Sign in to continue to your workspace.'}
      />
      {notice ? <div className="mb-5">{notice}</div> : null}
      {expiredNotice && !registering ? (
        <div className="mb-5">
          <Alert tone="info">Your session expired. Please sign in again.</Alert>
        </div>
      ) : null}
      <form className="grid gap-4" onSubmit={registering ? submitRegister : submitLogin} noValidate>
        {registering ? (
          <AuthField
            autoComplete="name"
            icon="user"
            label="Full name"
            placeholder="Your name"
            value={fullName}
            error={errors.fullName}
            onChange={(value) => {
              setFullName(value)
              clearError('fullName')
            }}
          />
        ) : null}
        <AuthField
          autoComplete="email"
          icon="mail"
          inputMode="email"
          label="Email address"
          placeholder="you@example.com"
          type="email"
          value={email}
          error={errors.email}
          onChange={(value) => {
            setEmail(value)
            clearError('email')
          }}
        />
        <AuthField
          autoComplete={registering ? 'new-password' : 'current-password'}
          icon="lock"
          label="Password"
          placeholder={registering ? 'At least 8 characters' : 'Your password'}
          type="password"
          value={password}
          error={errors.password}
          onChange={(value) => {
            setPassword(value)
            clearError('password')
          }}
        />
        {registering ? (
          <AuthField
            autoComplete="new-password"
            icon="lock"
            label="Confirm password"
            placeholder="Repeat your password"
            type="password"
            value={confirmPassword}
            error={errors.confirmPassword}
            onChange={(value) => {
              setConfirmPassword(value)
              clearError('confirmPassword')
            }}
          />
        ) : (
          <div className="-mt-1 flex justify-end">
            <AuthLinkButton onClick={() => go('forgot')}>Forgot password?</AuthLinkButton>
          </div>
        )}
        {formError ? <Alert>{formError}</Alert> : null}
        <SubmitButton busy={busy}>{registering ? 'Create account' : 'Sign in'}</SubmitButton>
      </form>
      <footer className="mt-7 flex items-center justify-center gap-2 text-[13px] text-fg-2">
        <span>{registering ? 'Already have an account?' : "Don't have an account?"}</span>
        <AuthLinkButton onClick={() => go(registering ? 'login' : 'register')}>{registering ? 'Sign in' : 'Create account'}</AuthLinkButton>
      </footer>
    </AuthFrame>
  )
}
