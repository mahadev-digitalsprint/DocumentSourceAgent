export type Company = {
  id: number
  company_name: string
  company_slug: string
  website_url: string
  crawl_depth: number
  active: boolean
}

export type CompanyCreateInput = {
  company_name: string
  website_url: string
  crawl_depth: number
}

export type DocumentRecord = {
  id: number
  company_id: number
  document_url: string
  doc_type: string
  status: 'NEW' | 'UNCHANGED' | 'UPDATED' | 'FAILED' | string
  metadata_extracted: boolean
  classifier_confidence?: number | null
  classifier_version?: string | null
  needs_review?: boolean
  created_at: string
}

export type DocumentMetadataRecord = {
  id: number
  document_id: number
  headline?: string | null
  filing_date?: string | null
  filing_data_source?: string | null
  language?: string | null
  period_end_date?: string | null
  document_type?: string | null
  income_statement?: boolean | null
  preliminary_document?: boolean | null
  note_flag?: boolean | null
  audit_flag?: boolean | null
  raw_llm_response?: Record<string, unknown>
}

export type MetadataListItem = {
  id: number
  document_id: number
  company_name: string
  company_id: number
  document_url: string
  document_category: string
  document_type: string
  headline?: string | null
  filing_date?: string | null
  period_end_date?: string | null
  language?: string | null
  audit_flag?: boolean | null
  audit_status?: string | null
  preliminary_document?: boolean | null
  income_statement?: boolean | null
  note_flag?: boolean | null
  filing_data_source?: string | null
  raw_llm_response?: Record<string, unknown>
  created_at?: string
}

export type ChangeLog = {
  id: number
  company_id: number
  company_name: string
  doc_type: string
  change_type: string
  document_url: string
  detected_at: string
}

export type PageChange = {
  id: number
  company_id: number
  page_url: string
  change_type: string
  diff_summary?: string
  new_pdf_urls?: string[]
  detected_at: string
}

export type PageSnapshot = {
  id: number
  company_id: number
  page_url: string
  content_hash: string
  pdf_count: number
  status_code: number
  is_active: boolean
  last_seen: string
}

export type PageChangeDiff = {
  change_type: string
  page_url: string
  old_text: string
  new_text: string
  diff_summary?: string
  detected_at: string
}

export type DirectRunResult = {
  job_id: string
  status: string
  run_id?: string
  result?: {
    total_companies: number
    succeeded: number
    failed: number
    companies?: Array<{
      company: string
      pdfs_found: number
      docs_downloaded: number
      has_changes: boolean
      errors: number
      email_sent: boolean
    }>
  }
}

export type QueuedJobResponse = {
  job_id: string
  status: string
  run_id?: string
  result?: Record<string, unknown> | null
}

export type JobStatusResponse = {
  job_id: string
  status: string
  run_id?: string
  result?: Record<string, unknown> | null
}

export type JobRunHistoryItem = {
  run_id: string
  trigger_type: string
  mode: string
  status: string
  celery_job_id?: string | null
  company_id?: number | null
  company_name?: string | null
  result_payload?: Record<string, unknown> | null
  error_message?: string | null
  duration_ms?: number | null
  items_processed?: number | null
  error_count?: number | null
  created_at?: string | null
  started_at?: string | null
  finished_at?: string | null
  updated_at?: string | null
}

export type WebwatchDirectResult = {
  job_id?: string
  status: string
  run_id?: string
  result?: {
    companies?: Array<{ company: string; page_changes?: number; error?: string }>
  }
}

export type EmailAlertConfig = {
  configured: boolean
  smtp_host?: string
  smtp_port?: number
  smtp_user?: string
  email_from?: string
  recipients?: string[]
  send_on_change?: boolean
  daily_digest_hour?: number
}

export type EmailAlertSaveInput = {
  smtp_host: string
  smtp_port: number
  smtp_user: string
  smtp_password: string
  email_from: string
  recipients: string[]
  send_on_change: boolean
  daily_digest_hour: number
}

export type AppSettingMap = Record<string, string>

export type AnalyticsOverview = {
  window_hours: number
  companies_total: number
  companies_active: number
  documents_total: number
  documents_metadata_extracted: number
  document_changes: number
  page_changes: number
  errors: number
  job_runs: number
}

export type AnalyticsDocTypeDistribution = Array<{
  doc_type: string
  count: number
}>

export type AnalyticsCompanyActivity = Array<{
  company_id: number
  company_name: string
  active: boolean
  documents_total: number
  document_changes_window: number
  page_changes_window: number
}>

export type AnalyticsChangeTrend = Array<{
  date: string
  document_changes: number
  page_changes: number
}>

export type AnalyticsJobRuns = {
  window_hours: number
  status_breakdown: Array<{ status: string; count: number }>
}

export type AnalyticsDocChangeType = Array<{
  change_type: string
  count: number
}>
