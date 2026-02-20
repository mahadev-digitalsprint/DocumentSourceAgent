import { useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { companyApi, jobsApi } from '../../shared/api'

export function CompanyRunsPage() {
  const queryClient = useQueryClient()
  const companiesQuery = useQuery({
    queryKey: ['companies'],
    queryFn: companyApi.list,
  })

  const runAllMutation = useMutation({
    mutationFn: jobsApi.runAllDirect,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      void queryClient.invalidateQueries({ queryKey: ['jobHistory'] })
    },
  })

  const runCompanyMutation = useMutation({
    mutationFn: (companyId: number) => jobsApi.runCompanyDirect(companyId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      void queryClient.invalidateQueries({ queryKey: ['jobHistory'] })
    },
  })

  const jobsQuery = useQuery({
    queryKey: ['jobHistory', 100],
    queryFn: () => jobsApi.history(100),
    refetchInterval: 15000,
  })

  const lastByCompany = useMemo(() => {
    const map = new Map<number, { status: string; updated: string }>()
    for (const row of jobsQuery.data ?? []) {
      if (!row.company_id) continue
      if (map.has(row.company_id)) continue
      map.set(row.company_id, {
        status: row.status,
        updated: (row.updated_at || row.created_at || '').replace('T', ' ').slice(0, 19),
      })
    }
    return map
  }, [jobsQuery.data])

  const runAllSummary = runAllMutation.data?.result

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-slate-50">Run Control</h2>
            <p className="mt-1 text-sm text-slate-300">
              Trigger all companies at once or run one company directly from the table below.
            </p>
          </div>
          <button
            onClick={() => runAllMutation.mutate()}
            disabled={runAllMutation.isPending}
            className="rounded-md bg-accent px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-300 disabled:cursor-not-allowed disabled:bg-slate-600"
          >
            {runAllMutation.isPending ? 'Running...' : 'Run All Now'}
          </button>
        </div>
        {runAllSummary ? (
          <p className="mt-3 rounded-md border border-emerald-500/40 bg-emerald-950/30 p-2 text-sm text-emerald-200">
            Companies={runAllSummary.total_companies}, Success={runAllSummary.succeeded}, Failed={runAllSummary.failed}
          </p>
        ) : null}
      </section>

      <section className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
        <h2 className="text-lg font-semibold text-slate-50">Company Runs</h2>
        <p className="mt-1 text-sm text-slate-300">Every row includes a run button and latest run status.</p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-left text-slate-400">
                <th className="py-2">Company</th>
                <th className="py-2">Website</th>
                <th className="py-2">Last Status</th>
                <th className="py-2">Updated</th>
                <th className="py-2">Action</th>
              </tr>
            </thead>
            <tbody>
              {(companiesQuery.data ?? []).map((company) => {
                const latest = lastByCompany.get(company.id)
                return (
                  <tr key={company.id} className="border-b border-slate-800/80 text-slate-200">
                    <td className="py-2">{company.company_name}</td>
                    <td className="max-w-[340px] truncate py-2 text-cyan-300">{company.website_url}</td>
                    <td className="py-2">{latest?.status ?? '-'}</td>
                    <td className="py-2 text-slate-400">{latest?.updated ?? '-'}</td>
                    <td className="py-2">
                      <button
                        onClick={() => runCompanyMutation.mutate(company.id)}
                        disabled={runCompanyMutation.isPending}
                        className="rounded-md bg-cyan-400 px-2 py-1 text-xs font-semibold text-slate-950 hover:bg-cyan-300 disabled:cursor-not-allowed disabled:bg-slate-600"
                      >
                        {runCompanyMutation.isPending ? 'Running...' : 'Run'}
                      </button>
                    </td>
                  </tr>
                )
              })}
              {companiesQuery.data?.length ? null : (
                <tr>
                  <td colSpan={5} className="py-3 text-slate-500">
                    No companies available.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
