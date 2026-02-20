import { useMemo } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { dashboardApi } from '../../shared/api'
import { KpiCard } from './KpiCard'
import { DocCategoryChart } from './DocCategoryChart'
import { RecentChangesPanel } from './RecentChangesPanel'
import { CrawlStatusPanel } from './CrawlStatusPanel'
import { SectionCard } from './SectionCard'
import { useDashboardStore } from './dashboardStore'
import { useLiveJobEvents } from './useLiveJobEvents'

export function DashboardPage() {
  const timeWindowHours = useDashboardStore((s) => s.timeWindowHours)
  const setTimeWindowHours = useDashboardStore((s) => s.setTimeWindowHours)
  const setIsRunningPipeline = useDashboardStore((s) => s.setIsRunningPipeline)
  const isRunningPipeline = useDashboardStore((s) => s.isRunningPipeline)
  const liveEvents = useLiveJobEvents()

  const companiesQuery = useQuery({ queryKey: ['companies'], queryFn: dashboardApi.companies })
  const documentsQuery = useQuery({ queryKey: ['documents'], queryFn: dashboardApi.documents })
  const docChangesQuery = useQuery({
    queryKey: ['docChanges', timeWindowHours],
    queryFn: () => dashboardApi.documentChanges(timeWindowHours),
  })
  const pageChangesQuery = useQuery({
    queryKey: ['pageChanges', timeWindowHours],
    queryFn: () => dashboardApi.pageChanges(timeWindowHours),
  })
  const healthQuery = useQuery({ queryKey: ['health'], queryFn: dashboardApi.health, refetchInterval: 20_000 })

  const runAllMutation = useMutation({
    mutationFn: dashboardApi.runAll,
    onMutate: () => setIsRunningPipeline(true),
    onSettled: () => setIsRunningPipeline(false),
  })

  const companies = companiesQuery.data ?? []
  const documents = documentsQuery.data ?? []
  const docChanges = docChangesQuery.data ?? []
  const pageChanges = pageChangesQuery.data ?? []

  const metrics = useMemo(() => {
    const activeCompanies = companies.filter((c) => c.active).length
    const financialDocs = documents.filter((d) => d.doc_type.startsWith('FINANCIAL')).length
    const nonFinancialDocs = documents.filter((d) => d.doc_type.startsWith('NON_FINANCIAL')).length
    const unknownDocs = Math.max(0, documents.length - financialDocs - nonFinancialDocs)
    return { activeCompanies, financialDocs, nonFinancialDocs, unknownDocs }
  }, [companies, documents])

  const isLoading = companiesQuery.isLoading || documentsQuery.isLoading || docChangesQuery.isLoading || pageChangesQuery.isLoading
  const hasError = companiesQuery.error || documentsQuery.error || docChangesQuery.error || pageChangesQuery.error

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">
      <header className="mb-6 rounded-2xl border border-slate-700/70 bg-panel/80 p-5 shadow-panel">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">FinWatch Enterprise</p>
            <h1 className="text-2xl font-semibold text-slate-50 md:text-3xl">Financial Document Intelligence Dashboard</h1>
            <p className="mt-2 text-sm text-slate-300">
              API status: <span className={healthQuery.isError ? 'text-danger' : 'text-accent'}>{healthQuery.data?.status ?? 'unknown'}</span>
            </p>
          </div>
          <div className="flex items-center gap-2">
            {[6, 12, 24, 48, 72].map((hours) => (
              <button
                key={hours}
                onClick={() => setTimeWindowHours(hours)}
                className={`rounded-md px-3 py-1 text-sm ${
                  timeWindowHours === hours ? 'bg-accent font-semibold text-slate-950' : 'bg-slate-800 text-slate-200'
                }`}
              >
                {hours}h
              </button>
            ))}
          </div>
        </div>
      </header>

      {isLoading ? <p className="mb-4 text-sm text-slate-400">Loading dashboard data...</p> : null}
      {hasError ? (
        <p className="mb-4 rounded-lg border border-red-500/40 bg-red-950/30 p-3 text-sm text-red-200">
          Failed to load one or more dashboard data sources. Check backend service and API routes.
        </p>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <KpiCard label="Active Companies" value={metrics.activeCompanies} />
        <KpiCard label="Financial Docs" value={metrics.financialDocs} tone="good" />
        <KpiCard label="Non-Financial Docs" value={metrics.nonFinancialDocs} />
        <KpiCard label={`Doc Changes (${timeWindowHours}h)`} value={docChanges.length} tone="warn" />
        <KpiCard label={`Page Changes (${timeWindowHours}h)`} value={pageChanges.length} tone="warn" />
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-2">
        <SectionCard title="Document Distribution" subtitle="Financial vs non-financial split">
          <DocCategoryChart
            financial={metrics.financialDocs}
            nonFinancial={metrics.nonFinancialDocs}
            unknown={metrics.unknownDocs}
          />
        </SectionCard>
        <CrawlStatusPanel
          isRunning={isRunningPipeline || runAllMutation.isPending}
          onRunAll={() => runAllMutation.mutate()}
          liveEvents={liveEvents}
        />
      </section>

      <section className="mt-6">
        <RecentChangesPanel docChanges={docChanges} pageChanges={pageChanges} />
      </section>
    </main>
  )
}
