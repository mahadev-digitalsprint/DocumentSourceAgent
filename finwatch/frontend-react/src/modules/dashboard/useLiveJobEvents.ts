import { useEffect, useMemo, useState } from 'react'

type JobEvent = {
  ts: string
  message: string
}

type EventPayload = {
  run_id?: string
  trigger_type?: string
  status?: string
  company_name?: string
}

export function useLiveJobEvents() {
  const [events, setEvents] = useState<JobEvent[]>([])
  const apiBase = useMemo(() => import.meta.env.VITE_API_BASE ?? '/api', [])

  useEffect(() => {
    const source = new EventSource(`${apiBase}/jobs/events`)
    source.addEventListener('job:event', (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent).data) as EventPayload
        const parts = [payload.trigger_type, payload.status, payload.company_name].filter(Boolean)
        const message = parts.length > 0 ? parts.join(' | ') : payload.run_id ?? 'Job update'
        setEvents((prev) => [{ ts: new Date().toISOString(), message }, ...prev].slice(0, 20))
      } catch {
        setEvents((prev) => [{ ts: new Date().toISOString(), message: 'Job update' }, ...prev].slice(0, 20))
      }
    })

    source.onerror = () => {
      source.close()
    }
    return () => source.close()
  }, [apiBase])

  return events
}
