import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { companyApi, documentsApi } from '../../shared/api'
import type { MetadataListItem } from '../../shared/types'
import { SectionCard } from '../dashboard/SectionCard'

type CategoryFilter = 'ALL' | 'FINANCIAL' | 'NON_FINANCIAL'
type AuditFilter = 'ALL' | 'AUDITED' | 'UNAUDITED'
type ViewMode = 'FINANCIAL' | 'NON_FINANCIAL'

function toCsv(items: MetadataListItem[]) {
  const headers = [
    'company_name',
    'document_category',
    'document_type',
    'headline',
    'filing_date',
    'period_end_date',
    'language',
    'audit_status',
    'preliminary_document',
    'income_statement',
    'filing_data_source',
    'document_url',
  ]

  const rows = items.map((item) => [
    item.company_name,
    item.document_category,
    item.document_type,
    item.headline ?? '',
    item.filing_date ?? '',
    item.period_end_date ?? '',
    item.language ?? '',
    item.audit_status ?? '',
    String(Boolean(item.preliminary_document)),
    String(Boolean(item.income_statement)),
    item.filing_data_source ?? '',
    item.document_url,
  ])

  const escaped = (value: string) => `"${value.replaceAll('"', '""')}"`
  return [headers.join(','), ...rows.map((row) => row.map((v) => escaped(String(v))).join(','))].join('\n')
}

function triggerCsvDownload(filename: string, csvData: string) {
  const blob = new Blob([csvData], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

export function MetadataIntelligencePage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [companyId, setCompanyId] = useState<number | 'ALL'>('ALL')
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('ALL')
  const [auditFilter, setAuditFilter] = useState<AuditFilter>('ALL')
  const [viewMode, setViewMode] = useState<ViewMode>('FINANCIAL')
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const companiesQuery = useQuery({
    queryKey: ['companies'],
    queryFn: companyApi.list,
  })

  const metadataQuery = useQuery({
    queryKey: ['metadataList'],
    queryFn: () => documentsApi.metadataList(),
  })
  const reviewQueueQuery = useQuery({
    queryKey: ['reviewQueue', companyId],
    queryFn: () => documentsApi.reviewQueue(companyId === 'ALL' ? undefined : companyId, 100),
    refetchInterval: 20_000,
  })
  const reviewMutation = useMutation({
    mutationFn: ({ docId, needsReview }: { docId: number; needsReview: boolean }) => documentsApi.setNeedsReview(docId, needsReview),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['reviewQueue'] })
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })

  const companies = companiesQuery.data ?? []
  const metadata = metadataQuery.data ?? []
  const reviewQueue = reviewQueueQuery.data ?? []

  const metrics = useMemo(() => {
    const total = metadata.length
    const financial = metadata.filter((m) => m.document_category === 'FINANCIAL').length
    const nonFinancial = metadata.filter((m) => m.document_category === 'NON_FINANCIAL').length
    const audited = metadata.filter((m) => (m.audit_status || '').toUpperCase() === 'AUDITED').length
    return { total, financial, nonFinancial, audited }
  }, [metadata])

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase()
    return metadata.filter((item) => {
      if (companyId !== 'ALL' && item.company_id !== companyId) return false
      if (categoryFilter !== 'ALL' && item.document_category !== categoryFilter) return false
      if (auditFilter === 'AUDITED' && (item.audit_status || '').toUpperCase() !== 'AUDITED') return false
      if (auditFilter === 'UNAUDITED' && (item.audit_status || '').toUpperCase() === 'AUDITED') return false
      if (item.document_category !== viewMode) return false
      if (!term) return true

      return (
        (item.company_name || '').toLowerCase().includes(term) ||
        (item.headline || '').toLowerCase().includes(term) ||
        (item.document_type || '').toLowerCase().includes(term) ||
        (item.document_url || '').toLowerCase().includes(term)
      )
    })
  }, [metadata, companyId, categoryFilter, auditFilter, viewMode, search])

  const selectedItem = selectedId !== null ? filtered.find((item) => item.id === selectedId) : undefined

  const exportCurrentView = () => {
    const csv = toCsv(filtered)
    const ts = new Date().toISOString().slice(0, 19).replaceAll(':', '-')
    triggerCsvDownload(`metadata_${viewMode.toLowerCase()}_${ts}.csv`, csv)
  }

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">
      <header className="mb-6 rounded-2xl border border-slate-700/70 bg-panel/80 p-5 shadow-panel">
        <h1 className="text-2xl font-semibold text-slate-50 md:text-3xl">Metadata Intelligence</h1>
        <p className="mt-2 text-sm text-slate-300">Inspect extracted filing metadata across financial and non-financial documents.</p>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Total Metadata Records</p>
          <p className="mt-2 text-3xl font-semibold text-slate-100">{metrics.total}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Financial</p>
          <p className="mt-2 text-3xl font-semibold text-accent">{metrics.financial}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Non-Financial</p>
          <p className="mt-2 text-3xl font-semibold text-slate-100">{metrics.nonFinancial}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Audited</p>
          <p className="mt-2 text-3xl font-semibold text-cyan-300">{metrics.audited}</p>
        </article>
      </section>

      <section className="mt-6">
        <SectionCard
          title="Filters"
          subtitle="Search and refine metadata records"
          action={
            <button onClick={exportCurrentView} className="rounded-md bg-accent px-3 py-1 text-xs font-semibold text-slate-950 hover:bg-emerald-300">
              Export CSV
            </button>
          }
        >
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
            <button
              onClick={() => setViewMode('FINANCIAL')}
              className={`rounded-lg px-3 py-2 text-sm font-semibold ${viewMode === 'FINANCIAL' ? 'bg-accent text-slate-950' : 'bg-slate-800 text-slate-100'}`}
            >
              Financial View
            </button>
            <button
              onClick={() => setViewMode('NON_FINANCIAL')}
              className={`rounded-lg px-3 py-2 text-sm font-semibold ${viewMode === 'NON_FINANCIAL' ? 'bg-accent text-slate-950' : 'bg-slate-800 text-slate-100'}`}
            >
              Non-Financial View
            </button>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2 xl:col-span-2"
              placeholder="Search company/headline/type/url"
            />
            <select
              value={companyId}
              onChange={(event) => setCompanyId(event.target.value === 'ALL' ? 'ALL' : Number(event.target.value))}
              className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
            >
              <option value="ALL">All Companies</option>
              {companies.map((company) => (
                <option key={company.id} value={company.id}>
                  {company.company_name}
                </option>
              ))}
            </select>
            <select
              value={categoryFilter}
              onChange={(event) => setCategoryFilter(event.target.value as CategoryFilter)}
              className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
            >
              <option value="ALL">All Categories</option>
              <option value="FINANCIAL">FINANCIAL</option>
              <option value="NON_FINANCIAL">NON_FINANCIAL</option>
            </select>
            <select
              value={auditFilter}
              onChange={(event) => setAuditFilter(event.target.value as AuditFilter)}
              className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
            >
              <option value="ALL">All Audit Status</option>
              <option value="AUDITED">Audited</option>
              <option value="UNAUDITED">Unaudited/Unknown</option>
            </select>
          </div>
        </SectionCard>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <SectionCard title="Metadata Records" subtitle={`Showing ${filtered.length} records for ${viewMode}`}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-left text-slate-400">
                    <th className="py-2">Company</th>
                    <th className="py-2">Type</th>
                    <th className="py-2">Headline</th>
                    <th className="py-2">Filing Date</th>
                    <th className="py-2">Audit</th>
                    <th className="py-2">Language</th>
                  </tr>
                </thead>
                <tbody>
                  {metadataQuery.isLoading ? (
                    <tr>
                      <td colSpan={6} className="py-3 text-slate-500">
                        Loading metadata...
                      </td>
                    </tr>
                  ) : null}

                  {filtered.slice(0, 300).map((item) => (
                    <tr
                      key={item.id}
                      onClick={() => setSelectedId(item.id)}
                      className={`cursor-pointer border-b border-slate-800/80 text-slate-200 ${
                        selectedId === item.id ? 'bg-slate-800/40' : ''
                      }`}
                    >
                      <td className="py-2">{item.company_name}</td>
                      <td className="py-2">{item.document_type}</td>
                      <td className="max-w-[320px] truncate py-2">{item.headline || '-'}</td>
                      <td className="py-2">{item.filing_date || '-'}</td>
                      <td className="py-2">{item.audit_status || '-'}</td>
                      <td className="py-2">{item.language || '-'}</td>
                    </tr>
                  ))}

                  {!metadataQuery.isLoading && filtered.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-3 text-slate-500">
                        No metadata records match current filters.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            {filtered.length > 300 ? (
              <p className="mt-3 text-xs text-slate-500">Showing first 300 rows for UI performance. Refine filters for deeper analysis.</p>
            ) : null}
          </SectionCard>
        </div>

        <div className="space-y-4">
          <SectionCard title="Record Detail" subtitle="Selected metadata payload">
            {!selectedItem ? (
              <p className="text-sm text-slate-500">Select a metadata row to inspect details.</p>
            ) : (
              <div className="space-y-3 text-sm">
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">Company</p>
                  <p className="text-slate-100">{selectedItem.company_name}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">Category / Type</p>
                  <p className="text-slate-100">
                    {selectedItem.document_category} / {selectedItem.document_type}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">Headline</p>
                  <p className="text-slate-100">{selectedItem.headline || '-'}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">Dates</p>
                  <p className="text-slate-100">
                    Filing: {selectedItem.filing_date || '-'} | Period End: {selectedItem.period_end_date || '-'}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">Source URL</p>
                  <a href={selectedItem.document_url} target="_blank" rel="noreferrer" className="break-all text-cyan-300 hover:text-cyan-200">
                    {selectedItem.document_url}
                  </a>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">Raw Payload</p>
                  <pre className="max-h-72 overflow-auto rounded-lg border border-slate-700 bg-slate-900/60 p-3 text-xs text-slate-200">
                    {JSON.stringify(selectedItem.raw_llm_response || {}, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </SectionCard>
          <SectionCard title="Classifier Review Queue" subtitle="Low-confidence documents awaiting analyst decision">
            <div className="space-y-2 text-sm">
              {reviewQueueQuery.isLoading ? <p className="text-slate-500">Loading review queue...</p> : null}
              {reviewQueue.slice(0, 25).map((doc) => (
                <div key={doc.id} className="rounded-lg border border-slate-700 bg-slate-900/60 p-3">
                  <p className="truncate font-semibold text-slate-100">{doc.doc_type || 'UNKNOWN'}</p>
                  <p className="truncate text-xs text-cyan-300">{doc.document_url}</p>
                  <p className="text-xs text-slate-400">Confidence: {((doc.classifier_confidence ?? 0) * 100).toFixed(1)}%</p>
                  <div className="mt-2 flex gap-2">
                    <button
                      onClick={() => reviewMutation.mutate({ docId: doc.id, needsReview: false })}
                      disabled={reviewMutation.isPending}
                      className="rounded-md bg-accent px-2 py-1 text-xs font-semibold text-slate-950 hover:bg-emerald-300 disabled:cursor-not-allowed"
                    >
                      Mark Reviewed
                    </button>
                    <a href={doc.document_url} target="_blank" rel="noreferrer" className="rounded-md bg-slate-700 px-2 py-1 text-xs font-semibold text-slate-100 hover:bg-slate-600">
                      Open
                    </a>
                  </div>
                </div>
              ))}
              {!reviewQueueQuery.isLoading && reviewQueue.length === 0 ? <p className="text-slate-500">No documents currently need review.</p> : null}
            </div>
          </SectionCard>
        </div>
      </section>
    </main>
  )
}
