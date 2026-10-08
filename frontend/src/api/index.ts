import { request, requestText } from './client'
import type { ClassModelerMode, ClassModelerResult, LlmProvider, OllamaModels } from './classModelerTypes'
import type {
  AdminAuditLog,
  AdminLlmCall,
  AdminOverview,
  AdminUser,
  AiCredential,
  AiProviderId,
  AiProviderSetting,
  AuthSession,
  CurrentUserResponse,
  Diagram,
  DiagramDetail,
  DiagramVersion,
  GenerationMode,
  InvitationPreview,
  PipelineRun,
  PipelineRunSummary,
  PipelineStage,
  PipelineStageRevision,
  Project,
  PromptTemplate,
  SearchResults,
  SrsDocument,
  Workspace,
  WorkspaceInvitation,
  WorkspaceMember,
  WorkspaceMembership,
  WorkspaceRole,
} from './types'

export * from './client'
export type * from './types'
export type * from './classModelerTypes'

const ws = (workspaceId: string) => `/workspaces/${workspaceId}`
const project = (workspaceId: string, projectId: string) => `${ws(workspaceId)}/projects/${projectId}`

export const authApi = {
  login: (payload: { email: string; password: string }) =>
    request<AuthSession>('/auth/login', { method: 'POST', body: payload, auth: false }),
  register: (payload: { email: string; password: string; full_name: string }) =>
    request<{ message: string; verification_code: string | null }>('/auth/register', {
      method: 'POST',
      body: payload,
      auth: false,
    }),
  verifyEmail: (payload: { email: string; code: string }) =>
    request<AuthSession>('/auth/verify-email', { method: 'POST', body: payload, auth: false }),
  resendVerification: (email: string) =>
    request<{ message: string; verification_code: string | null }>('/auth/resend-verification-code', {
      method: 'POST',
      body: { email },
      auth: false,
    }),
  forgotPassword: (email: string) =>
    request<{ message: string; reset_token: string | null }>('/auth/forgot-password', {
      method: 'POST',
      body: { email },
      auth: false,
    }),
  resetPassword: (payload: { token: string; new_password: string }) =>
    request<{ message: string }>('/auth/reset-password', { method: 'POST', body: payload, auth: false }),
  me: () => request<CurrentUserResponse>('/auth/me'),
}

export const workspaceApi = {
  list: () => request<WorkspaceMembership[]>('/workspaces'),
  createOrganization: (payload: { name: string; slug: string }) =>
    request<WorkspaceMembership>('/workspaces', { method: 'POST', body: { ...payload, type: 'organization' } }),
  members: (workspaceId: string) => request<WorkspaceMember[]>(`${ws(workspaceId)}/members`),
  invite: (workspaceId: string, payload: { email: string; role: Exclude<WorkspaceRole, 'owner'> }) =>
    request<WorkspaceInvitation>(`${ws(workspaceId)}/members/invite`, { method: 'POST', body: payload }),
  invitations: (workspaceId: string) => request<WorkspaceInvitation[]>(`${ws(workspaceId)}/invitations`),
  revokeInvitation: (workspaceId: string, invitationId: string) =>
    request<void>(`${ws(workspaceId)}/invitations/${invitationId}`, { method: 'DELETE' }),
  updateRole: (workspaceId: string, memberId: string, role: Exclude<WorkspaceRole, 'owner'>) =>
    request<WorkspaceMember>(`${ws(workspaceId)}/members/${memberId}`, { method: 'PATCH', body: { role } }),
  removeMember: (workspaceId: string, memberId: string) =>
    request<void>(`${ws(workspaceId)}/members/${memberId}`, { method: 'DELETE' }),
  search: (workspaceId: string, q: string) => request<SearchResults>(`${ws(workspaceId)}/search`, { query: { q } }),
}

export const invitationApi = {
  preview: (token: string) => request<InvitationPreview>(`/invitations/${encodeURIComponent(token)}`, { auth: false }),
  accept: (token: string) =>
    request<WorkspaceMembership>(`/invitations/${encodeURIComponent(token)}/accept`, { method: 'POST' }),
}

export const projectApi = {
  list: (workspaceId: string) => request<Project[]>(`${ws(workspaceId)}/projects`),
  get: (workspaceId: string, projectId: string) => request<Project>(project(workspaceId, projectId)),
  create: (workspaceId: string, payload: { name: string; description: string | null }) =>
    request<Project>(`${ws(workspaceId)}/projects`, { method: 'POST', body: payload }),
  update: (workspaceId: string, projectId: string, payload: { name?: string; description?: string | null }) =>
    request<Project>(project(workspaceId, projectId), { method: 'PATCH', body: payload }),
  archive: (workspaceId: string, projectId: string) =>
    request<Project>(`${project(workspaceId, projectId)}/archive`, { method: 'POST' }),
}

export const pipelineApi = {
  listWorkspace: (workspaceId: string) => request<PipelineRunSummary[]>(`${ws(workspaceId)}/generation-pipelines`),
  listProject: (workspaceId: string, projectId: string) =>
    request<PipelineRunSummary[]>(`${project(workspaceId, projectId)}/generation-pipelines`),
  get: (workspaceId: string, projectId: string, runId: string) =>
    request<PipelineRun>(`${project(workspaceId, projectId)}/generation-pipelines/${runId}`),
  create: (
    workspaceId: string,
    projectId: string,
    payload: { title: string; raw_text: string; generation_mode: GenerationMode },
  ) => request<PipelineRun>(`${project(workspaceId, projectId)}/generation-pipelines`, { method: 'POST', body: payload }),
  rename: (workspaceId: string, projectId: string, runId: string, title: string) =>
    request<PipelineRun>(`${project(workspaceId, projectId)}/generation-pipelines/${runId}`, {
      method: 'PATCH',
      body: { title },
    }),
  remove: (workspaceId: string, projectId: string, runId: string) =>
    request<void>(`${project(workspaceId, projectId)}/generation-pipelines/${runId}`, { method: 'DELETE' }),
  saveStage: (
    workspaceId: string,
    projectId: string,
    runId: string,
    stage: PipelineStage,
    payload: Record<string, unknown>,
    expectedVersion?: number,
  ) =>
    request<PipelineStageRevision>(
      `${project(workspaceId, projectId)}/generation-pipelines/${runId}/stages/${stage}/revisions`,
      { method: 'POST', body: { payload, expected_version: expectedVersion } },
    ),
  approveStage: (workspaceId: string, projectId: string, runId: string, stage: PipelineStage, versionNumber: number) =>
    request<PipelineRun>(`${project(workspaceId, projectId)}/generation-pipelines/${runId}/stages/${stage}/approve`, {
      method: 'POST',
      body: { version_number: versionNumber, proceed: true },
    }),
  next: (workspaceId: string, projectId: string, runId: string) =>
    request<PipelineRun>(`${project(workspaceId, projectId)}/generation-pipelines/${runId}/next`, { method: 'POST' }),
  reopenStage: (workspaceId: string, projectId: string, runId: string, stage: PipelineStage) =>
    request<PipelineStageRevision>(
      `${project(workspaceId, projectId)}/generation-pipelines/${runId}/stages/${stage}/reopen`,
      { method: 'POST' },
    ),
}

export const srsApi = {
  listWorkspace: (workspaceId: string) => request<SrsDocument[]>(`${ws(workspaceId)}/srs-documents`),
  listProject: (workspaceId: string, projectId: string) => request<SrsDocument[]>(`${project(workspaceId, projectId)}/srs`),
  get: (workspaceId: string, projectId: string, documentId: string) =>
    request<SrsDocument>(`${project(workspaceId, projectId)}/srs/${documentId}`),
  update: (
    workspaceId: string,
    projectId: string,
    documentId: string,
    payload: { title?: string; content_markdown?: string },
  ) => request<SrsDocument>(`${project(workspaceId, projectId)}/srs/${documentId}`, { method: 'PATCH', body: payload }),
  remove: (workspaceId: string, projectId: string, documentId: string) =>
    request<void>(`${project(workspaceId, projectId)}/srs/${documentId}`, { method: 'DELETE' }),
  exportMarkdown: (workspaceId: string, projectId: string, documentId: string) =>
    requestText(`${project(workspaceId, projectId)}/srs/${documentId}/export`),
}

export const diagramApi = {
  listWorkspace: (workspaceId: string) => request<Diagram[]>(`${ws(workspaceId)}/diagrams`),
  listProject: (workspaceId: string, projectId: string) => request<Diagram[]>(`${project(workspaceId, projectId)}/diagrams`),
  get: (workspaceId: string, projectId: string, diagramId: string) =>
    request<DiagramDetail>(`${project(workspaceId, projectId)}/diagrams/${diagramId}`),
  create: (
    workspaceId: string,
    projectId: string,
    payload: { title: string; diagram_type: string; drawio_xml: string; diagram_json?: string | null },
  ) => request<DiagramDetail>(`${project(workspaceId, projectId)}/diagrams`, { method: 'POST', body: payload }),
  rename: (workspaceId: string, projectId: string, diagramId: string, title: string) =>
    request<Diagram>(`${project(workspaceId, projectId)}/diagrams/${diagramId}`, { method: 'PATCH', body: { title } }),
  remove: (workspaceId: string, projectId: string, diagramId: string) =>
    request<void>(`${project(workspaceId, projectId)}/diagrams/${diagramId}`, { method: 'DELETE' }),
  versions: (workspaceId: string, projectId: string, diagramId: string) =>
    request<DiagramVersion[]>(`${project(workspaceId, projectId)}/diagrams/${diagramId}/versions`),
  saveVersion: (workspaceId: string, projectId: string, diagramId: string, drawioXml: string) =>
    request<DiagramVersion>(`${project(workspaceId, projectId)}/diagrams/${diagramId}/versions`, {
      method: 'POST',
      body: { drawio_xml: drawioXml },
    }),
  exportDrawio: (workspaceId: string, projectId: string, diagramId: string) =>
    requestText(`${project(workspaceId, projectId)}/diagrams/${diagramId}/export`),
}

export const classModelerApi = {
  generate: (
    workspaceId: string,
    payload: { text: string; mode: ClassModelerMode; project_id?: string; llm_provider?: LlmProvider; model_name?: string },
  ) => request<ClassModelerResult>(`${ws(workspaceId)}/class-modeler/generate`, { method: 'POST', body: payload }),
  ollamaModels: (workspaceId: string) => request<OllamaModels>(`${ws(workspaceId)}/class-modeler/ollama-models`),
  /** Remember a model the user fixed, so the same text stops producing the same
   * mistake. `remembered` is false when nothing was stored. */
  rememberCorrection: (
    workspaceId: string,
    payload: {
      text: string
      project_id: string
      generation_mode: string
      wrong_model: ClassModelerResult['model']
      corrected_model: ClassModelerResult['model']
    },
  ) => request<{ remembered: boolean }>(`${ws(workspaceId)}/class-modeler/corrections`, { method: 'POST', body: payload }),
}

const aiBase = '/users/me/ai-settings'
export const aiSettingsApi = {
  providers: () => request<AiProviderSetting[]>(`${aiBase}/providers`),
  hosted: () => request<{ available: boolean }>(`${aiBase}/hosted`),
  models: (provider: AiProviderId) => request<string[]>(`${aiBase}/credentials/${provider}/models`),
  save: (provider: AiProviderId, payload: { api_key: string; selected_model: string; is_default: boolean }) =>
    request<AiCredential>(`${aiBase}/credentials/${provider}`, { method: 'PUT', body: payload }),
  patch: (provider: AiProviderId, payload: { selected_model?: string; is_default?: boolean }) =>
    request<AiCredential>(`${aiBase}/credentials/${provider}`, { method: 'PATCH', body: payload }),
  test: (provider: AiProviderId) => request<AiCredential>(`${aiBase}/credentials/${provider}/test`, { method: 'POST' }),
  remove: (provider: AiProviderId) => request<void>(`${aiBase}/credentials/${provider}`, { method: 'DELETE' }),
}

export const adminApi = {
  overview: () => request<AdminOverview>('/admin/overview'),
  users: () => request<AdminUser[]>('/admin/users'),
  workspaces: () => request<Workspace[]>('/admin/workspaces'),
  projects: () => request<Project[]>('/admin/projects'),
  pipelineRuns: () => request<PipelineRunSummary[]>('/admin/pipeline-runs'),
  llmCalls: () => request<AdminLlmCall[]>('/admin/llm-calls'),
  promptTemplates: () => request<PromptTemplate[]>('/admin/prompt-templates'),
  auditLogs: () => request<AdminAuditLog[]>('/admin/audit-logs'),
}
