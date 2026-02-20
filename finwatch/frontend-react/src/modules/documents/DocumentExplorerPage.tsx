import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { companyApi, documentsApi } from '../../shared/api'
import type { DocumentRecord } from '../../shared/types'
import { SectionCard } from '../dashboard/SectionCard'

type CategoryFilter = 'ALL' | 'FINANCIAL' | 'NON_FINANCIAL' | 'UNKNOWN'
type MetadataFilter = 'ALL' | 'EXTRACTED' | 'PENDING'

function categoryOf(docType: string): CategoryFilter {
  if (docType.startsWith('FINANCIAL')) return 'FINANCIAL'
  if (docType.startsWith('NON_FINANCIAL')) return 'NON_FINANCIAL'
  return 'UNKNOWN'
}

function subtypeOf(docType: string) {
  const parts = docType.split('|')
  return parts.length > 1 ? parts[1] : parts[0] || 'UNKNOWN'
}

export function DocumentExplorerPage() {
  const [search, setSearch] = useState('')
  const [companyId, setCompanyId] = useState<number | 'ALL'>('ALL')
  const [statusFilter, setStatusFilter] = useState<string>('ALL')
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('ALL')
  const [metadataFilter, setMetadataFilter] = useState<MetadataFilter>('ALL')
  const [subtypeFilter, setSubtypeFilter] = useState<string>('ALL')
  const [selectedDocId, setSelectedDocId] = useState<number | null>(null)

  const companiesQuery = useQuery({
    queryKey: ['companies'],
    queryFn: companyApi.list,
  })

  const documentsQuery = useQuery({
    queryKey: ['documents'],
    queryFn: documentsApi.list,
  })

  const selectedMetadataQuery = useQuery({
    queryKey: ['docMetadata', selectedDocId],
    queryFn: () => documentsApi.metadataByDocId(selectedDocId as number),
    enabled: selectedDocId !== null,
  })

  const companies = companiesQuery.data ?? []
  const documents = documentsQuery.data ?? []

  const companyNameById = useMemo(() => new Map(companies.map((c) => [c.id, c.company_name])), [companies])

  const subtypes = useMemo(() => {
    const set = new Set(documents.map((d) => subtypeOf(d.doc_type || 'UNKNOWN')))
    return ['ALL', ...Array.from(set).sort()]
  }, [documents])

  const filteredDocs = useMemo(() => {
    const term = search.trim().toLowerCase()
    return documents.filter((doc) => {
      if (companyId !== 'ALL' && doc.company_id !== companyId) return false
      if (statusFilter !== 'ALL' && doc.status !== statusFilter) return false
      if (categoryFilter !== 'ALL' && categoryOf(doc.doc_type || '') !== categoryFilter) return false
      if (metadataFilter === 'EXTRACTED' && !doc.metadata_extracted) return false
      if (metadataFilter === 'PENDING' && doc.metadata_extracted) return false
      if (subtypeFilter !== 'ALL' && subtypeOf(doc.doc_type || '') !== subtypeFilter) return false
      if (!term) return true

      const companyName = (companyNameById.get(doc.company_id) || '').toLowerCase()
      return (
        (doc.document_url || '').toLowerCase().includes(term) ||
        (doc.doc_type || '').toLowerCase().includes(term) ||
        companyName.includes(term)
      )
    })
  }, [documents, search, companyId, statusFilter, categoryFilter, metadataFilter, subtypeFilter, companyNameById])

  const metrics = useMemo(() => {
    const financial = documents.filter((d) => categoryOf(d.doc_type || '') === 'FINANCIAL').length
    const nonFinancial = documents.filter((d) => categoryOf(d.doc_type || '') === 'NON_FINANCIAL').length
    const unknown = Math.max(0, documents.length - financial - nonFinancial)
    const extracted = documents.filter((d) => d.metadata_extracted).length
    return { financial, nonFinancial, unknown, extracted }
  }, [documents])

  const selectedDoc: DocumentRecord | undefined = selectedDocId !== null ? documents.find((d) => d.id === selectedDocId) : undefined

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">
      <header className="mb-6 rounded-2xl border border-slate-700/70 bg-panel/80 p-5 shadow-panel">
        <h1 className="text-2xl font-semibold text-slate-50 md:text-3xl">Document Explorer</h1>
        <p className="mt-2 text-sm text-slate-300">Filter and inspect financial/non-financial document inventory.</p>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Total Documents</p>
          <p className="mt-2 text-3xl font-semibold text-slate-100">{documents.length}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Financial</p>
          <p className="mt-2 text-3xl font-semibold text-accent">{metrics.financial}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Non-Financial</p>
          <p className="mt-2 text-3xl font-semibold text-slate-100">{metrics.nonFinancial}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Unknown</p>
          <p className="mt-2 text-3xl font-semibold text-warn">{metrics.unknown}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Metadata Extracted</p>
          <p className="mt-2 text-3xl font-semibold text-accent">{metrics.extracted}</p>
        </article>
      </section>

      <section className="mt-6">
        <SectionCard title="Filters" subtitle="Narrow by company, status, category, metadata and subtype">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2 xl:col-span-2"
              placeholder="Search URL/type/company"
            />

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
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
            >
              <option value="ALL">All Status</option>
              <option value="NEW">NEW</option>
              <option value="UPDATED">UPDATED</option>
              <option value="UNCHANGED">UNCHANGED</option>
              <option value="FAILED">FAILED</option>
            </select>

            <select
              value={categoryFilter}
              onChange={(event) => setCategoryFilter(event.target.value as CategoryFilter)}
              className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
            >
              <option value="ALL">All Categories</option>
              <option value="FINANCIAL">Financial</option>
              <option value="NON_FINANCIAL">Non-Financial</option>
              <option value="UNKNOWN">Unknown</option>
            </select>

            <select
              value={metadataFilter}
              onChange={(event) => setMetadataFilter(event.target.value as MetadataFilter)}
              className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
            >
              <option value="ALL">All Metadata</option>
              <option value="EXTRACTED">Extracted</option>
              <option value="PENDING">Pending</option>
            </select>
          </div>
          <div className="mt-3">
            <select
              value={subtypeFilter}
              onChange={(event) => setSubtypeFilter(event.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2 md:w-72"
            >
              {subtypes.map((subtype) => (
                <option key={subtype} value={subtype}>
                  {subtype === 'ALL' ? 'All Subtypes' : subtype}
                </option>
              ))}
            </select>
          </div>
        </SectionCard>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <SectionCard title="Documents" subtitle={`Showing ${filteredDocs.length} records`}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[820px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-left text-slate-400">
                    <th className="py-2">Company</th>
                    <th className="py-2">Category</th>
                    <th className="py-2">Subtype</th>
                    <th className="py-2">Status</th>
                    <th className="py-2">Metadata</th>
                    <th className="py-2">URL</th>
                  </tr>
                </thead>
                <tbody>
                  {documentsQuery.isLoading ? (
                    <tr>
                      <td colSpan={6} className="py-3 text-slate-500">
                        Loading documents...
                      </td>
                    </tr>
                  ) : null}

                  {filteredDocs.slice(0, 250).map((doc) => {
                    const category = categoryOf(doc.doc_type || '')
                    const subtype = subtypeOf(doc.doc_type || 'UNKNOWN')
                    return (
                      <tr
                        key={doc.id}
                        className={`cursor-pointer border-b border-slate-800/80 text-slate-200 ${
                          selectedDocId === doc.id ? 'bg-slate-800/40' : ''
                        }`}
                        onClick={() => setSelectedDocId(doc.id)}
                      >
                        <td className="py-2">{companyNameById.get(doc.company_id) ?? `#${doc.company_id}`}</td>
                        <td className="py-2">{category}</td>
                        <td className="py-2">{subtype}</td>
                        <td className="py-2">{doc.status}</td>
                        <td className="py-2">{doc.metadata_extracted ? 'Yes' : 'No'}</td>
                        <td className="max-w-[260px] truncate py-2">
                          <a
                            href={doc.document_url}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(event) => event.stopPropagation()}
                            className="text-cyan-300 hover:text-cyan-200"
                          >
                            {doc.document_url}
                          </a>
                        </td>
                      </tr>
                    )
                  })}

                  {!documentsQuery.isLoading && filteredDocs.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-3 text-slate-500">
                        No documents match current filters.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            {filteredDocs.length > 250 ? (
              <p className="mt-3 text-xs text-slate-500">Showing first 250 records for UI performance. Refine filters for deeper inspection.</p>
            ) : null}
          </SectionCard>
        </div>

        <div>
          <SectionCard title="Document Details" subtitle="Selected record and extracted metadata">
            {!selectedDoc ? (
              <p className="text-sm text-slate-500">Select a document row to inspect details.</p>
            ) : (
              <div className="space-y-3 text-sm">
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">Document ID</p>
                  <p className="text-slate-100">{selectedDoc.id}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">Company</p>
                  <p className="text-slate-100">{companyNameById.get(selectedDoc.company_id) ?? selectedDoc.company_id}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">Type</p>
                  <p className="text-slate-100">{selectedDoc.doc_type}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">Status</p>
                  <p className="text-slate-100">{selectedDoc.status}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">Created At</p>
                  <p className="text-slate-100">{selectedDoc.created_at}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">Metadata Extracted</p>
                  <p className="text-slate-100">{selectedDoc.metadata_extracted ? 'Yes' : 'No'}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wider text-slate-500">Metadata Payload</p>
                  {selectedMetadataQuery.isLoading ? (
                    <p className="text-slate-500">Loading metadata...</p>
                  ) : selectedMetadataQuery.isError ? (
                    <p className="text-slate-500">No metadata available for this document.</p>
                  ) : (
                    <pre className="max-h-72 overflow-auto rounded-lg border border-slate-700 bg-slate-900/60 p-3 text-xs text-slate-200">
                      {JSON.stringify(selectedMetadataQuery.data, null, 2)}
                    </pre>
                  )}
                </div>
              </div>
            )}
          </SectionCard>
        </div>
      </section>
    </main>
  )
}
