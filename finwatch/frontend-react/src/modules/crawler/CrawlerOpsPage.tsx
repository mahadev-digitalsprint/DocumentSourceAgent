import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { companyApi, crawlApi } from '../../shared/api'
import { SectionCard } from '../dashboard/SectionCard'

type BlockedFilter = 'ALL' | 'BLOCKED' | 'NOT_BLOCKED'

export function CrawlerOpsPage() {
  const queryClient = useQueryClient()
  const [hours, setHours] = useState(24)
  const [companyId, setCompanyId] = useState<number | 'ALL'>('ALL')
  const [strategy, setStrategy] = useState<string>('ALL')
  const [blockedFilter, setBlockedFilter] = useState<BlockedFilter>('ALL')

  const companiesQuery = useQuery({
    queryKey: ['companies'],
    queryFn: companyApi.list,
  })

  const diagnosticsQuery = useQuery({
    queryKey: ['crawlDiagnostics', hours, companyId, strategy, blockedFilter],
    queryFn: () =>
      crawlApi.diagnostics({
        hours,
        companyId: companyId === 'ALL' ? undefined : companyId,
        strategy: strategy === 'ALL' ? undefined : strategy,
        blocked: blockedFilter === 'ALL' ? undefined : blockedFilter === 'BLOCKED',
        limit: 500,
      }),
    refetchInterval: 20_000,
  })

  const summaryQuery = useQuery({
    queryKey: ['crawlDiagnosticsSummary', hours, companyId, strategy],
    queryFn: () =>
      crawlApi.summary({
        hours,
        companyId: companyId === 'ALL' ? undefined : companyId,
        strategy: strategy === 'ALL' ? undefined : strategy,
      }),
    refetchInterval: 20_000,
  })

  const cooldownsQuery = useQuery({
    queryKey: ['crawlCooldowns'],
    queryFn: crawlApi.cooldowns,
    refetchInterval: 20_000,
  })

  const clearAllMutation = useMutation({
    mutationFn: crawlApi.clearAllCooldowns,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['crawlCooldowns'] })
      void queryClient.invalidateQueries({ queryKey: ['crawlDiagnosticsSummary'] })
    },
  })

  const clearDomainMutation = useMutation({
    mutationFn: (domain: string) => crawlApi.clearDomainCooldown(domain),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['crawlCooldowns'] })
      void queryClient.invalidateQueries({ queryKey: ['crawlDiagnosticsSummary'] })
    },
  })

  const diagnostics = diagnosticsQuery.data ?? []
  const summary = summaryQuery.data
  const cooldowns = cooldownsQuery.data?.blocked_domains ?? []
  const companies = companiesQuery.data ?? []

  const strategies = useMemo(() => {
    const all = new Set<string>()
    for (const row of diagnostics) {
      if (row.strategy) all.add(row.strategy)
    }
    for (const row of summary?.strategy_breakdown ?? []) {
      if (row.strategy) all.add(row.strategy)
    }
    return ['ALL', ...Array.from(all).sort()]
  }, [diagnostics, summary])

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">
      <header className="mb-6 rounded-2xl border border-slate-700/70 bg-panel/80 p-5 shadow-panel">
        <h1 className="text-2xl font-semibold text-slate-50 md:text-3xl">Crawler Operations</h1>
        <p className="mt-2 text-sm text-slate-300">Domain cooldowns, blocked detection, and request-level crawl diagnostics.</p>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Requests</p>
          <p className="mt-2 text-3xl font-semibold text-accent">{summary?.total_requests ?? 0}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Blocked</p>
          <p className="mt-2 text-3xl font-semibold text-danger">{summary?.blocked_requests ?? 0}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Errors</p>
          <p className="mt-2 text-3xl font-semibold text-warn">{summary?.error_requests ?? 0}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">P95 Latency</p>
          <p className="mt-2 text-3xl font-semibold text-cyan-300">{summary?.p95_duration_ms ?? 0}ms</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Active Cooldowns</p>
          <p className="mt-2 text-3xl font-semibold text-slate-100">{summary?.active_domain_cooldowns ?? 0}</p>
        </article>
      </section>

      <section className="mt-6">
        <SectionCard title="Filters" subtitle="Slice diagnostics by time, company, strategy, and blocked state">
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
              <option value={6}>Last 6h</option>
              <option value={12}>Last 12h</option>
              <option value={24}>Last 24h</option>
              <option value={72}>Last 72h</option>
              <option value={168}>Last 7d</option>
            </select>
            <select
              value={strategy}
              onChange={(event) => setStrategy(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
            >
              {strategies.map((strategyOption) => (
                <option key={strategyOption} value={strategyOption}>
                  {strategyOption}
                </option>
              ))}
            </select>
            <select
              value={blockedFilter}
              onChange={(event) => setBlockedFilter(event.target.value as BlockedFilter)}
              className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
            >
              <option value="ALL">All Responses</option>
              <option value="BLOCKED">Blocked Only</option>
              <option value="NOT_BLOCKED">Not Blocked</option>
            </select>
          </div>
        </SectionCard>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <SectionCard title="Diagnostic Stream" subtitle="Latest crawl requests across all strategies">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[920px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-left text-slate-400">
                    <th className="py-2">Time</th>
                    <th className="py-2">Company</th>
                    <th className="py-2">Strategy</th>
                    <th className="py-2">Domain</th>
                    <th className="py-2">HTTP</th>
                    <th className="py-2">Blocked</th>
                    <th className="py-2">Duration</th>
                    <th className="py-2">URL / Error</th>
                  </tr>
                </thead>
                <tbody>
                  {diagnosticsQuery.isLoading ? (
                    <tr>
                      <td colSpan={8} className="py-3 text-slate-500">
                        Loading diagnostics...
                      </td>
                    </tr>
                  ) : null}
                  {diagnostics.map((row) => (
                    <tr key={row.id} className="border-b border-slate-800/80 text-slate-200">
                      <td className="py-2 text-slate-400">{(row.created_at ?? '').slice(0, 19).replace('T', ' ')}</td>
                      <td className="py-2">{row.company_name ?? '-'}</td>
                      <td className="py-2 font-semibold text-cyan-300">{row.strategy ?? '-'}</td>
                      <td className="py-2">{row.domain ?? '-'}</td>
                      <td className="py-2">{row.status_code ?? '-'}</td>
                      <td className={`py-2 font-semibold ${row.blocked ? 'text-danger' : 'text-accent'}`}>{row.blocked ? 'Yes' : 'No'}</td>
                      <td className="py-2">{row.duration_ms ?? 0}ms</td>
                      <td className="max-w-[320px] py-2">
                        {row.error_message ? (
                          <span className="block truncate text-xs text-danger">{row.error_message}</span>
                        ) : (
                          <a href={row.page_url ?? ''} target="_blank" rel="noreferrer" className="block truncate text-xs text-cyan-300 hover:text-cyan-200">
                            {row.page_url ?? '-'}
                          </a>
                        )}
                      </td>
                    </tr>
                  ))}
                  {!diagnosticsQuery.isLoading && diagnostics.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-3 text-slate-500">
                        No diagnostics for selected filters.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>

        <div>
          <SectionCard
            title="Domain Cooldowns"
            subtitle="Domains currently skipped after bot-block detection"
            action={
              <button
                onClick={() => clearAllMutation.mutate()}
                disabled={clearAllMutation.isPending}
                className="rounded-lg bg-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-100 hover:bg-slate-600 disabled:cursor-not-allowed"
              >
                Clear All
              </button>
            }
          >
            <div className="space-y-2 text-sm">
              {cooldownsQuery.isLoading ? <p className="text-slate-500">Loading cooldowns...</p> : null}
              {cooldowns.map((item) => (
                <div key={item.domain} className="rounded-lg border border-slate-700 bg-slate-900/60 p-3">
                  <p className="truncate font-semibold text-slate-100">{item.domain}</p>
                  <p className="text-xs text-slate-400">Remaining: {Math.round(item.remaining_seconds)}s</p>
                  <button
                    onClick={() => clearDomainMutation.mutate(item.domain)}
                    disabled={clearDomainMutation.isPending}
                    className="mt-2 rounded-md bg-accent px-2 py-1 text-xs font-semibold text-slate-950 hover:bg-emerald-300 disabled:cursor-not-allowed"
                  >
                    Unblock
                  </button>
                </div>
              ))}
              {!cooldownsQuery.isLoading && cooldowns.length === 0 ? <p className="text-slate-500">No active cooldowns.</p> : null}
            </div>
          </SectionCard>
        </div>
      </section>
    </main>
  )
}
