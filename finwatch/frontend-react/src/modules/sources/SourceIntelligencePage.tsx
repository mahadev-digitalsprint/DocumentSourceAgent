import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { companyApi, documentsApi } from '../../shared/api'
import { SectionCard } from '../dashboard/SectionCard'

type RetryStatusFilter = 'ALL' | 'PENDING' | 'DEAD' | 'RESOLVED'

export function SourceIntelligencePage() {
  const queryClient = useQueryClient()
  const [hours, setHours] = useState(168)
  const [companyId, setCompanyId] = useState<number | 'ALL'>('ALL')
  const [retryStatus, setRetryStatus] = useState<RetryStatusFilter>('ALL')

  const companiesQuery = useQuery({
    queryKey: ['companies'],
    queryFn: companyApi.list,
  })

  const sourceSummaryQuery = useQuery({
    queryKey: ['sourceSummary', hours, companyId],
    queryFn: () => documentsApi.sourceSummary(hours, companyId === 'ALL' ? undefined : companyId, 300),
    refetchInterval: 20_000,
  })

  const retriesQuery = useQuery({
    queryKey: ['ingestionRetries', retryStatus, companyId],
    queryFn: () =>
      documentsApi.retries({
        status: retryStatus === 'ALL' ? undefined : retryStatus,
        companyId: companyId === 'ALL' ? undefined : companyId,
        limit: 300,
      }),
    refetchInterval: 20_000,
  })

  const updateRetryMutation = useMutation({
    mutationFn: (args: { retryId: number; status: 'PENDING' | 'RESOLVED' | 'DEAD' }) =>
      documentsApi.updateRetry(args.retryId, {
        status: args.status,
        next_retry_in_minutes: args.status === 'PENDING' ? 0 : undefined,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['ingestionRetries'] })
    },
  })

  const companies = companiesQuery.data ?? []
  const summaryRows = sourceSummaryQuery.data ?? []
  const retryRows = retriesQuery.data ?? []

  const metrics = useMemo(() => {
    const totalDocs = summaryRows.reduce((acc, item) => acc + item.documents_total, 0)
    const newDocs = summaryRows.reduce((acc, item) => acc + item.new_docs_window, 0)
    const needsReview = summaryRows.reduce((acc, item) => acc + item.needs_review_count, 0)
    const pendingRetries = retryRows.filter((item) => item.status === 'PENDING').length
    const deadLetters = retryRows.filter((item) => item.status === 'DEAD').length
    return { totalDocs, newDocs, needsReview, pendingRetries, deadLetters }
  }, [summaryRows, retryRows])

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">
      <header className="mb-6 rounded-2xl border border-slate-700/70 bg-panel/80 p-5 shadow-panel">
        <h1 className="text-2xl font-semibold text-slate-50 md:text-3xl">Source Intelligence</h1>
        <p className="mt-2 text-sm text-slate-300">Domain/source yield analytics with retry and dead-letter queue controls.</p>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Documents</p>
          <p className="mt-2 text-3xl font-semibold text-slate-100">{metrics.totalDocs}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">New in Window</p>
          <p className="mt-2 text-3xl font-semibold text-accent">{metrics.newDocs}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Needs Review</p>
          <p className="mt-2 text-3xl font-semibold text-warn">{metrics.needsReview}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Pending Retries</p>
          <p className="mt-2 text-3xl font-semibold text-cyan-300">{metrics.pendingRetries}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Dead Letters</p>
          <p className="mt-2 text-3xl font-semibold text-danger">{metrics.deadLetters}</p>
        </article>
      </section>

      <section className="mt-6">
        <SectionCard title="Filters" subtitle="Control source summary window and retry queue slice">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
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
              value={hours}
              onChange={(event) => setHours(Number(event.target.value))}
              className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
            >
              <option value={24}>Last 24h</option>
              <option value={72}>Last 72h</option>
              <option value={168}>Last 7d</option>
              <option value={720}>Last 30d</option>
            </select>
            <select
              value={retryStatus}
              onChange={(event) => setRetryStatus(event.target.value as RetryStatusFilter)}
              className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
            >
              <option value="ALL">All Retry Statuses</option>
              <option value="PENDING">PENDING</option>
              <option value="DEAD">DEAD</option>
              <option value="RESOLVED">RESOLVED</option>
            </select>
          </div>
        </SectionCard>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <SectionCard title="Source Domains" subtitle="Document yield by domain, strategy, and source type">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[920px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-left text-slate-400">
                    <th className="py-2">Domain</th>
                    <th className="py-2">Strategy</th>
                    <th className="py-2">Type</th>
                    <th className="py-2">Documents</th>
                    <th className="py-2">New</th>
                    <th className="py-2">Needs Review</th>
                    <th className="py-2">Last Seen</th>
                  </tr>
                </thead>
                <tbody>
                  {sourceSummaryQuery.isLoading ? (
                    <tr>
                      <td colSpan={7} className="py-3 text-slate-500">
                        Loading source summary...
                      </td>
                    </tr>
                  ) : null}
                  {summaryRows.map((row, idx) => (
                    <tr key={`${row.source_domain}-${row.discovery_strategy}-${idx}`} className="border-b border-slate-800/80 text-slate-200">
                      <td className="py-2">{row.source_domain}</td>
                      <td className="py-2 text-cyan-300">{row.discovery_strategy}</td>
                      <td className="py-2">{row.source_type}</td>
                      <td className="py-2">{row.documents_total}</td>
                      <td className="py-2 text-accent">{row.new_docs_window}</td>
                      <td className="py-2 text-warn">{row.needs_review_count}</td>
                      <td className="py-2 text-slate-400">{(row.last_seen_at ?? '').slice(0, 19).replace('T', ' ') || '-'}</td>
                    </tr>
                  ))}
                  {!sourceSummaryQuery.isLoading && summaryRows.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-3 text-slate-500">
                        No source summary rows for selected filters.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>
        <div>
          <SectionCard title="Dead-Letter Queue" subtitle="Retry failed URLs or resolve them manually">
            <div className="max-h-[620px] space-y-2 overflow-auto pr-1 text-sm">
              {retriesQuery.isLoading ? <p className="text-slate-500">Loading retries...</p> : null}
              {retryRows.map((row) => (
                <div key={row.id} className="rounded-lg border border-slate-700 bg-slate-900/60 p-3">
                  <p className="truncate font-semibold text-slate-100">{row.reason_code}</p>
                  <p className="truncate text-xs text-cyan-300">{row.document_url}</p>
                  <p className="text-xs text-slate-400">
                    Status: <span className={row.status === 'DEAD' ? 'text-danger' : row.status === 'PENDING' ? 'text-warn' : 'text-accent'}>{row.status}</span> | Failures: {row.failure_count}
                  </p>
                  <p className="truncate text-xs text-slate-500">{row.last_error || '-'}</p>
                  <div className="mt-2 flex gap-2">
                    <button
                      onClick={() => updateRetryMutation.mutate({ retryId: row.id, status: 'PENDING' })}
                      disabled={updateRetryMutation.isPending}
                      className="rounded-md bg-accent px-2 py-1 text-xs font-semibold text-slate-950 hover:bg-emerald-300 disabled:cursor-not-allowed"
                    >
                      Retry Now
                    </button>
                    <button
                      onClick={() => updateRetryMutation.mutate({ retryId: row.id, status: 'RESOLVED' })}
                      disabled={updateRetryMutation.isPending}
                      className="rounded-md bg-slate-700 px-2 py-1 text-xs font-semibold text-slate-100 hover:bg-slate-600 disabled:cursor-not-allowed"
                    >
                      Resolve
                    </button>
                  </div>
                </div>
              ))}
              {!retriesQuery.isLoading && retryRows.length === 0 ? <p className="text-slate-500">No retry/dead-letter entries.</p> : null}
            </div>
          </SectionCard>
        </div>
      </section>
    </main>
  )
}
