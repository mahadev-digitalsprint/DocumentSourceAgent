import type {
  AnalyticsChangeTrend,
  AnalyticsCompanyActivity,
  AnalyticsDocTypeDistribution,
  AnalyticsJobRuns,
  AnalyticsOverview,
  AppSettingMap,
  ChangeLog,
  Company,
  CompanyCreateInput,
  DirectRunResult,
  EmailAlertConfig,
  EmailAlertSaveInput,
  DocumentRecord,
  DocumentMetadataRecord,
  JobStatusResponse,
  MetadataListItem,
  PageChangeDiff,
  PageChange,
  PageSnapshot,
  QueuedJobResponse,
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
}

export const documentsApi = {
  list: () => request<DocumentRecord[]>('/documents/'),
  metadataList: (companyId?: number) => {
    const params = new URLSearchParams()
    if (companyId) params.set('company_id', String(companyId))
    const qs = params.toString()
    return request<MetadataListItem[]>(`/documents/metadata/${qs ? `?${qs}` : ''}`)
  },
  metadataByDocId: (docId: number) => request<DocumentMetadataRecord>(`/documents/${docId}/metadata`),
  changes: (hours: number, companyId?: number) => {
    const params = new URLSearchParams({ hours: String(hours) })
    if (companyId) params.set('company_id', String(companyId))
    return request<ChangeLog[]>(`/documents/changes/?${params.toString()}`)
  },
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
  saveConfig: (payload: EmailAlertSaveInput) =>
    request<{ saved: boolean }>('/alerts/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  testEmail: () => request<{ sent: boolean; error?: string }>('/alerts/test', { method: 'POST' }),
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
}
