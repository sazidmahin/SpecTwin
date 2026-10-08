export type AuthUser = {
  id: string
  email: string
  full_name: string
  avatar_url: string | null
  status: string
  platform_role?: string
  is_platform_admin?: boolean
  created_at: string
  updated_at: string
}

export type AuthSession = {
  access_token: string
  token_type: string
  user: AuthUser
}

export type WorkspaceRole = 'owner' | 'admin' | 'member' | 'viewer'

export type Workspace = {
  id: string
  name: string
  slug: string
  type: 'personal' | 'organization' | string
  owner_user_id: string
  status: string
  created_at: string
  updated_at: string
}

export type WorkspaceMembership = {
  workspace: Workspace
  role: WorkspaceRole
  status: string
}

export type CurrentUserResponse = {
  user: AuthUser
  workspaces: WorkspaceMembership[]
}

export type WorkspaceMember = {
  id: string
  workspace_id: string
  user_id: string
  user: { id: string; email: string; full_name: string } | null
  role: WorkspaceRole
  status: string
  invited_by: string | null
  created_at: string
  updated_at: string
}

export type InvitationStatus = 'pending' | 'accepted' | 'revoked' | 'expired'

export type WorkspaceInvitation = {
  id: string
  workspace_id: string
  email: string
  role: WorkspaceRole
  status: InvitationStatus
  invited_by: string
  expires_at: string
  created_at: string
  updated_at: string
  /** Only set when the backend prints emails to its console (local development). */
  invite_url?: string | null
}

export type InvitationPreview = {
  workspace_name: string
  inviter_name: string
  email: string
  role: WorkspaceRole
  status: InvitationStatus
  expires_at: string
  account_exists: boolean
}

export type Project = {
  id: string
  workspace_id: string
  name: string
  description: string | null
  status: string
  created_by_user_id: string
  created_at: string
  updated_at: string
}

export type GenerationMode = 'rule_based' | 'srsgen' | 'byok' | 'ollama' | 'ai'
export type PipelineStage = 'input' | 'clarifications' | 'final-story' | 'requirements' | 'class-model' | 'xml'

export type PipelineStageRevision = {
  id: string
  stage_name: PipelineStage
  version_number: number
  status: string
  payload: Record<string, unknown>
  created_by_user_id: string
  approved_by_user_id: string | null
  approved_at: string | null
  created_at: string
  updated_at: string
}

export type PipelineRunSummary = {
  id: string
  workspace_id: string
  project_id: string
  project_name?: string | null
  title: string
  generation_mode: GenerationMode
  provider: string | null
  model_name: string | null
  current_stage: PipelineStage
  status: string
  created_by_user_id: string
  created_at: string
  updated_at: string
  srs_document_id: string | null
}

export type PipelineRun = Omit<PipelineRunSummary, 'project_name'> & {
  raw_text: string
  stages: PipelineStageRevision[]
}

export type SrsRequirement = {
  id: string
  type: 'functional' | 'non_functional' | string
  statement: string
  actor: string | null
  category: string | null
  source: string | null
}

export type SrsDocument = {
  id: string
  workspace_id: string
  project_id: string
  pipeline_run_id: string | null
  diagram_id: string | null
  title: string
  status: string
  content_markdown: string
  content_json: {
    requirements?: SrsRequirement[]
    generationMode?: GenerationMode
    classCount?: number
    relationshipCount?: number
    editedManually?: boolean
    [key: string]: unknown
  }
  created_by_user_id: string
  created_at: string
  updated_at: string
}

export type Diagram = {
  id: string
  workspace_id: string
  project_id: string
  title: string
  diagram_type: string
  source: 'manual' | 'generated' | string
  status: string
  current_version: number
  created_by_user_id: string
  created_at: string
  updated_at: string
}

export type DiagramVersion = {
  id: string
  workspace_id: string
  project_id: string
  diagram_id: string
  version_number: number
  drawio_xml: string
  diagram_json: string | null
  created_by_user_id: string
  created_at: string
}

export type DiagramDetail = Diagram & { current: DiagramVersion }

export type SearchHit = { id: string; project_id: string; title: string; subtitle: string | null }
export type SearchResults = { projects: SearchHit[]; documents: SearchHit[]; runs: SearchHit[]; diagrams: SearchHit[] }

export type AiProviderId = 'openai' | 'anthropic' | 'gemini'

export type AiCredential = {
  id: string
  provider: AiProviderId
  configured: boolean
  key_last_four: string
  selected_model: string
  is_default: boolean
  status: string
  validated_at: string | null
  last_used_at: string | null
  created_at: string
  updated_at: string
  test_response?: string | null
}

export type AiProviderSetting = {
  provider: AiProviderId
  label: string
  models: string[]
  default_model: string
  credential: AiCredential | null
}

export type PromptTemplate = {
  id: string
  name: string
  version: number
  purpose: string
  template_text: string
  status: string
  created_at: string
  updated_at: string
}

export type AdminOverview = {
  users: number
  workspaces: number
  projects: number
  pipeline_runs: number
  completed_runs: number
  srs_documents: number
  diagrams: number
  llm_calls: number
}

export type AdminUser = AuthUser & { platform_role: string; is_platform_admin: boolean }

export type AdminLlmCall = {
  id: string
  workspace_id: string
  project_id: string
  pipeline_run_id: string | null
  provider: string
  model_name: string
  status: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  error_message: string | null
  created_at: string
}

export type AdminAuditLog = {
  id: string
  admin_user_id: string
  action: string
  target_type: string
  target_id: string | null
  metadata: Record<string, unknown> | null
  ip_address: string | null
  created_at: string
}
