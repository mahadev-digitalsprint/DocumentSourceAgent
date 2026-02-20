import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { analyticsApi } from '../../shared/api'
import { SectionCard } from '../dashboard/SectionCard'

export function AnalyticsPage() {
  const [hours, setHours] = useState(168)
  const trendDays = Math.max(1, Math.ceil(hours / 24))

  const overviewQuery = useQuery({
    queryKey: ['analyticsOverview', hours],
    queryFn: () => analyticsApi.overview(hours),
  })
  const docTypeQuery = useQuery({
    queryKey: ['analyticsDocTypeDistribution'],
    queryFn: () => analyticsApi.docTypeDistribution(100),
  })
  const companyActivityQuery = useQuery({
    queryKey: ['analyticsCompanyActivity', hours],
    queryFn: () => analyticsApi.companyActivity(hours, 10),
  })
  const trendQuery = useQuery({
    queryKey: ['analyticsChangeTrend', trendDays],
    queryFn: () => analyticsApi.changeTrend(trendDays),
  })
  const docChangeTypeQuery = useQuery({
    queryKey: ['analyticsDocChangeTypes', hours],
    queryFn: () => analyticsApi.docChangeTypes(hours),
  })

  const overview = overviewQuery.data
  const docTypeDistribution = docTypeQuery.data ?? []
  const companyActivity = companyActivityQuery.data ?? []
  const trend = trendQuery.data ?? []
  const docChangeTypes = docChangeTypeQuery.data ?? []

  const categoryDistribution = useMemo(() => {
    const financial = docTypeDistribution
      .filter((item) => (item.doc_type || '').startsWith('FINANCIAL'))
      .reduce((acc, item) => acc + item.count, 0)
    const nonFinancial = docTypeDistribution
      .filter((item) => (item.doc_type || '').startsWith('NON_FINANCIAL'))
      .reduce((acc, item) => acc + item.count, 0)
    const total = overview?.documents_total ?? financial + nonFinancial
    const unknown = Math.max(0, total - financial - nonFinancial)
    return [
      { name: 'Financial', value: financial },
      { name: 'Non-Financial', value: nonFinancial },
      { name: 'Unknown', value: unknown },
    ]
  }, [docTypeDistribution, overview?.documents_total])

  const topSubtypeData = useMemo(
    () =>
      docTypeDistribution
        .map((item) => {
          const parts = (item.doc_type || 'UNKNOWN').split('|')
          return { name: parts.length > 1 ? parts[1] : parts[0], count: item.count }
        })
        .sort((a, b) => b.count - a.count)
        .slice(0, 10),
    [docTypeDistribution],
  )

  const companyDocData = useMemo(
    () =>
      companyActivity
        .map((item) => ({ name: item.company_name, count: item.documents_total }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 10),
    [companyActivity],
  )

  const trendData = useMemo(
    () =>
      trend.map((item) => ({
        date: item.date,
        docChanges: item.document_changes,
        pageChanges: item.page_changes,
      })),
    [trend],
  )

  const changeTypeMix = useMemo(
    () => docChangeTypes.map((item) => ({ name: item.change_type, count: item.count })),
    [docChangeTypes],
  )

  const totalDocuments = overview?.documents_total ?? 0
  const extractedCount = overview?.documents_metadata_extracted ?? 0
  const pendingCount = Math.max(0, totalDocuments - extractedCount)
  const totalCompanies = overview?.companies_total ?? 0
  const docChanges = overview?.document_changes ?? 0
  const pageChanges = overview?.page_changes ?? 0

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">
      <header className="mb-6 rounded-2xl border border-slate-700/70 bg-panel/80 p-5 shadow-panel">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-50 md:text-3xl">Analytics</h1>
            <p className="mt-2 text-sm text-slate-300">Document intelligence, company activity, and change trends.</p>
          </div>
          <select
            value={hours}
            onChange={(event) => setHours(Number(event.target.value))}
            className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
          >
            <option value={24}>Last 24h</option>
            <option value={72}>Last 72h</option>
            <option value={168}>Last 7d</option>
            <option value={336}>Last 14d</option>
          </select>
        </div>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Companies</p>
          <p className="mt-2 text-3xl font-semibold text-slate-100">{totalCompanies}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Documents</p>
          <p className="mt-2 text-3xl font-semibold text-accent">{totalDocuments}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Doc Changes ({hours}h)</p>
          <p className="mt-2 text-3xl font-semibold text-warn">{docChanges}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Page Changes ({hours}h)</p>
          <p className="mt-2 text-3xl font-semibold text-cyan-300">{pageChanges}</p>
        </article>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-2">
        <SectionCard title="Document Category Split" subtitle="Financial vs non-financial distribution">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Tooltip />
                <Legend />
                <Pie data={categoryDistribution} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={105} fill="#00b894" />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>

        <SectionCard title="Metadata Coverage" subtitle="Extracted vs pending documents">
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={[{ name: 'Metadata', extracted: extractedCount, pending: pendingCount }]}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f3344" />
                <XAxis dataKey="name" stroke="#8ca2b7" />
                <YAxis stroke="#8ca2b7" allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Bar dataKey="extracted" fill="#00b894" />
                <Bar dataKey="pending" fill="#ffb347" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-2">
        <SectionCard title="Top Document Subtypes" subtitle="Top 10 by volume">
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topSubtypeData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f3344" />
                <XAxis dataKey="name" stroke="#8ca2b7" interval={0} angle={-20} textAnchor="end" height={90} />
                <YAxis stroke="#8ca2b7" allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#59a0ff" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>

        <SectionCard title="Top Company Activity" subtitle="Companies with most documents">
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={companyDocData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f3344" />
                <XAxis dataKey="name" stroke="#8ca2b7" interval={0} angle={-20} textAnchor="end" height={90} />
                <YAxis stroke="#8ca2b7" allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#00b894" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-2">
        <SectionCard title="Change Trend Over Time" subtitle={`Daily trend for last ${hours}h`}>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f3344" />
                <XAxis dataKey="date" stroke="#8ca2b7" />
                <YAxis stroke="#8ca2b7" allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="docChanges" stroke="#ffb347" strokeWidth={2} />
                <Line type="monotone" dataKey="pageChanges" stroke="#00b894" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>

        <SectionCard title="Document Change Type Mix" subtitle="NEW/UPDATED/REMOVED distribution">
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={changeTypeMix}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f3344" />
                <XAxis dataKey="name" stroke="#8ca2b7" />
                <YAxis stroke="#8ca2b7" allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#ffb347" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
      </section>
    </main>
  )
}
