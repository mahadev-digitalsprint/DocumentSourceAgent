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

export type CompanyIntakeRunInput = {
  company_name: string
  website_url: string
  crawl_depth: number
  reuse_existing?: boolean
}

export type CompanyOverview = {
  documents_total: number
  quarterly_documents: number
  yearly_documents: number
  other_documents: number
  financial_documents: number
  non_financial_documents: number
  download_folders: string[]
}

export type CompanyOverviewResponse = {
  company: Company
  overview: CompanyOverview
}

export type CompanyIntakeRunResponse = {
  company: Company
  run_result: {
    company: string
    pdfs_found?: number
    docs_downloaded?: number
    has_changes?: boolean
    errors?: number
    email_sent?: boolean
  }
  overview: CompanyOverview
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
  source_type?: string | null
  source_domain?: string | null
  discovery_strategy?: string | null
  first_seen_at?: string | null
  last_seen_at?: string | null
  created_at: string
}

export type CompanyDownloadViewRecord = {
  id: number
  document_url: string
  local_path?: string | null
  folder_path?: string | null
  doc_type?: string | null
  status: string
  period_bucket: 'QUARTERLY' | 'YEARLY' | 'OTHER'
  category_bucket: 'FINANCIAL' | 'NON_FINANCIAL'
  file_size_bytes?: number | null
  created_at?: string | null
}

export type CompanyDownloadViewResponse = {
  company_id: number
  company_name: string
  filters: {
    period: string
    category: string
  }
  summary: {
    documents_total: number
    quarterly_documents: number
    yearly_documents: number
    other_documents: number
    download_folders: string[]
  }
  records: CompanyDownloadViewRecord[]
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
  smtp_host?: string
  smtp_port?: number
  smtp_user?: string
  smtp_password?: string
  email_from?: string
  recipients?: string[]
  receiver_email?: string
  send_on_change?: boolean
  daily_digest_hour?: number
}

export type EmailAlertSimpleConfig = {
  configured: boolean
  receiver_email: string
  send_on_change: boolean
  daily_digest_hour: number
  sender_email: string
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

export type SchedulerStatus = {
  enabled: boolean
  poll_seconds: number
  pipeline_interval_minutes: number
  webwatch_interval_minutes: number
  digest_hour_utc: number
  digest_minute_utc: number
  last_tick_at?: string | null
  last_pipeline_run_at?: string | null
  last_webwatch_run_at?: string | null
  last_digest_run_at?: string | null
  last_error?: string | null
}

export type SourceSummaryItem = {
  source_domain: string
  discovery_strategy: string
  source_type: string
  documents_total: number
  companies_count: number
  new_docs_window: number
  needs_review_count: number
  last_seen_at?: string | null
}

export type IngestionRetryItem = {
  id: number
  company_id?: number | null
  document_url: string
  source_domain?: string | null
  reason_code: string
  failure_count: number
  next_retry_at?: string | null
  status: string
  last_error?: string | null
  last_attempt_at?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export type CrawlDiagnosticRecord = {
  id: number
  company_id?: number | null
  company_name?: string | null
  domain?: string | null
  strategy?: string | null
  page_url?: string | null
  status_code?: number | null
  blocked: boolean
  error_message?: string | null
  retry_count?: number | null
  duration_ms?: number | null
  created_at?: string | null
}

export type CrawlDiagnosticsSummary = {
  window_hours: number
  total_requests: number
  blocked_requests: number
  error_requests: number
  avg_duration_ms: number
  p95_duration_ms: number
  unique_domains: number
  unique_companies: number
  active_domain_cooldowns: number
  strategy_breakdown: Array<{
    strategy: string
    count: number
  }>
}
