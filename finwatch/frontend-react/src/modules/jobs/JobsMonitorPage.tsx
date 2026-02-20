import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { jobsApi } from '../../shared/api'
import type { DirectRunResult } from '../../shared/types'
import { SectionCard } from '../dashboard/SectionCard'

type TrackedJob = {
  jobId: string
  purpose: 'RUN_ALL' | 'WEBWATCH'
  status: string
  createdAt: string
  updatedAt: string
  result?: Record<string, unknown> | null
}

type DirectRunEntry = {
  id: string
  mode: 'RUN_ALL_DIRECT' | 'WEBWATCH_DIRECT'
  createdAt: string
  summary: string
}

function statusTone(status: string) {
  const s = status.toUpperCase()
  if (s.includes('SUCCESS') || s.includes('DONE')) return 'text-accent'
  if (s.includes('FAIL')) return 'text-danger'
  if (s.includes('STARTED') || s.includes('PROGRESS') || s.includes('PENDING') || s.includes('QUEUED')) return 'text-warn'
  return 'text-slate-300'
}

export function JobsMonitorPage() {
  const queryClient = useQueryClient()
  const [trackedJobs, setTrackedJobs] = useState<TrackedJob[]>([])
  const [directRuns, setDirectRuns] = useState<DirectRunEntry[]>([])
  const [lastError, setLastError] = useState('')
  const [isPolling, setIsPolling] = useState(true)

  const addTrackedJob = (jobId: string, purpose: TrackedJob['purpose'], status: string) => {
    const now = new Date().toISOString()
    setTrackedJobs((prev) => [{ jobId, purpose, status, createdAt: now, updatedAt: now }, ...prev].slice(0, 30))
  }

  const addDirectRunSummary = (mode: DirectRunEntry['mode'], summary: string) => {
    setDirectRuns((prev) => [{ id: `${Date.now()}-${mode}`, mode, createdAt: new Date().toISOString(), summary }, ...prev].slice(0, 20))
  }

  const runAllQueuedMutation = useMutation({
    mutationFn: jobsApi.runAllQueued,
    onSuccess: (data) => {
      addTrackedJob(data.job_id, 'RUN_ALL', data.status)
      setLastError('')
    },
    onError: (error: Error) => {
      setLastError(error.message)
    },
  })

  const webwatchQueuedMutation = useMutation({
    mutationFn: jobsApi.webwatchQueued,
    onSuccess: (data) => {
      addTrackedJob(data.job_id, 'WEBWATCH', data.status)
      setLastError('')
    },
    onError: (error: Error) => {
      setLastError(error.message)
    },
  })

  const runAllDirectMutation = useMutation({
    mutationFn: jobsApi.runAllDirect,
    onSuccess: (data: DirectRunResult) => {
      const summary = data.result
        ? `Companies=${data.result.total_companies} | Success=${data.result.succeeded} | Failed=${data.result.failed}`
        : 'Direct pipeline finished.'
      addDirectRunSummary('RUN_ALL_DIRECT', summary)
      setLastError('')
      void queryClient.invalidateQueries({ queryKey: ['companies'] })
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      void queryClient.invalidateQueries({ queryKey: ['docChanges'] })
      void queryClient.invalidateQueries({ queryKey: ['pageChanges'] })
    },
    onError: (error: Error) => {
      setLastError(error.message)
    },
  })

  const webwatchDirectMutation = useMutation({
    mutationFn: jobsApi.webwatchDirect,
    onSuccess: (data) => {
      const companies = data.result?.companies ?? []
      const changed = companies.reduce((acc, item) => acc + (item.page_changes ?? 0), 0)
      addDirectRunSummary('WEBWATCH_DIRECT', `Companies=${companies.length} | Total page changes=${changed}`)
      setLastError('')
      void queryClient.invalidateQueries({ queryKey: ['pageChanges'] })
    },
    onError: (error: Error) => {
      setLastError(error.message)
    },
  })

  const refreshStatuses = async () => {
    const pendingStatuses = new Set(['QUEUED', 'PENDING', 'STARTED', 'PROGRESS', 'RETRY'])
    const candidates = trackedJobs.filter((job) => pendingStatuses.has(job.status.toUpperCase()))
    if (candidates.length === 0) return

    const updates = await Promise.all(
      candidates.map(async (job) => {
        try {
          const latest = await jobsApi.status(job.jobId)
          return { jobId: job.jobId, status: latest.status, result: latest.result ?? null, updatedAt: new Date().toISOString() }
        } catch {
          return { jobId: job.jobId, status: 'UNKNOWN', result: null, updatedAt: new Date().toISOString() }
        }
      }),
    )

    setTrackedJobs((prev) =>
      prev.map((job) => {
        const latest = updates.find((item) => item.jobId === job.jobId)
        if (!latest) return job
        return { ...job, status: latest.status, result: latest.result, updatedAt: latest.updatedAt }
      }),
    )
  }

  useEffect(() => {
    if (!isPolling) return
    const timer = window.setInterval(() => {
      void refreshStatuses()
    }, 10_000)
    return () => window.clearInterval(timer)
  })

  const busy =
    runAllQueuedMutation.isPending ||
    runAllDirectMutation.isPending ||
    webwatchQueuedMutation.isPending ||
    webwatchDirectMutation.isPending

  const counts = useMemo(() => {
    const queued = trackedJobs.filter((job) => ['QUEUED', 'PENDING', 'STARTED', 'PROGRESS', 'RETRY'].includes(job.status.toUpperCase())).length
    const completed = trackedJobs.filter((job) => ['SUCCESS', 'DONE'].includes(job.status.toUpperCase())).length
    const failed = trackedJobs.filter((job) => job.status.toUpperCase().includes('FAIL')).length
    return { queued, completed, failed }
  }, [trackedJobs])

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">
      <header className="mb-6 rounded-2xl border border-slate-700/70 bg-panel/80 p-5 shadow-panel">
        <h1 className="text-2xl font-semibold text-slate-50 md:text-3xl">Crawl Jobs Monitor</h1>
        <p className="mt-2 text-sm text-slate-300">Queue or run direct jobs, then track status and outcomes.</p>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Queued/In Progress</p>
          <p className="mt-2 text-3xl font-semibold text-warn">{counts.queued}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Completed</p>
          <p className="mt-2 text-3xl font-semibold text-accent">{counts.completed}</p>
        </article>
        <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
          <p className="text-xs uppercase tracking-wider text-slate-400">Failed</p>
          <p className="mt-2 text-3xl font-semibold text-danger">{counts.failed}</p>
        </article>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-2">
        <SectionCard title="Run Jobs" subtitle="Use queued mode when Celery is available, direct mode otherwise">
          <div className="grid gap-2 sm:grid-cols-2">
            <button
              disabled={busy}
              onClick={() => runAllQueuedMutation.mutate()}
              className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-semibold text-slate-100 hover:bg-slate-600 disabled:cursor-not-allowed disabled:bg-slate-800"
            >
              Queue Run All
            </button>
            <button
              disabled={busy}
              onClick={() => runAllDirectMutation.mutate()}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-300 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
            >
              Run All Direct
            </button>
            <button
              disabled={busy}
              onClick={() => webwatchQueuedMutation.mutate()}
              className="rounded-lg bg-slate-700 px-4 py-2 text-sm font-semibold text-slate-100 hover:bg-slate-600 disabled:cursor-not-allowed disabled:bg-slate-800"
            >
              Queue WebWatch
            </button>
            <button
              disabled={busy}
              onClick={() => webwatchDirectMutation.mutate()}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-300 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
            >
              WebWatch Direct
            </button>
          </div>

          {lastError ? <p className="mt-3 rounded-md border border-red-500/40 bg-red-950/30 p-2 text-sm text-red-200">{lastError}</p> : null}
        </SectionCard>

        <SectionCard
          title="Monitor Controls"
          subtitle="Status polling for tracked queued jobs"
          action={
            <button
              onClick={() => setIsPolling((v) => !v)}
              className="rounded-md bg-slate-700 px-3 py-1 text-xs font-semibold text-slate-100 hover:bg-slate-600"
            >
              {isPolling ? 'Pause Polling' : 'Resume Polling'}
            </button>
          }
        >
          <div className="flex items-center gap-2">
            <button
              onClick={() => void refreshStatuses()}
              className="rounded-md bg-slate-700 px-3 py-1 text-xs font-semibold text-slate-100 hover:bg-slate-600"
            >
              Refresh Now
            </button>
            <span className="text-xs text-slate-400">Polling interval: 10s</span>
          </div>
        </SectionCard>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-2">
        <SectionCard title="Queued Jobs" subtitle="Tracked Celery jobs and latest status">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-left text-slate-400">
                  <th className="py-2">Job ID</th>
                  <th className="py-2">Purpose</th>
                  <th className="py-2">Status</th>
                  <th className="py-2">Updated</th>
                </tr>
              </thead>
              <tbody>
                {trackedJobs.map((job) => (
                  <tr key={job.jobId} className="border-b border-slate-800/80 text-slate-200">
                    <td className="max-w-[220px] truncate py-2 font-mono text-xs">{job.jobId}</td>
                    <td className="py-2">{job.purpose}</td>
                    <td className={`py-2 font-semibold ${statusTone(job.status)}`}>{job.status}</td>
                    <td className="py-2 text-slate-400">{job.updatedAt.slice(11, 19)}</td>
                  </tr>
                ))}
                {trackedJobs.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-3 text-slate-500">
                      No queued jobs tracked yet.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </SectionCard>

        <SectionCard title="Direct Run History" subtitle="Results from synchronous job executions">
          <ul className="space-y-2">
            {directRuns.map((entry) => (
              <li key={entry.id} className="rounded-lg border border-slate-700/70 p-3 text-sm text-slate-200">
                <p className="font-semibold text-slate-100">{entry.mode}</p>
                <p className="text-slate-300">{entry.summary}</p>
                <p className="text-xs text-slate-500">{entry.createdAt.replace('T', ' ').slice(0, 19)}</p>
              </li>
            ))}
            {directRuns.length === 0 ? <li className="text-sm text-slate-500">No direct runs yet.</li> : null}
          </ul>
        </SectionCard>
      </section>
    </main>
  )
}
