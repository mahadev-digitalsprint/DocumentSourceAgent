import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { companyApi, jobsApi } from '../../shared/api'

function fmtBoolean(value?: boolean) {
  return value ? 'Yes' : 'No'
}

export function QuickIntakePage() {
  const queryClient = useQueryClient()
  const [companyName, setCompanyName] = useState('')
  const [websiteUrl, setWebsiteUrl] = useState('')
  const [crawlDepth, setCrawlDepth] = useState(3)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const companiesQuery = useQuery({
    queryKey: ['companies'],
    queryFn: companyApi.list,
  })

  const intakeMutation = useMutation({
    mutationFn: () =>
      companyApi.intakeRun({
        company_name: companyName.trim(),
        website_url: websiteUrl.trim(),
        crawl_depth: crawlDepth,
        reuse_existing: true,
      }),
    onSuccess: (data) => {
      setError('')
      setMessage(
        `Run complete for ${data.company.company_name}. Downloaded=${data.run_result.docs_downloaded ?? 0}, Quarterly=${data.overview.quarterly_documents}, Yearly=${data.overview.yearly_documents}`,
      )
      void queryClient.invalidateQueries({ queryKey: ['companies'] })
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: (err: Error) => {
      setMessage('')
      setError(err.message)
    },
  })

  const runAllMutation = useMutation({
    mutationFn: jobsApi.runAllDirect,
    onSuccess: (result) => {
      setError('')
      const info = result.result
      setMessage(
        info
          ? `Run all finished. Companies=${info.total_companies}, Success=${info.succeeded}, Failed=${info.failed}`
          : 'Run all completed.',
      )
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: (err: Error) => {
      setMessage('')
      setError(err.message)
    },
  })

  const runCompanyMutation = useMutation({
    mutationFn: (companyId: number) => jobsApi.runCompanyDirect(companyId),
    onSuccess: (result) => {
      setError('')
      setMessage(`Company run completed. Status=${result.status} RunId=${result.run_id ?? '-'}`)
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: (err: Error) => {
      setMessage('')
      setError(err.message)
    },
  })

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    intakeMutation.mutate()
  }

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-slate-50">1. Add Company + Run Pipeline</h2>
            <p className="mt-1 text-sm text-slate-300">
              Enter company name and investor/website URL. It immediately fetches docs and stores them in local download folders.
            </p>
          </div>
          <button
            type="button"
            onClick={() => runAllMutation.mutate()}
            disabled={runAllMutation.isPending}
            className="rounded-md bg-accent px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-300 disabled:cursor-not-allowed disabled:bg-slate-600"
          >
            {runAllMutation.isPending ? 'Running...' : 'Run All Companies'}
          </button>
        </div>

        <form className="mt-4 grid gap-3 md:grid-cols-4" onSubmit={onSubmit}>
          <input
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            placeholder="Company Name"
            className="rounded-md border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
            required
          />
          <input
            value={websiteUrl}
            onChange={(e) => setWebsiteUrl(e.target.value)}
            placeholder="https://company.com/investors"
            className="rounded-md border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2 md:col-span-2"
            required
            type="url"
          />
          <div className="flex gap-2">
            <input
              value={crawlDepth}
              onChange={(e) => setCrawlDepth(Number(e.target.value))}
              className="w-20 rounded-md border border-slate-700 bg-slate-950/60 px-2 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
              type="number"
              min={1}
              max={8}
            />
            <button
              type="submit"
              disabled={intakeMutation.isPending}
              className="flex-1 rounded-md bg-cyan-400 px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-300 disabled:cursor-not-allowed disabled:bg-slate-600"
            >
              {intakeMutation.isPending ? 'Running...' : 'Create + Run'}
            </button>
          </div>
        </form>

        {message ? <p className="mt-3 rounded-md border border-emerald-500/40 bg-emerald-950/30 p-2 text-sm text-emerald-200">{message}</p> : null}
        {error ? <p className="mt-3 rounded-md border border-red-500/40 bg-red-950/30 p-2 text-sm text-red-200">{error}</p> : null}
      </section>

      <section className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
        <h2 className="text-lg font-semibold text-slate-50">2. Quick Company Actions</h2>
        <p className="mt-1 text-sm text-slate-300">Each company has a run button for immediate refresh.</p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-left text-slate-400">
                <th className="py-2">Company</th>
                <th className="py-2">Website</th>
                <th className="py-2">Depth</th>
                <th className="py-2">Active</th>
                <th className="py-2">Action</th>
              </tr>
            </thead>
            <tbody>
              {(companiesQuery.data ?? []).map((company) => (
                <tr key={company.id} className="border-b border-slate-800/80 text-slate-200">
                  <td className="py-2">{company.company_name}</td>
                  <td className="max-w-[360px] truncate py-2 text-cyan-300">
                    <a href={company.website_url} target="_blank" rel="noreferrer" className="hover:text-cyan-200">
                      {company.website_url}
                    </a>
                  </td>
                  <td className="py-2">{company.crawl_depth}</td>
                  <td className="py-2">{fmtBoolean(company.active)}</td>
                  <td className="py-2">
                    <button
                      type="button"
                      onClick={() => runCompanyMutation.mutate(company.id)}
                      disabled={runCompanyMutation.isPending}
                      className="rounded-md bg-accent px-2 py-1 text-xs font-semibold text-slate-950 hover:bg-emerald-300 disabled:cursor-not-allowed disabled:bg-slate-600"
                    >
                      {runCompanyMutation.isPending ? 'Running...' : 'Run Company'}
                    </button>
                  </td>
                </tr>
              ))}
              {companiesQuery.data?.length ? null : (
                <tr>
                  <td colSpan={5} className="py-3 text-slate-500">
                    No companies yet.
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
