import { useMemo, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { companyApi } from '../../shared/api'
import { SectionCard } from '../dashboard/SectionCard'

type StatusFilter = 'ALL' | 'ACTIVE' | 'INACTIVE'

export function CompanyManagerPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL')
  const [name, setName] = useState('')
  const [websiteUrl, setWebsiteUrl] = useState('')
  const [crawlDepth, setCrawlDepth] = useState(3)
  const [formError, setFormError] = useState('')

  const companiesQuery = useQuery({
    queryKey: ['companies'],
    queryFn: companyApi.list,
  })

  const createMutation = useMutation({
    mutationFn: companyApi.create,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['companies'] })
      setName('')
      setWebsiteUrl('')
      setCrawlDepth(3)
      setFormError('')
    },
    onError: (error: Error) => {
      setFormError(error.message)
    },
  })

  const toggleMutation = useMutation({
    mutationFn: companyApi.toggle,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['companies'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: companyApi.remove,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['companies'] })
    },
  })

  const companies = companiesQuery.data ?? []

  const filteredCompanies = useMemo(() => {
    const term = search.trim().toLowerCase()
    return companies.filter((company) => {
      const matchesSearch =
        term.length === 0 ||
        company.company_name.toLowerCase().includes(term) ||
        company.website_url.toLowerCase().includes(term)
      const matchesStatus =
        statusFilter === 'ALL' ||
        (statusFilter === 'ACTIVE' && company.active) ||
        (statusFilter === 'INACTIVE' && !company.active)
      return matchesSearch && matchesStatus
    })
  }, [companies, search, statusFilter])

  const activeCount = companies.filter((company) => company.active).length
  const inactiveCount = companies.length - activeCount

  const submitNewCompany = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFormError('')

    const payload = {
      company_name: name.trim(),
      website_url: websiteUrl.trim(),
      crawl_depth: crawlDepth,
    }

    if (!payload.company_name || !payload.website_url) {
      setFormError('Company name and website URL are required.')
      return
    }

    createMutation.mutate(payload)
  }

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">
      <header className="mb-6 rounded-2xl border border-slate-700/70 bg-panel/80 p-5 shadow-panel">
        <h1 className="text-2xl font-semibold text-slate-50 md:text-3xl">Company Manager</h1>
        <p className="mt-2 text-sm text-slate-300">Manage tracked investor-relations websites and crawl depth.</p>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Total</p>
          <p className="mt-2 text-3xl font-semibold text-slate-100">{companies.length}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Active</p>
          <p className="mt-2 text-3xl font-semibold text-accent">{activeCount}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Inactive</p>
          <p className="mt-2 text-3xl font-semibold text-warn">{inactiveCount}</p>
        </article>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-5">
        <div className="xl:col-span-2">
          <SectionCard title="Add Company" subtitle="Register a company for crawl and monitoring">
            <form className="space-y-3" onSubmit={submitNewCompany}>
              <div>
                <label className="mb-1 block text-sm text-slate-300" htmlFor="company_name">
                  Company Name
                </label>
                <input
                  id="company_name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
                  placeholder="Infosys Ltd"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm text-slate-300" htmlFor="website_url">
                  Investor URL
                </label>
                <input
                  id="website_url"
                  value={websiteUrl}
                  onChange={(event) => setWebsiteUrl(event.target.value)}
                  className="w-full rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
                  placeholder="https://example.com/investors"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm text-slate-300" htmlFor="crawl_depth">
                  Crawl Depth
                </label>
                <input
                  id="crawl_depth"
                  type="number"
                  min={1}
                  max={5}
                  value={crawlDepth}
                  onChange={(event) => setCrawlDepth(Number(event.target.value))}
                  className="w-full rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
                />
              </div>

              {formError ? <p className="text-sm text-danger">{formError}</p> : null}

              <button
                type="submit"
                disabled={createMutation.isPending}
                className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
              >
                {createMutation.isPending ? 'Adding...' : 'Add Company'}
              </button>
            </form>
          </SectionCard>
        </div>

        <div className="xl:col-span-3">
          <SectionCard title="Tracked Companies" subtitle="Search, toggle monitoring status, and delete records">
            <div className="mb-3 grid gap-3 sm:grid-cols-2">
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
                placeholder="Search by name or URL"
              />
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
                className="w-full rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
              >
                <option value="ALL">All</option>
                <option value="ACTIVE">Active</option>
                <option value="INACTIVE">Inactive</option>
              </select>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[740px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-left text-slate-400">
                    <th className="py-2">Company</th>
                    <th className="py-2">Website</th>
                    <th className="py-2">Depth</th>
                    <th className="py-2">Status</th>
                    <th className="py-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {companiesQuery.isLoading ? (
                    <tr>
                      <td colSpan={5} className="py-3 text-slate-500">
                        Loading companies...
                      </td>
                    </tr>
                  ) : null}

                  {filteredCompanies.map((company) => (
                    <tr key={company.id} className="border-b border-slate-800/80 text-slate-200">
                      <td className="py-3 font-medium">{company.company_name}</td>
                      <td className="max-w-[320px] truncate py-3 text-slate-300">{company.website_url}</td>
                      <td className="py-3">{company.crawl_depth}</td>
                      <td className="py-3">
                        <span
                          className={`rounded-full px-2 py-1 text-xs font-semibold ${
                            company.active ? 'bg-emerald-900/60 text-accent' : 'bg-amber-900/50 text-warn'
                          }`}
                        >
                          {company.active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="py-3">
                        <div className="flex gap-2">
                          <button
                            onClick={() => toggleMutation.mutate(company.id)}
                            className="rounded-md bg-slate-700 px-3 py-1 text-xs font-semibold text-slate-100 hover:bg-slate-600"
                          >
                            {company.active ? 'Pause' : 'Resume'}
                          </button>
                          <button
                            onClick={() => deleteMutation.mutate(company.id)}
                            className="rounded-md bg-red-900/70 px-3 py-1 text-xs font-semibold text-red-100 hover:bg-red-800/80"
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}

                  {!companiesQuery.isLoading && filteredCompanies.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-3 text-slate-500">
                        No companies match current filters.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </div>
      </section>
    </main>
  )
}
