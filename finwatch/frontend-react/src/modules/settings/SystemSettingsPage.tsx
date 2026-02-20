import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { dashboardApi, settingsApi } from '../../shared/api'
import { SectionCard } from '../dashboard/SectionCard'

export function SystemSettingsPage() {
  const queryClient = useQueryClient()
  const [basePath, setBasePath] = useState('/app/downloads')
  const [crawlDepth, setCrawlDepth] = useState(3)
  const [message, setMessage] = useState('')
  const [errorMessage, setErrorMessage] = useState('')

  const settingsQuery = useQuery({
    queryKey: ['systemSettings'],
    queryFn: settingsApi.list,
  })

  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: dashboardApi.health,
    refetchInterval: 20_000,
  })

  useEffect(() => {
    const settings = settingsQuery.data
    if (!settings) return
    setBasePath(settings.base_path ?? '/app/downloads')
    setCrawlDepth(Number(settings.crawl_depth ?? 3))
  }, [settingsQuery.data])

  const saveMutation = useMutation({
    mutationFn: async () => {
      await settingsApi.save('base_path', basePath)
      await settingsApi.save('crawl_depth', String(crawlDepth))
      return true
    },
    onSuccess: () => {
      setErrorMessage('')
      setMessage('System settings saved.')
      void queryClient.invalidateQueries({ queryKey: ['systemSettings'] })
    },
    onError: (error: Error) => {
      setMessage('')
      setErrorMessage(error.message)
    },
  })

  return (
    <main className="mx-auto min-h-screen max-w-5xl px-4 py-6 md:px-8">
      <header className="mb-6 rounded-2xl border border-slate-700/70 bg-panel/80 p-5 shadow-panel">
        <h1 className="text-2xl font-semibold text-slate-50 md:text-3xl">System Settings</h1>
        <p className="mt-2 text-sm text-slate-300">Configure platform defaults and check service health.</p>
      </header>

      <section className="grid gap-4 md:grid-cols-2">
        <SectionCard title="Runtime Settings" subtitle="Persistence path and crawl defaults">
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-sm text-slate-300">Base Download Path</label>
              <input
                value={basePath}
                onChange={(event) => setBasePath(event.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-300">Default Crawl Depth</label>
              <input
                type="number"
                min={1}
                max={5}
                value={crawlDepth}
                onChange={(event) => setCrawlDepth(Number(event.target.value))}
                className="w-full rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100 outline-none ring-accent focus:ring-2"
              />
            </div>

            <button
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending}
              className="rounded-md bg-accent px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-300 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
            >
              {saveMutation.isPending ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
          {message ? <p className="mt-3 rounded-md border border-emerald-500/40 bg-emerald-950/30 p-2 text-sm text-emerald-200">{message}</p> : null}
          {errorMessage ? <p className="mt-3 rounded-md border border-red-500/40 bg-red-950/30 p-2 text-sm text-red-200">{errorMessage}</p> : null}
        </SectionCard>

        <SectionCard title="Service Health" subtitle="Backend status and resolved service identity">
          {healthQuery.isLoading ? <p className="text-sm text-slate-400">Checking health...</p> : null}
          {healthQuery.isError ? <p className="text-sm text-red-300">API health check failed.</p> : null}
          {healthQuery.data ? (
            <div className="space-y-2 text-sm">
              <p>
                <span className="text-slate-400">Status:</span>{' '}
                <span className="font-semibold text-accent">{healthQuery.data.status}</span>
              </p>
              <p>
                <span className="text-slate-400">Service:</span>{' '}
                <span className="font-semibold text-slate-100">{healthQuery.data.service}</span>
              </p>
            </div>
          ) : null}

          <div className="mt-4 rounded-lg border border-slate-700/70 bg-slate-900/40 p-3 text-xs text-slate-400">
            <p>Tips:</p>
            <p>1. Use local absolute/volume path for long-running deployments.</p>
            <p>2. Keep crawl depth conservative (2-3) for higher throughput.</p>
          </div>
        </SectionCard>
      </section>
    </main>
  )
}
