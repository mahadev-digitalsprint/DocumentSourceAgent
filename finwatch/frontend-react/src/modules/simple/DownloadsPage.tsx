import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { companyApi, documentsApi, jobsApi } from '../../shared/api'

type PeriodFilter = 'ALL' | 'QUARTERLY' | 'YEARLY'
type CategoryFilter = 'ALL' | 'FINANCIAL' | 'NON_FINANCIAL'

function prettySize(size?: number | null) {
  if (!size || size <= 0) return '-'
  return `${(size / 1024 / 1024).toFixed(2)} MB`
}

export function DownloadsPage() {
  const [companyId, setCompanyId] = useState<number | 'ALL'>('ALL')
  const [period, setPeriod] = useState<PeriodFilter>('ALL')
  const [category, setCategory] = useState<CategoryFilter>('ALL')
  const [refreshTick, setRefreshTick] = useState(0)

  const companiesQuery = useQuery({
    queryKey: ['companies'],
    queryFn: companyApi.list,
  })

  const selectedCompanyId = companyId === 'ALL' ? undefined : companyId

  const downloadsQuery = useQuery({
    queryKey: ['companyDownloads', selectedCompanyId, period, category, refreshTick],
    queryFn: () =>
      documentsApi.companyDownloadView(selectedCompanyId as number, {
        period,
        category,
        limit: 3000,
      }),
    enabled: selectedCompanyId !== undefined,
    refetchInterval: 15000,
  })

  const runCompanyMutation = useMutation({
    mutationFn: (id: number) => jobsApi.runCompanyDirect(id),
    onSuccess: () => setRefreshTick((v) => v + 1),
  })

  const folders = downloadsQuery.data?.summary.download_folders ?? []
  const records = downloadsQuery.data?.records ?? []
  const latestRows = useMemo(() => records.slice(0, 300), [records])

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
        <h2 className="text-xl font-semibold text-slate-50">Downloads Explorer (Quarterly / Yearly)</h2>
        <p className="mt-1 text-sm text-slate-300">
          Select a company to view downloaded files. Use run button to fetch latest docs.
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <select
            value={companyId}
            onChange={(e) => setCompanyId(e.target.value === 'ALL' ? 'ALL' : Number(e.target.value))}
            className="rounded-md border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
          >
            <option value="ALL">Select Company</option>
            {(companiesQuery.data ?? []).map((company) => (
              <option key={company.id} value={company.id}>
                {company.company_name}
              </option>
            ))}
          </select>

          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value as PeriodFilter)}
            className="rounded-md border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
          >
            <option value="ALL">All Periods</option>
            <option value="QUARTERLY">Quarterly</option>
            <option value="YEARLY">Yearly</option>
          </select>

          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as CategoryFilter)}
            className="rounded-md border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
          >
            <option value="ALL">All Categories</option>
            <option value="FINANCIAL">Financial</option>
            <option value="NON_FINANCIAL">Non-Financial</option>
          </select>

          <div className="flex gap-2">
            <button
              onClick={() => setRefreshTick((v) => v + 1)}
              className="flex-1 rounded-md bg-slate-700 px-3 py-2 text-sm font-semibold text-slate-100 hover:bg-slate-600"
            >
              Refresh
            </button>
            <button
              onClick={() => selectedCompanyId && runCompanyMutation.mutate(selectedCompanyId)}
              disabled={!selectedCompanyId || runCompanyMutation.isPending}
              className="flex-1 rounded-md bg-accent px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-300 disabled:cursor-not-allowed disabled:bg-slate-600"
            >
              {runCompanyMutation.isPending ? 'Running...' : 'Run Company'}
            </button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Total</p>
          <p className="mt-2 text-2xl font-semibold text-slate-100">{downloadsQuery.data?.summary.documents_total ?? 0}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Quarterly</p>
          <p className="mt-2 text-2xl font-semibold text-cyan-300">{downloadsQuery.data?.summary.quarterly_documents ?? 0}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Yearly</p>
          <p className="mt-2 text-2xl font-semibold text-accent">{downloadsQuery.data?.summary.yearly_documents ?? 0}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Folders</p>
          <p className="mt-2 text-2xl font-semibold text-slate-100">{folders.length}</p>
        </article>
      </section>

      <section className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
        <h3 className="text-lg font-semibold text-slate-50">Download Folders</h3>
        <div className="mt-2 space-y-1 text-xs text-slate-300">
          {folders.map((folder) => (
            <p key={folder} className="rounded-md border border-slate-800 bg-slate-950/60 px-2 py-1 font-mono">
              {folder}
            </p>
          ))}
          {folders.length === 0 ? <p className="text-slate-500">No folders available yet.</p> : null}
        </div>
      </section>

      <section className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
        <h3 className="text-lg font-semibold text-slate-50">Downloaded Documents</h3>
        <p className="mt-1 text-sm text-slate-300">Showing up to 300 recent records for performance.</p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[900px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-left text-slate-400">
                <th className="py-2">Period</th>
                <th className="py-2">Category</th>
                <th className="py-2">Status</th>
                <th className="py-2">Size</th>
                <th className="py-2">URL</th>
                <th className="py-2">Local Path</th>
              </tr>
            </thead>
            <tbody>
              {latestRows.map((row) => (
                <tr key={row.id} className="border-b border-slate-800/80 text-slate-200">
                  <td className="py-2">{row.period_bucket}</td>
                  <td className="py-2">{row.category_bucket}</td>
                  <td className="py-2">{row.status}</td>
                  <td className="py-2">{prettySize(row.file_size_bytes)}</td>
                  <td className="max-w-[300px] truncate py-2 text-cyan-300">
                    <a href={row.document_url} target="_blank" rel="noreferrer" className="hover:text-cyan-200">
                      {row.document_url}
                    </a>
                  </td>
                  <td className="max-w-[360px] truncate py-2 font-mono text-xs text-slate-300">{row.local_path || '-'}</td>
                </tr>
              ))}
              {latestRows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-3 text-slate-500">
                    {selectedCompanyId ? 'No documents for selected filters yet.' : 'Select a company to view downloads.'}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
