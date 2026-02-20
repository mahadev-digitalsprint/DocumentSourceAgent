import { useEffect, useMemo, useState } from 'react'
import { io, type Socket } from 'socket.io-client'

type JobEvent = {
  ts: string
  message: string
}

export function useLiveJobEvents() {
  const [events, setEvents] = useState<JobEvent[]>([])

  const socketUrl = useMemo(() => import.meta.env.VITE_SOCKET_URL, [])

  useEffect(() => {
    if (!socketUrl) {
      return
    }

    const socket: Socket = io(socketUrl, {
      transports: ['websocket'],
      reconnectionAttempts: 3,
    })

    socket.on('connect_error', () => {
      // Best-effort live updates only; ignore errors silently.
    })

    socket.on('job:event', (payload: { message?: string }) => {
      setEvents((prev) =>
        [{ ts: new Date().toISOString(), message: payload?.message ?? 'Job update' }, ...prev].slice(0, 20),
      )
    })

    return () => {
      socket.disconnect()
    }
  }, [socketUrl])

  return events
}
