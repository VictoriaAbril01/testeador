export type EnvironmentName = 'development' | 'staging' | 'production' | 'other'
export type ExecutionStatus = 'pending' | 'queued' | 'running' | 'cancelling' | 'completed' | 'failed' | 'cancelled'

export interface Environment {
  id: string
  name: EnvironmentName
  base_url: string
  is_active: boolean
}

export interface Project {
  id: string
  name: string
  description: string | null
  base_url: string
  environment: EnvironmentName
  modality: 'blackbox' | 'whitebox' | 'hybrid'
  created_at: string
  is_active: boolean
  authorized_origins: string[]
  environments: Environment[]
}

export interface ProjectInput {
  name: string
  description?: string
  base_url: string
  environment: EnvironmentName
  modality: 'blackbox'
  authorized_origins: string[]
}

export interface CredentialInput {
  login_url: string
  username_selector: string
  password_selector: string
  submit_selector: string
  success_selector?: string
  success_url_pattern?: string
  username: string
  password: string
}

export interface CredentialReceipt {
  id: string
  project_id: string
  login_url: string
  auth_type: 'form'
  created_at: string
}

export interface ExecutionInput {
  project_id: string
  max_pages: number
  max_depth: number
  max_requests: number
  max_concurrency: number
  page_timeout_ms: number
  execution_timeout_ms: number
  slow_navigation_ms?: number | null
}

export interface Execution extends ExecutionInput {
  id: string
  retest_of_run_id: string | null
  retry_of_run_id: string | null
  status: ExecutionStatus
  cancellation_requested: boolean
  heartbeat_at: string | null
  requested_at: string
  started_at: string | null
  finished_at: string | null
  error_message: string | null
}

export interface ExecutionSummary {
  id: string
  project_id: string
  project_name: string
  modality: Project['modality']
  status: ExecutionStatus
  requested_at: string
  started_at: string | null
  finished_at: string | null
  finding_count: number
  retest_of_run_id: string | null
  retry_of_run_id: string | null
}

export interface ExecutionHistory {
  total: number
  limit: number
  offset: number
  items: ExecutionSummary[]
}

export interface Dashboard {
  total_projects: number
  total_executions: number
  executions_by_status: Partial<Record<ExecutionStatus, number>>
  total_findings: number
  findings_pending_confirmation: number
  recent_executions: ExecutionSummary[]
  recent_projects: Array<{ id: string; name: string; modality: Project['modality']; latest_execution: ExecutionSummary | null }>
}

export interface Finding {
  id: string
  run_id: string
  project_id: string
  environment: EnvironmentName
  fingerprint: string
  error_type: string
  severity: 'info' | 'low' | 'medium' | 'high' | 'critical'
  validation_status: string
  module_name: string | null
  page_name: string | null
  url: string | null
  element: string | null
  description: string
  expected_result: string | null
  observed_result: string
  reproduction_steps: unknown[] | null
  scenario: Record<string, unknown> | null
  created_at: string
}

export interface Evidence {
  id: string
  finding_id: string
  kind: string
  size_bytes: number
  sha256: string
  created_at: string
  expires_at: string
  capture_status?: 'valid' | 'suspicious' | 'invalid' | 'unavailable' | null
  capture_reason?: string | null
  page_url?: string | null
  captured_at?: string | null
  width?: number | null
  height?: number | null
}

export type ValidationStatus = 'detected' | 'pending_confirmation' | 'confirmed' | 'not_reproducible' | 'false_positive' | 'fixed' | 'retested'

export interface Validation {
  id: string
  finding_id: string
  from_status: ValidationStatus
  to_status: ValidationStatus
  actor: string
  notes: string | null
  validated_at: string
}

export interface RetestComparison {
  previous_run_id: string
  current_run_id: string
  previous_finished_at: string | null
  current_finished_at: string | null
  complete: boolean
  previous_status: ExecutionStatus
  current_status: ExecutionStatus
  findings: Array<{
    fingerprint: string
    previous_finding_id: string | null
    current_finding_id: string | null
    previous_result: string | null
    current_result: string | null
    previous_evidence_count: number
    current_evidence_count: number
    assessment: 'unknown' | 'persisting' | 'not_observed_pending_verification' | 'inconclusive' | 'technical_failure' | 'new'
  }>
}

export interface Step {
  id: string
  run_id: string
  step_number: number
  action: string
  module_name: string | null
  page_name: string | null
  page_url: string | null
  target: string | null
  status: string
  observed_at: string
}
