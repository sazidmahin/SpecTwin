import type { GenerationMode } from '../api'

export function relativeTime(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.round(diffMs / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days < 7) return `${days}d ago`
  return formatDate(iso)
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export function humanize(value: string) {
  const text = value.replaceAll('_', ' ').replaceAll('-', ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export const ENGINE_LABELS: Record<GenerationMode, string> = {
  rule_based: 'Rule-Based',
  ollama: 'Local AI (Ollama)',
  byok: 'AI provider',
  srsgen: 'SrsGen',
  ai: 'AI generation',
}

export const STAGE_LABELS: Record<string, string> = {
  input: 'Input',
  clarifications: 'Clarifications',
  'final-story': 'Final story',
  requirements: 'Requirements',
  'class-model': 'Class model',
  xml: 'Diagram XML',
}

export type StatusTone = 'success' | 'warning' | 'danger' | 'info' | 'muted' | 'accent'

export function runStatusTone(status: string): StatusTone {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'running') return 'info'
  if (status === 'approved') return 'accent'
  return 'warning'
}

export function runStatusLabel(status: string) {
  if (status === 'ready_for_review') return 'Needs review'
  return humanize(status)
}

export function slugify(value: string) {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
}
