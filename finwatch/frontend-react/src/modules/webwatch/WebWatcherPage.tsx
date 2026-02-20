import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { companyApi, jobsApi, webwatchApi } from '../../shared/api'
import type { PageChange } from '../../shared/types'
import { SectionCard } from '../dashboard/SectionCard'

type ChangeTypeFilter = 'ALL' | 'PAGE_ADDED' | 'PAGE_DELETED' | 'CONTENT_CHANGED' | 'NEW_DOC_LINKED'
type ViewMode = 'CHANGES' | 'SNAPSHOTS'

function toneForChange(changeType: string) {
  if (changeType.includes('ADDED')) return 'text-accent'
  if (changeType.includes('DELETED')) return 'text-danger'
  if (changeType.includes('CHANGED')) return 'text-warn'
  if (changeType.includes('DOC')) return 'text-cyan-300'
  return 'text-slate-300'
}

export function WebWatcherPage() {
  const queryClient = useQueryClient()
  const [viewMode, setViewMode] = useState<ViewMode>('CHANGES')
  const [hours, setHours] = useState(24)
  const [companyId, setCompanyId] = useState<number | 'ALL'>('ALL')
  const [changeType, setChangeType] = useState<ChangeTypeFilter>('ALL')
  const [selectedChangeId, setSelectedChangeId] = useState<number | null>(null)
  const [actionError, setActionError] = useState('')

  const companiesQuery = useQuery({
    queryKey: ['companies'],
    queryFn: companyApi.list,
  })

  const changesQuery = useQuery({
    queryKey: ['webwatchChanges', hours, companyId, changeType],
    queryFn: () => webwatchApi.changes(hours, companyId === 'ALL' ? undefined : companyId, changeType),
  })

  const snapshotsQuery = useQuery({
    queryKey: ['webwatchSnapshots', companyId],
    queryFn: () => webwatchApi.snapshots(companyId === 'ALL' ? undefined : companyId),
  })

  const selectedChange: PageChange | undefined = useMemo(
    () => (changesQuery.data ?? []).find((change) => change.id === selectedChangeId),
    [changesQuery.data, selectedChangeId],
  )

  const diffQuery = useQuery({
    queryKey: ['webwatchDiff', selectedChangeId],
    queryFn: () => webwatchApi.diff(selectedChangeId as number),
    enabled: selectedChangeId !== null && selectedChange?.change_type === 'CONTENT_CHANGED',
  })

  const queuedScanMutation = useMutation({
    mutationFn: jobsApi.webwatchQueued,
    onSuccess: () => {
      setActionError('')
    },
    onError: (error: Error) => {
      setActionError(error.message)
    },
  })

  const directScanMutation = useMutation({
    mutationFn: jobsApi.webwatchDirect,
    onSuccess: () => {
      setActionError('')
      void queryClient.invalidateQueries({ queryKey: ['webwatchChanges'] })
      void queryClient.invalidateQueries({ queryKey: ['webwatchSnapshots'] })
    },
    onError: (error: Error) => {
      setActionError(error.message)
    },
  })

  const changes = changesQuery.data ?? []
  const snapshots = snapshotsQuery.data ?? []
  const companies = companiesQuery.data ?? []

  const metrics = useMemo(() => {
    const added = changes.filter((c) => c.change_type === 'PAGE_ADDED').length
    const deleted = changes.filter((c) => c.change_type === 'PAGE_DELETED').length
    const contentChanged = changes.filter((c) => c.change_type === 'CONTENT_CHANGED').length
    const newDocs = changes.filter((c) => c.change_type === 'NEW_DOC_LINKED').length
    return { added, deleted, contentChanged, newDocs }
  }, [changes])

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">
      <header className="mb-6 rounded-2xl border border-slate-700/70 bg-panel/80 p-5 shadow-panel">
        <h1 className="text-2xl font-semibold text-slate-50 md:text-3xl">Web Watcher</h1>
        <p className="mt-2 text-sm text-slate-300">Monitor page-level changes, snapshots, and structural diffs across tracked websites.</p>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Page Added</p>
          <p className="mt-2 text-3xl font-semibold text-accent">{metrics.added}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Page Deleted</p>
          <p className="mt-2 text-3xl font-semibold text-danger">{metrics.deleted}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Content Changed</p>
          <p className="mt-2 text-3xl font-semibold text-warn">{metrics.contentChanged}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">New PDFs Linked</p>
          <p className="mt-2 text-3xl font-semibold text-cyan-300">{metrics.newDocs}</p>
        </article>
      </section>

      <section className="mt-6">
        <SectionCard title="Controls" subtitle="Filter by company/type and trigger scans">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
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
              <option value={48}>Last 48h</option>
              <option value={72}>Last 72h</option>
              <option value={168}>Last 7d</option>
            </select>

            <select
              value={changeType}
              onChange={(event) => setChangeType(event.target.value as ChangeTypeFilter)}
              className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
            >
              <option value="ALL">All Changes</option>
              <option value="PAGE_ADDED">PAGE_ADDED</option>
              <option value="PAGE_DELETED">PAGE_DELETED</option>
              <option value="CONTENT_CHANGED">CONTENT_CHANGED</option>
              <option value="NEW_DOC_LINKED">NEW_DOC_LINKED</option>
            </select>

            <button
              onClick={() => setViewMode('CHANGES')}
              className={`rounded-lg px-3 py-2 text-sm font-semibold ${viewMode === 'CHANGES' ? 'bg-accent text-slate-950' : 'bg-slate-800 text-slate-100'}`}
            >
              Changes
            </button>

            <button
              onClick={() => setViewMode('SNAPSHOTS')}
              className={`rounded-lg px-3 py-2 text-sm font-semibold ${viewMode === 'SNAPSHOTS' ? 'bg-accent text-slate-950' : 'bg-slate-800 text-slate-100'}`}
            >
              Snapshots
            </button>

            <div className="flex gap-2">
              <button
                onClick={() => queuedScanMutation.mutate()}
                disabled={queuedScanMutation.isPending || directScanMutation.isPending}
                className="w-full rounded-lg bg-slate-700 px-3 py-2 text-xs font-semibold text-slate-100 hover:bg-slate-600 disabled:cursor-not-allowed"
              >
                Queue Scan
              </button>
              <button
                onClick={() => directScanMutation.mutate()}
                disabled={queuedScanMutation.isPending || directScanMutation.isPending}
                className="w-full rounded-lg bg-accent px-3 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-300 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
              >
                Direct Scan
              </button>
            </div>
          </div>
          {actionError ? <p className="mt-3 rounded-md border border-red-500/40 bg-red-950/30 p-2 text-sm text-red-200">{actionError}</p> : null}
        </SectionCard>
      </section>

      {viewMode === 'CHANGES' ? (
        <section className="mt-6 grid gap-4 xl:grid-cols-3">
          <div className="xl:col-span-2">
            <SectionCard title="Page Changes" subtitle={`Records in last ${hours}h`}>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[820px] border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-slate-700 text-left text-slate-400">
                      <th className="py-2">Change</th>
                      <th className="py-2">Page URL</th>
                      <th className="py-2">Detected</th>
                      <th className="py-2">Summary</th>
                    </tr>
                  </thead>
                  <tbody>
                    {changesQuery.isLoading ? (
                      <tr>
                        <td colSpan={4} className="py-3 text-slate-500">
                          Loading changes...
                        </td>
                      </tr>
                    ) : null}

                    {changes.map((change) => (
                      <tr
                        key={change.id}
                        onClick={() => setSelectedChangeId(change.id)}
                        className={`cursor-pointer border-b border-slate-800/80 text-slate-200 ${
                          selectedChangeId === change.id ? 'bg-slate-800/40' : ''
                        }`}
                      >
                        <td className={`py-2 font-semibold ${toneForChange(change.change_type)}`}>{change.change_type}</td>
                        <td className="max-w-[300px] truncate py-2">{change.page_url}</td>
                        <td className="py-2 text-slate-400">{change.detected_at.slice(0, 19).replace('T', ' ')}</td>
                        <td className="max-w-[320px] truncate py-2 text-slate-300">{change.diff_summary ?? '-'}</td>
                      </tr>
                    ))}

                    {!changesQuery.isLoading && changes.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="py-3 text-slate-500">
                          No page changes for selected filters.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            </SectionCard>
          </div>

          <div>
            <SectionCard title="Diff Viewer" subtitle="Selected change details">
              {!selectedChange ? (
                <p className="text-sm text-slate-500">Select a page change to inspect details.</p>
              ) : (
                <div className="space-y-3 text-sm">
                  <div>
                    <p className="text-xs uppercase tracking-wider text-slate-500">Change Type</p>
                    <p className={`font-semibold ${toneForChange(selectedChange.change_type)}`}>{selectedChange.change_type}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wider text-slate-500">Page URL</p>
                    <a href={selectedChange.page_url} target="_blank" rel="noreferrer" className="break-all text-cyan-300 hover:text-cyan-200">
                      {selectedChange.page_url}
                    </a>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-wider text-slate-500">Summary</p>
                    <p className="text-slate-200">{selectedChange.diff_summary ?? 'No summary available'}</p>
                  </div>
                  {selectedChange.new_pdf_urls && selectedChange.new_pdf_urls.length > 0 ? (
                    <div>
                      <p className="text-xs uppercase tracking-wider text-slate-500">New PDFs</p>
                      <ul className="space-y-1">
                        {selectedChange.new_pdf_urls.map((url) => (
                          <li key={url} className="truncate text-xs text-cyan-300">
                            <a href={url} target="_blank" rel="noreferrer">
                              {url}
                            </a>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {selectedChange.change_type === 'CONTENT_CHANGED' ? (
                    <div>
                      <p className="text-xs uppercase tracking-wider text-slate-500">Text Diff (raw snippets)</p>
                      {diffQuery.isLoading ? (
                        <p className="text-slate-500">Loading diff details...</p>
                      ) : diffQuery.isError ? (
                        <p className="text-slate-500">Diff payload unavailable.</p>
                      ) : (
                        <div className="space-y-2">
                          <div>
                            <p className="mb-1 text-xs text-slate-400">Old Text</p>
                            <pre className="max-h-32 overflow-auto rounded-lg border border-slate-700 bg-slate-900/60 p-2 text-xs text-slate-300">
                              {diffQuery.data?.old_text?.slice(0, 2000) || ''}
                            </pre>
                          </div>
                          <div>
                            <p className="mb-1 text-xs text-slate-400">New Text</p>
                            <pre className="max-h-32 overflow-auto rounded-lg border border-slate-700 bg-slate-900/60 p-2 text-xs text-slate-300">
                              {diffQuery.data?.new_text?.slice(0, 2000) || ''}
                            </pre>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : null}
                </div>
              )}
            </SectionCard>
          </div>
        </section>
      ) : (
        <section className="mt-6">
          <SectionCard title="Snapshots" subtitle="Latest observed pages with hash/status state">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-left text-slate-400">
                    <th className="py-2">Page URL</th>
                    <th className="py-2">PDF Count</th>
                    <th className="py-2">HTTP Status</th>
                    <th className="py-2">Active</th>
                    <th className="py-2">Last Seen</th>
                    <th className="py-2">Hash</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshotsQuery.isLoading ? (
                    <tr>
                      <td colSpan={6} className="py-3 text-slate-500">
                        Loading snapshots...
                      </td>
                    </tr>
                  ) : null}

                  {snapshots.map((snapshot) => (
                    <tr key={snapshot.id} className="border-b border-slate-800/80 text-slate-200">
                      <td className="max-w-[340px] truncate py-2">
                        <a href={snapshot.page_url} target="_blank" rel="noreferrer" className="text-cyan-300 hover:text-cyan-200">
                          {snapshot.page_url}
                        </a>
                      </td>
                      <td className="py-2">{snapshot.pdf_count}</td>
                      <td className="py-2">{snapshot.status_code}</td>
                      <td className={`py-2 font-semibold ${snapshot.is_active ? 'text-accent' : 'text-danger'}`}>
                        {snapshot.is_active ? 'Yes' : 'No'}
                      </td>
                      <td className="py-2 text-slate-400">{snapshot.last_seen.slice(0, 19).replace('T', ' ')}</td>
                      <td className="max-w-[160px] truncate py-2 font-mono text-xs text-slate-400">{snapshot.content_hash}</td>
                    </tr>
                  ))}

                  {!snapshotsQuery.isLoading && snapshots.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-3 text-slate-500">
                        No snapshots available for selected filters.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </section>
      )}
    </main>
  )
}
