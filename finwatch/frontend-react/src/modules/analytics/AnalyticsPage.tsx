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
import { dashboardApi } from '../../shared/api'
import { SectionCard } from '../dashboard/SectionCard'

function toDateBucket(input: string) {
  const parsed = new Date(input)
  if (Number.isNaN(parsed.getTime())) return 'unknown'
  return parsed.toISOString().slice(0, 10)
}

export function AnalyticsPage() {
  const [hours, setHours] = useState(168)

  const companiesQuery = useQuery({
    queryKey: ['companies'],
    queryFn: dashboardApi.companies,
  })
  const documentsQuery = useQuery({
    queryKey: ['documents'],
    queryFn: dashboardApi.documents,
  })
  const docChangesQuery = useQuery({
    queryKey: ['docChanges', hours],
    queryFn: () => dashboardApi.documentChanges(hours),
  })
  const pageChangesQuery = useQuery({
    queryKey: ['pageChanges', hours],
    queryFn: () => dashboardApi.pageChanges(hours),
  })

  const companies = companiesQuery.data ?? []
  const documents = documentsQuery.data ?? []
  const docChanges = docChangesQuery.data ?? []
  const pageChanges = pageChangesQuery.data ?? []

  const companyNameById = useMemo(() => new Map(companies.map((c) => [c.id, c.company_name])), [companies])

  const categoryDistribution = useMemo(() => {
    const financial = documents.filter((d) => (d.doc_type || '').startsWith('FINANCIAL')).length
    const nonFinancial = documents.filter((d) => (d.doc_type || '').startsWith('NON_FINANCIAL')).length
    const unknown = Math.max(0, documents.length - financial - nonFinancial)
    return [
      { name: 'Financial', value: financial },
      { name: 'Non-Financial', value: nonFinancial },
      { name: 'Unknown', value: unknown },
    ]
  }, [documents])

  const topSubtypeData = useMemo(() => {
    const counts = new Map<string, number>()
    for (const doc of documents) {
      const parts = (doc.doc_type || 'UNKNOWN').split('|')
      const subtype = parts.length > 1 ? parts[1] : parts[0]
      counts.set(subtype, (counts.get(subtype) ?? 0) + 1)
    }
    return Array.from(counts.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10)
  }, [documents])

  const companyDocData = useMemo(() => {
    const counts = new Map<string, number>()
    for (const doc of documents) {
      const company = companyNameById.get(doc.company_id) ?? `#${doc.company_id}`
      counts.set(company, (counts.get(company) ?? 0) + 1)
    }
    return Array.from(counts.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10)
  }, [documents, companyNameById])

  const trendData = useMemo(() => {
    const map = new Map<string, { date: string; docChanges: number; pageChanges: number }>()
    for (const change of docChanges) {
      const day = toDateBucket(change.detected_at)
      const row = map.get(day) ?? { date: day, docChanges: 0, pageChanges: 0 }
      row.docChanges += 1
      map.set(day, row)
    }
    for (const change of pageChanges) {
      const day = toDateBucket(change.detected_at)
      const row = map.get(day) ?? { date: day, docChanges: 0, pageChanges: 0 }
      row.pageChanges += 1
      map.set(day, row)
    }
    return Array.from(map.values()).sort((a, b) => a.date.localeCompare(b.date))
  }, [docChanges, pageChanges])

  const changeTypeMix = useMemo(() => {
    const counts = new Map<string, number>()
    for (const ch of docChanges) {
      counts.set(ch.change_type, (counts.get(ch.change_type) ?? 0) + 1)
    }
    return Array.from(counts.entries()).map(([name, count]) => ({ name, count }))
  }, [docChanges])

  const extractedCount = documents.filter((d) => d.metadata_extracted).length
  const pendingCount = Math.max(0, documents.length - extractedCount)

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
          <p className="mt-2 text-3xl font-semibold text-slate-100">{companies.length}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Documents</p>
          <p className="mt-2 text-3xl font-semibold text-accent">{documents.length}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Doc Changes ({hours}h)</p>
          <p className="mt-2 text-3xl font-semibold text-warn">{docChanges.length}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Page Changes ({hours}h)</p>
          <p className="mt-2 text-3xl font-semibold text-cyan-300">{pageChanges.length}</p>
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
