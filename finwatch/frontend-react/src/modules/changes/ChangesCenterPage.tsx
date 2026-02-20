import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { companyApi, documentsApi, jobsApi, webwatchApi } from '../../shared/api'
import { SectionCard } from '../dashboard/SectionCard'

type CategoryFilter = 'ALL' | 'FINANCIAL' | 'NON_FINANCIAL'
type PageChangeFilter = 'ALL' | 'PAGE_ADDED' | 'PAGE_DELETED' | 'CONTENT_CHANGED' | 'NEW_DOC_LINKED'

function cardTone(kind: string) {
  if (kind.includes('NEW') || kind.includes('ADDED')) return 'text-accent'
  if (kind.includes('DELETED') || kind.includes('REMOVED')) return 'text-danger'
  return 'text-warn'
}

export function ChangesCenterPage() {
  const queryClient = useQueryClient()
  const [hours, setHours] = useState(24)
  const [companyId, setCompanyId] = useState<number | 'ALL'>('ALL')
  const [docCategoryFilter, setDocCategoryFilter] = useState<CategoryFilter>('ALL')
  const [pageChangeFilter, setPageChangeFilter] = useState<PageChangeFilter>('ALL')
  const [errorMessage, setErrorMessage] = useState('')

  const companiesQuery = useQuery({
    queryKey: ['companies'],
    queryFn: companyApi.list,
  })

  const docChangesQuery = useQuery({
    queryKey: ['docChanges', hours, companyId],
    queryFn: () => documentsApi.changes(hours, companyId === 'ALL' ? undefined : companyId),
  })

  const pageChangesQuery = useQuery({
    queryKey: ['pageChanges', hours, companyId, pageChangeFilter],
    queryFn: () =>
      webwatchApi.changes(hours, companyId === 'ALL' ? undefined : companyId, pageChangeFilter === 'ALL' ? undefined : pageChangeFilter),
  })

  const scanMutation = useMutation({
    mutationFn: jobsApi.webwatchDirect,
    onSuccess: () => {
      setErrorMessage('')
      void queryClient.invalidateQueries({ queryKey: ['docChanges'] })
      void queryClient.invalidateQueries({ queryKey: ['pageChanges'] })
      void queryClient.invalidateQueries({ queryKey: ['webwatchChanges'] })
    },
    onError: (error: Error) => {
      setErrorMessage(error.message)
    },
  })

  const companies = companiesQuery.data ?? []
  const docChanges = docChangesQuery.data ?? []
  const pageChanges = pageChangesQuery.data ?? []

  const filteredDocChanges = useMemo(() => {
    return docChanges.filter((change) => {
      if (docCategoryFilter === 'ALL') return true
      return (change.doc_type || '').startsWith(docCategoryFilter)
    })
  }, [docChanges, docCategoryFilter])

  const docMetrics = useMemo(() => {
    const newCount = filteredDocChanges.filter((c) => c.change_type === 'NEW').length
    const updatedCount = filteredDocChanges.filter((c) => c.change_type === 'UPDATED').length
    const removedCount = filteredDocChanges.filter((c) => c.change_type === 'REMOVED').length
    return { newCount, updatedCount, removedCount }
  }, [filteredDocChanges])

  const pageMetrics = useMemo(() => {
    const added = pageChanges.filter((c) => c.change_type === 'PAGE_ADDED').length
    const deleted = pageChanges.filter((c) => c.change_type === 'PAGE_DELETED').length
    const contentChanged = pageChanges.filter((c) => c.change_type === 'CONTENT_CHANGED').length
    const docsLinked = pageChanges.filter((c) => c.change_type === 'NEW_DOC_LINKED').length
    return { added, deleted, contentChanged, docsLinked }
  }, [pageChanges])

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">
      <header className="mb-6 rounded-2xl border border-slate-700/70 bg-panel/80 p-5 shadow-panel">
        <h1 className="text-2xl font-semibold text-slate-50 md:text-3xl">Changes Center</h1>
        <p className="mt-2 text-sm text-slate-300">Unified monitoring for document and page-level changes.</p>
      </header>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Doc Changes ({hours}h)</p>
          <p className="mt-2 text-3xl font-semibold text-warn">{filteredDocChanges.length}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Page Changes ({hours}h)</p>
          <p className="mt-2 text-3xl font-semibold text-cyan-300">{pageChanges.length}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">New Documents</p>
          <p className="mt-2 text-3xl font-semibold text-accent">{docMetrics.newCount}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Content Changed Pages</p>
          <p className="mt-2 text-3xl font-semibold text-warn">{pageMetrics.contentChanged}</p>
        </article>
      </section>

      <section className="mt-6">
        <SectionCard
          title="Filters + Actions"
          subtitle="Scope changes and trigger a WebWatch scan"
          action={
            <button
              onClick={() => scanMutation.mutate()}
              disabled={scanMutation.isPending}
              className="rounded-md bg-accent px-3 py-1 text-xs font-semibold text-slate-950 hover:bg-emerald-300 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
            >
              {scanMutation.isPending ? 'Running Scan...' : 'Run WebWatch Scan'}
            </button>
          }
        >
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <select
              value={hours}
              onChange={(event) => setHours(Number(event.target.value))}
              className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
            >
              <option value={6}>Last 6h</option>
              <option value={12}>Last 12h</option>
              <option value={24}>Last 24h</option>
              <option value={48}>Last 48h</option>
              <option value={72}>Last 72h</option>
              <option value={168}>Last 7d</option>
            </select>

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
              value={docCategoryFilter}
              onChange={(event) => setDocCategoryFilter(event.target.value as CategoryFilter)}
              className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
            >
              <option value="ALL">All Doc Categories</option>
              <option value="FINANCIAL">FINANCIAL</option>
              <option value="NON_FINANCIAL">NON_FINANCIAL</option>
            </select>

            <select
              value={pageChangeFilter}
              onChange={(event) => setPageChangeFilter(event.target.value as PageChangeFilter)}
              className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
            >
              <option value="ALL">All Page Change Types</option>
              <option value="PAGE_ADDED">PAGE_ADDED</option>
              <option value="PAGE_DELETED">PAGE_DELETED</option>
              <option value="CONTENT_CHANGED">CONTENT_CHANGED</option>
              <option value="NEW_DOC_LINKED">NEW_DOC_LINKED</option>
            </select>
          </div>
          {errorMessage ? <p className="mt-3 rounded-md border border-red-500/40 bg-red-950/30 p-2 text-sm text-red-200">{errorMessage}</p> : null}
        </SectionCard>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-2">
        <SectionCard title="Document Change Feed" subtitle="NEW / UPDATED / REMOVED changes">
          <div className="space-y-2">
            {filteredDocChanges.slice(0, 100).map((change) => (
              <div key={change.id} className="rounded-lg border border-slate-700/70 p-3 text-sm">
                <p className={`font-semibold ${cardTone(change.change_type)}`}>{change.change_type}</p>
                <p className="text-slate-200">{change.company_name}</p>
                <p className="text-slate-400">{change.doc_type}</p>
                <a href={change.document_url} target="_blank" rel="noreferrer" className="block truncate text-cyan-300 hover:text-cyan-200">
                  {change.document_url}
                </a>
                <p className="mt-1 text-xs text-slate-500">{change.detected_at.slice(0, 19).replace('T', ' ')}</p>
              </div>
            ))}
            {filteredDocChanges.length === 0 ? <p className="text-sm text-slate-500">No document changes found.</p> : null}
          </div>
        </SectionCard>

        <SectionCard title="Page Change Feed" subtitle="WebWatch detected website changes">
          <div className="space-y-2">
            {pageChanges.slice(0, 100).map((change) => (
              <div key={change.id} className="rounded-lg border border-slate-700/70 p-3 text-sm">
                <p className={`font-semibold ${cardTone(change.change_type)}`}>{change.change_type}</p>
                <p className="truncate text-slate-200">{change.page_url}</p>
                <p className="truncate text-xs text-slate-400">{change.diff_summary ?? 'No summary available'}</p>
                <p className="mt-1 text-xs text-slate-500">{change.detected_at.slice(0, 19).replace('T', ' ')}</p>
              </div>
            ))}
            {pageChanges.length === 0 ? <p className="text-sm text-slate-500">No page changes found.</p> : null}
          </div>
        </SectionCard>
      </section>
    </main>
  )
}
