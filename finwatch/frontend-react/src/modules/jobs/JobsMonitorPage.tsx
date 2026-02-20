import { useCallback, useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { jobsApi } from '../../shared/api'
import type { DirectRunResult, JobRunHistoryItem } from '../../shared/types'
import { SectionCard } from '../dashboard/SectionCard'

type TrackedJob = {
  runId: string
  jobId?: string
  purpose: string
  mode: string
  status: string
  companyName?: string
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
  if (s.includes('STARTED') || s.includes('PROGRESS') || s.includes('PENDING') || s.includes('QUEUED') || s.includes('RETRY')) return 'text-warn'
  return 'text-slate-300'
}

function purposeLabel(triggerType: string) {
  const t = (triggerType || '').toUpperCase()
  if (t === 'PIPELINE_ALL') return 'RUN_ALL'
  if (t === 'PIPELINE') return 'PIPELINE'
  if (t === 'WEBWATCH') return 'WEBWATCH'
  if (t === 'DIGEST') return 'DIGEST'
  if (t === 'EXCEL') return 'EXCEL'
  return t || 'JOB'
}

function toIso(value?: string | null) {
  if (!value) return new Date().toISOString()
  return value.includes('T') ? value : value.replace(' ', 'T')
}

function historyToTracked(job: JobRunHistoryItem): TrackedJob {
  return {
    runId: job.run_id,
    jobId: job.celery_job_id ?? undefined,
    purpose: purposeLabel(job.trigger_type),
    mode: job.mode,
    status: job.status,
    companyName: job.company_name ?? undefined,
    createdAt: toIso(job.created_at),
    updatedAt: toIso(job.updated_at ?? job.finished_at ?? job.started_at ?? job.created_at),
    result: job.result_payload ?? null,
  }
}

export function JobsMonitorPage() {
  const queryClient = useQueryClient()
  const [trackedJobs, setTrackedJobs] = useState<TrackedJob[]>([])
  const [directRuns, setDirectRuns] = useState<DirectRunEntry[]>([])
  const [lastError, setLastError] = useState('')
  const [isPolling, setIsPolling] = useState(true)
  const [schedulerEnabled, setSchedulerEnabled] = useState(true)
  const [schedulerPollSeconds, setSchedulerPollSeconds] = useState(15)
  const [pipelineIntervalMinutes, setPipelineIntervalMinutes] = useState(120)
  const [webwatchIntervalMinutes, setWebwatchIntervalMinutes] = useState(60)
  const [digestHourUtc, setDigestHourUtc] = useState(0)
  const [digestMinuteUtc, setDigestMinuteUtc] = useState(30)
  const [schedulerMessage, setSchedulerMessage] = useState('')

  const historyQuery = useQuery({
    queryKey: ['jobHistory', 100],
    queryFn: () => jobsApi.history(100),
    refetchInterval: 60_000,
  })
  const schedulerQuery = useQuery({
    queryKey: ['schedulerStatus'],
    queryFn: jobsApi.schedulerStatus,
    refetchInterval: 20_000,
  })

  useEffect(() => {
    const history = historyQuery.data ?? []
    if (history.length === 0) return
    const mapped = history.map(historyToTracked)
    setTrackedJobs((prev) => {
      const merged = new Map<string, TrackedJob>()
      for (const job of prev) merged.set(job.runId, job)
      for (const job of mapped) merged.set(job.runId, { ...(merged.get(job.runId) ?? {}), ...job })
      return Array.from(merged.values())
        .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
        .slice(0, 100)
    })
  }, [historyQuery.data])

  useEffect(() => {
    if (!schedulerQuery.data) return
    setSchedulerEnabled(Boolean(schedulerQuery.data.enabled))
    setSchedulerPollSeconds(Number(schedulerQuery.data.poll_seconds || 15))
    setPipelineIntervalMinutes(Number(schedulerQuery.data.pipeline_interval_minutes || 120))
    setWebwatchIntervalMinutes(Number(schedulerQuery.data.webwatch_interval_minutes || 60))
    setDigestHourUtc(Number(schedulerQuery.data.digest_hour_utc || 0))
    setDigestMinuteUtc(Number(schedulerQuery.data.digest_minute_utc || 30))
  }, [schedulerQuery.data])

  useEffect(() => {
    const base = import.meta.env.VITE_API_BASE ?? '/api'
    const source = new EventSource(`${base}/jobs/events`)
    source.addEventListener('job:event', (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent).data) as JobRunHistoryItem
        const incoming = historyToTracked(payload)
        setTrackedJobs((prev) => {
          const next = new Map(prev.map((job) => [job.runId, job]))
          const existing = next.get(incoming.runId)
          next.set(incoming.runId, { ...(existing ?? {}), ...incoming })
          return Array.from(next.values())
            .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
            .slice(0, 100)
        })
      } catch {
        // ignore malformed event payload
      }
    })
    source.onerror = () => {
      source.close()
    }
    return () => source.close()
  }, [])

  const addTrackedJob = (runId: string | undefined, jobId: string | undefined, purpose: string, status: string) => {
    if (!runId) return
    const now = new Date().toISOString()
    setTrackedJobs((prev) => [{ runId, jobId, purpose, mode: 'QUEUED', status, createdAt: now, updatedAt: now }, ...prev].slice(0, 100))
  }

  const addDirectRunSummary = (mode: DirectRunEntry['mode'], summary: string) => {
    setDirectRuns((prev) => [{ id: `${Date.now()}-${mode}`, mode, createdAt: new Date().toISOString(), summary }, ...prev].slice(0, 20))
  }

  const runAllQueuedMutation = useMutation({
    mutationFn: jobsApi.runAllQueued,
    onSuccess: (data) => {
      addTrackedJob(data.run_id, data.job_id, 'RUN_ALL', data.status)
      setLastError('')
      void queryClient.invalidateQueries({ queryKey: ['jobHistory'] })
    },
    onError: (error: Error) => setLastError(error.message),
  })

  const webwatchQueuedMutation = useMutation({
    mutationFn: jobsApi.webwatchQueued,
    onSuccess: (data) => {
      addTrackedJob(data.run_id, data.job_id, 'WEBWATCH', data.status)
      setLastError('')
      void queryClient.invalidateQueries({ queryKey: ['jobHistory'] })
    },
    onError: (error: Error) => setLastError(error.message),
  })

  const runAllDirectMutation = useMutation({
    mutationFn: jobsApi.runAllDirect,
    onSuccess: (data: DirectRunResult) => {
      const summary = data.result
        ? `Companies=${data.result.total_companies} | Success=${data.result.succeeded} | Failed=${data.result.failed}`
        : 'Direct pipeline finished.'
      addDirectRunSummary('RUN_ALL_DIRECT', summary)
      if (data.run_id) {
        addTrackedJob(data.run_id, data.job_id, 'RUN_ALL', data.status)
      }
      setLastError('')
      void queryClient.invalidateQueries({ queryKey: ['companies'] })
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      void queryClient.invalidateQueries({ queryKey: ['docChanges'] })
      void queryClient.invalidateQueries({ queryKey: ['pageChanges'] })
      void queryClient.invalidateQueries({ queryKey: ['jobHistory'] })
    },
    onError: (error: Error) => setLastError(error.message),
  })

  const webwatchDirectMutation = useMutation({
    mutationFn: jobsApi.webwatchDirect,
    onSuccess: (data) => {
      const companies = data.result?.companies ?? []
      const changed = companies.reduce((acc, item) => acc + (item.page_changes ?? 0), 0)
      addDirectRunSummary('WEBWATCH_DIRECT', `Companies=${companies.length} | Total page changes=${changed}`)
      if (data.run_id) {
        addTrackedJob(data.run_id, data.job_id, 'WEBWATCH', data.status)
      }
      setLastError('')
      void queryClient.invalidateQueries({ queryKey: ['pageChanges'] })
      void queryClient.invalidateQueries({ queryKey: ['jobHistory'] })
    },
    onError: (error: Error) => setLastError(error.message),
  })

  const saveSchedulerMutation = useMutation({
    mutationFn: () =>
      jobsApi.schedulerConfig({
        enabled: schedulerEnabled,
        poll_seconds: schedulerPollSeconds,
        pipeline_interval_minutes: pipelineIntervalMinutes,
        webwatch_interval_minutes: webwatchIntervalMinutes,
        digest_hour_utc: digestHourUtc,
        digest_minute_utc: digestMinuteUtc,
      }),
    onSuccess: () => {
      setSchedulerMessage('Scheduler settings saved.')
      void queryClient.invalidateQueries({ queryKey: ['schedulerStatus'] })
    },
    onError: (error: Error) => setSchedulerMessage(error.message),
  })

  const tickSchedulerMutation = useMutation({
    mutationFn: jobsApi.schedulerTick,
    onSuccess: (data) => {
      const triggerCount = data.triggers?.length ?? 0
      setSchedulerMessage(`Scheduler tick completed. Triggered ${triggerCount} job(s).`)
      for (const trigger of data.triggers ?? []) {
        addTrackedJob(trigger.run_id, undefined, trigger.trigger_type, 'QUEUED')
      }
      void queryClient.invalidateQueries({ queryKey: ['jobHistory'] })
      void queryClient.invalidateQueries({ queryKey: ['schedulerStatus'] })
    },
    onError: (error: Error) => setSchedulerMessage(error.message),
  })

  const refreshStatuses = useCallback(async () => {
    const pendingStatuses = new Set(['QUEUED', 'PENDING', 'STARTED', 'PROGRESS', 'RETRY', 'RETRYING'])
    const candidates = trackedJobs.filter((job) => pendingStatuses.has(job.status.toUpperCase()))
    if (candidates.length === 0) return

    const updates = await Promise.all(
      candidates.map(async (job) => {
        try {
          if (job.runId) {
            const latest = await jobsApi.statusByRunId(job.runId)
            return {
              runId: latest.run_id,
              status: latest.status,
              jobId: latest.celery_job_id ?? undefined,
              result: latest.result_payload ?? null,
              updatedAt: new Date().toISOString(),
            }
          }
          if (job.jobId) {
            const latest = await jobsApi.status(job.jobId)
            return {
              runId: job.runId,
              status: latest.status,
              jobId: latest.job_id,
              result: latest.result ?? null,
              updatedAt: new Date().toISOString(),
            }
          }
          return null
        } catch {
          return {
            runId: job.runId,
            status: 'UNKNOWN',
            jobId: job.jobId,
            result: null,
            updatedAt: new Date().toISOString(),
          }
        }
      }),
    )

    setTrackedJobs((prev) =>
      prev.map((job) => {
        const latest = updates.find((item) => item?.runId === job.runId)
        if (!latest) return job
        return { ...job, status: latest.status, jobId: latest.jobId, result: latest.result, updatedAt: latest.updatedAt }
      }),
    )
  }, [trackedJobs])

  useEffect(() => {
    if (!isPolling) return
    const timer = window.setInterval(() => {
      void refreshStatuses()
    }, 10_000)
    return () => window.clearInterval(timer)
  }, [isPolling, refreshStatuses])

  const busy =
    runAllQueuedMutation.isPending ||
    runAllDirectMutation.isPending ||
    webwatchQueuedMutation.isPending ||
    webwatchDirectMutation.isPending

  const counts = useMemo(() => {
    const queued = trackedJobs.filter((job) => ['QUEUED', 'PENDING', 'STARTED', 'PROGRESS', 'RETRY', 'RETRYING'].includes(job.status.toUpperCase())).length
    const completed = trackedJobs.filter((job) => ['SUCCESS', 'DONE'].includes(job.status.toUpperCase())).length
    const failed = trackedJobs.filter((job) => job.status.toUpperCase().includes('FAIL')).length
    return { queued, completed, failed }
  }, [trackedJobs])

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">
      <header className="mb-6 rounded-2xl border border-slate-700/70 bg-panel/80 p-5 shadow-panel">
        <h1 className="text-2xl font-semibold text-slate-50 md:text-3xl">Crawl Jobs Monitor</h1>
        <p className="mt-2 text-sm text-slate-300">Queue or run direct jobs, then track status and outcomes in real time.</p>
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
          subtitle="Event stream live updates + polling fallback"
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

      <section className="mt-6">
        <SectionCard
          title="Scheduler Control Plane"
          subtitle="DB-backed schedule controls with single-flight launch protection"
          action={
            <div className="flex gap-2">
              <button
                onClick={() => tickSchedulerMutation.mutate()}
                disabled={tickSchedulerMutation.isPending}
                className="rounded-md bg-slate-700 px-3 py-1 text-xs font-semibold text-slate-100 hover:bg-slate-600 disabled:cursor-not-allowed"
              >
                Tick Now
              </button>
              <button
                onClick={() => saveSchedulerMutation.mutate()}
                disabled={saveSchedulerMutation.isPending}
                className="rounded-md bg-accent px-3 py-1 text-xs font-semibold text-slate-950 hover:bg-emerald-300 disabled:cursor-not-allowed"
              >
                Save
              </button>
            </div>
          }
        >
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
            <label className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100">
              <input type="checkbox" checked={schedulerEnabled} onChange={(event) => setSchedulerEnabled(event.target.checked)} />
              Scheduler Enabled
            </label>
            <label className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100">
              Poll (s)
              <input
                type="number"
                min={5}
                max={300}
                value={schedulerPollSeconds}
                onChange={(event) => setSchedulerPollSeconds(Number(event.target.value))}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
              />
            </label>
            <label className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100">
              Pipeline Interval (min)
              <input
                type="number"
                min={15}
                max={1440}
                value={pipelineIntervalMinutes}
                onChange={(event) => setPipelineIntervalMinutes(Number(event.target.value))}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
              />
            </label>
            <label className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100">
              WebWatch Interval (min)
              <input
                type="number"
                min={5}
                max={1440}
                value={webwatchIntervalMinutes}
                onChange={(event) => setWebwatchIntervalMinutes(Number(event.target.value))}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
              />
            </label>
            <label className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100">
              Digest Hour (UTC)
              <input
                type="number"
                min={0}
                max={23}
                value={digestHourUtc}
                onChange={(event) => setDigestHourUtc(Number(event.target.value))}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
              />
            </label>
            <label className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-100">
              Digest Minute (UTC)
              <input
                type="number"
                min={0}
                max={59}
                value={digestMinuteUtc}
                onChange={(event) => setDigestMinuteUtc(Number(event.target.value))}
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
              />
            </label>
          </div>
          <div className="mt-3 grid gap-2 text-xs text-slate-400 md:grid-cols-2 xl:grid-cols-4">
            <p>Last Tick: {schedulerQuery.data?.last_tick_at || '-'}</p>
            <p>Last Pipeline: {schedulerQuery.data?.last_pipeline_run_at || '-'}</p>
            <p>Last WebWatch: {schedulerQuery.data?.last_webwatch_run_at || '-'}</p>
            <p>Last Digest: {schedulerQuery.data?.last_digest_run_at || '-'}</p>
          </div>
          {schedulerQuery.data?.last_error ? (
            <p className="mt-3 rounded-md border border-red-500/40 bg-red-950/30 p-2 text-xs text-red-200">{schedulerQuery.data.last_error}</p>
          ) : null}
          {schedulerMessage ? <p className="mt-3 rounded-md border border-emerald-500/40 bg-emerald-950/30 p-2 text-xs text-emerald-200">{schedulerMessage}</p> : null}
        </SectionCard>
      </section>

      <section className="mt-6 grid gap-4 xl:grid-cols-2">
        <SectionCard title="Job Runs" subtitle="Live operational run history with statuses">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[780px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-700 text-left text-slate-400">
                  <th className="py-2">Run ID</th>
                  <th className="py-2">Job ID</th>
                  <th className="py-2">Purpose</th>
                  <th className="py-2">Mode</th>
                  <th className="py-2">Status</th>
                  <th className="py-2">Updated</th>
                </tr>
              </thead>
              <tbody>
                {trackedJobs.map((job) => (
                  <tr key={job.runId} className="border-b border-slate-800/80 text-slate-200">
                    <td className="max-w-[180px] truncate py-2 font-mono text-xs">{job.runId}</td>
                    <td className="max-w-[180px] truncate py-2 font-mono text-xs">{job.jobId ?? '-'}</td>
                    <td className="py-2">{job.purpose}</td>
                    <td className="py-2">{job.mode}</td>
                    <td className={`py-2 font-semibold ${statusTone(job.status)}`}>{job.status}</td>
                    <td className="py-2 text-slate-400">{job.updatedAt.replace('T', ' ').slice(0, 19)}</td>
                  </tr>
                ))}
                {trackedJobs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-3 text-slate-500">
                      No jobs tracked yet.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </SectionCard>

        <SectionCard title="Direct Run Notes" subtitle="Results from synchronous job executions">
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
