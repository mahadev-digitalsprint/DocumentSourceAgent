import type {
  AnalyticsChangeTrend,
  AnalyticsCompanyActivity,
  AnalyticsDocChangeType,
  AnalyticsDocTypeDistribution,
  AnalyticsJobRuns,
  AnalyticsOverview,
  AppSettingMap,
  ChangeLog,
  Company,
  CompanyCreateInput,
  CrawlDiagnosticRecord,
  CrawlDiagnosticsSummary,
  DirectRunResult,
  EmailAlertConfig,
  EmailAlertSimpleConfig,
  EmailAlertSaveInput,
  DocumentRecord,
  DocumentMetadataRecord,
  JobRunHistoryItem,
  JobStatusResponse,
  MetadataListItem,
  PageChangeDiff,
  PageChange,
  PageSnapshot,
  QueuedJobResponse,
  SchedulerStatus,
  SourceSummaryItem,
  IngestionRetryItem,
  WebwatchDirectResult,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers ?? {}),
    },
    ...options,
  })

  if (!response.ok) {
    const body = await response.text()
    throw new Error(`API ${response.status} ${path}: ${body.slice(0, 200)}`)
  }

  if (response.status === 204) {
    return true as T
  }

  return (await response.json()) as T
}

export const dashboardApi = {
  health: () => request<{ status: string; service: string }>('/health'),
  companies: () => request<Company[]>('/companies/'),
  documents: () => request<DocumentRecord[]>('/documents/'),
  documentChanges: (hours = 24) => request<ChangeLog[]>(`/documents/changes/?hours=${hours}`),
  pageChanges: (hours = 24) => request<PageChange[]>(`/webwatch/changes?hours=${hours}`),
  runAll: () => request<DirectRunResult>('/jobs/run-all-direct', { method: 'POST' }),
}

export const companyApi = {
  list: () => request<Company[]>('/companies/'),
  create: (payload: CompanyCreateInput) =>
    request<Company>('/companies/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  toggle: (companyId: number) =>
    request<{ active: boolean }>(`/companies/${companyId}/toggle`, {
      method: 'PATCH',
    }),
  remove: (companyId: number) =>
    request<boolean>(`/companies/${companyId}`, {
      method: 'DELETE',
    }),
}

export const jobsApi = {
  runAllQueued: () => request<QueuedJobResponse>('/jobs/run-all', { method: 'POST' }),
  runAllDirect: () => request<DirectRunResult>('/jobs/run-all-direct', { method: 'POST' }),
  webwatchQueued: () => request<QueuedJobResponse>('/jobs/webwatch-now', { method: 'POST' }),
  webwatchDirect: () => request<WebwatchDirectResult>('/jobs/webwatch-direct', { method: 'POST' }),
  status: (jobId: string) => request<JobStatusResponse>(`/jobs/status/${jobId}`),
  statusByRunId: (runId: string) => request<JobRunHistoryItem>(`/jobs/status/run/${runId}`),
  history: (limit = 100) => request<JobRunHistoryItem[]>(`/jobs/history?limit=${limit}`),
  schedulerStatus: () => request<SchedulerStatus>('/jobs/scheduler/status'),
  schedulerTick: () => request<{ enabled: boolean; triggers: Array<{ trigger_type: string; run_id: string }>; error?: string }>('/jobs/scheduler/tick', { method: 'POST' }),
  schedulerConfig: (payload: Partial<{
    enabled: boolean
    poll_seconds: number
    pipeline_interval_minutes: number
    webwatch_interval_minutes: number
    digest_hour_utc: number
    digest_minute_utc: number
  }>) =>
    request<SchedulerStatus>('/jobs/scheduler/config', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
}

export const documentsApi = {
  list: () => request<DocumentRecord[]>('/documents/?limit=1000'),
  reviewQueue: (companyId?: number, limit = 100) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (companyId) params.set('company_id', String(companyId))
    return request<DocumentRecord[]>(`/documents/review/queue?${params.toString()}`)
  },
  setNeedsReview: (docId: number, needsReview: boolean) =>
    request<{ id: number; needs_review: boolean; classifier_confidence?: number | null }>(`/documents/review/${docId}`, {
      method: 'PATCH',
      body: JSON.stringify({ needs_review: needsReview }),
    }),
  metadataList: (companyId?: number, limit = 1000) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (companyId) params.set('company_id', String(companyId))
    const qs = params.toString()
    return request<MetadataListItem[]>(`/documents/metadata/${qs ? `?${qs}` : ''}`)
  },
  metadataByDocId: (docId: number) => request<DocumentMetadataRecord>(`/documents/${docId}/metadata`),
  changes: (hours: number, companyId?: number, limit = 1000) => {
    const params = new URLSearchParams({ hours: String(hours), limit: String(limit) })
    if (companyId) params.set('company_id', String(companyId))
    return request<ChangeLog[]>(`/documents/changes/?${params.toString()}`)
  },
  sourceSummary: (hours = 168, companyId?: number, limit = 200) => {
    const params = new URLSearchParams({ hours: String(hours), limit: String(limit) })
    if (companyId) params.set('company_id', String(companyId))
    return request<SourceSummaryItem[]>(`/documents/sources/summary?${params.toString()}`)
  },
  retries: (args?: { status?: string; companyId?: number; sourceDomain?: string; limit?: number }) => {
    const params = new URLSearchParams()
    if (args?.status) params.set('status', args.status)
    if (args?.companyId) params.set('company_id', String(args.companyId))
    if (args?.sourceDomain) params.set('source_domain', args.sourceDomain)
    if (args?.limit) params.set('limit', String(args.limit))
    const qs = params.toString()
    return request<IngestionRetryItem[]>(`/documents/retries${qs ? `?${qs}` : ''}`)
  },
  updateRetry: (retryId: number, payload: { status: string; next_retry_in_minutes?: number; reason_code?: string; last_error?: string }) =>
    request<{ id: number; status: string; next_retry_at?: string; failure_count: number; reason_code?: string }>(`/documents/retries/${retryId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
}

export const webwatchApi = {
  changes: (hours: number, companyId?: number, changeType?: string) => {
    const params = new URLSearchParams({ hours: String(hours) })
    if (companyId) params.set('company_id', String(companyId))
    if (changeType && changeType !== 'ALL') params.set('change_type', changeType)
    return request<PageChange[]>(`/webwatch/changes?${params.toString()}`)
  },
  snapshots: (companyId?: number) => {
    const params = new URLSearchParams()
    if (companyId) params.set('company_id', String(companyId))
    const qs = params.toString()
    return request<PageSnapshot[]>(`/webwatch/snapshots${qs ? `?${qs}` : ''}`)
  },
  diff: (changeId: number) => request<PageChangeDiff>(`/webwatch/changes/${changeId}/diff`),
}

export const alertsApi = {
  getConfig: () => request<EmailAlertConfig>('/alerts/'),
  getSimpleConfig: () => request<EmailAlertSimpleConfig>('/alerts/simple'),
  saveConfig: (payload: EmailAlertSaveInput) =>
    request<{ saved: boolean }>('/alerts/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  saveSimpleConfig: (receiverEmail: string) =>
    request<{ saved: boolean; configured: boolean; receiver_email: string }>('/alerts/simple', {
      method: 'POST',
      body: JSON.stringify({ receiver_email: receiverEmail }),
    }),
  testEmail: (receiverEmail?: string) =>
    request<{ sent: boolean; error?: string }>('/alerts/test', {
      method: 'POST',
      body: JSON.stringify(receiverEmail ? { receiver_email: receiverEmail } : {}),
    }),
}

export const settingsApi = {
  list: () => request<AppSettingMap>('/settings/'),
  save: (key: string, value: string) =>
    request<{ key: string; value: string }>('/settings/', {
      method: 'POST',
      body: JSON.stringify({ key, value }),
    }),
}

export const analyticsApi = {
  overview: (hours = 24) => request<AnalyticsOverview>(`/analytics/overview?hours=${hours}`),
  docTypeDistribution: (limit = 25) =>
    request<AnalyticsDocTypeDistribution>(`/analytics/doc-type-distribution?limit=${limit}`),
  companyActivity: (hours = 168, limit = 20) =>
    request<AnalyticsCompanyActivity>(`/analytics/company-activity?hours=${hours}&limit=${limit}`),
  changeTrend: (days = 14, companyId?: number) => {
    const params = new URLSearchParams({ days: String(days) })
    if (companyId) params.set('company_id', String(companyId))
    return request<AnalyticsChangeTrend>(`/analytics/change-trend?${params.toString()}`)
  },
  jobRuns: (hours = 24) => request<AnalyticsJobRuns>(`/analytics/job-runs?hours=${hours}`),
  docChangeTypes: (hours = 168, companyId?: number) => {
    const params = new URLSearchParams({ hours: String(hours) })
    if (companyId) params.set('company_id', String(companyId))
    return request<AnalyticsDocChangeType>(`/analytics/doc-change-types?${params.toString()}`)
  },
}

export const crawlApi = {
  diagnostics: (args?: {
    hours?: number
    companyId?: number
    strategy?: string
    domain?: string
    blocked?: boolean
    limit?: number
  }) => {
    const params = new URLSearchParams()
    if (args?.hours) params.set('hours', String(args.hours))
    if (args?.companyId) params.set('company_id', String(args.companyId))
    if (args?.strategy) params.set('strategy', args.strategy)
    if (args?.domain) params.set('domain', args.domain)
    if (typeof args?.blocked === 'boolean') params.set('blocked', String(args.blocked))
    if (args?.limit) params.set('limit', String(args.limit))
    const qs = params.toString()
    return request<CrawlDiagnosticRecord[]>(`/crawl/diagnostics${qs ? `?${qs}` : ''}`)
  },
  summary: (args?: { hours?: number; companyId?: number; strategy?: string; domain?: string }) => {
    const params = new URLSearchParams()
    if (args?.hours) params.set('hours', String(args.hours))
    if (args?.companyId) params.set('company_id', String(args.companyId))
    if (args?.strategy) params.set('strategy', args.strategy)
    if (args?.domain) params.set('domain', args.domain)
    const qs = params.toString()
    return request<CrawlDiagnosticsSummary>(`/crawl/diagnostics/summary${qs ? `?${qs}` : ''}`)
  },
  cooldowns: () => request<{ blocked_domains: Array<{ domain: string; blocked_until_epoch: number; remaining_seconds: number }> }>('/crawl/cooldowns'),
  clearDomainCooldown: (domain: string) => request<{ cleared: boolean; domain: string }>(`/crawl/cooldowns/${encodeURIComponent(domain)}`, { method: 'DELETE' }),
  clearAllCooldowns: () => request<{ cleared: boolean }>('/crawl/cooldowns', { method: 'DELETE' }),
}
