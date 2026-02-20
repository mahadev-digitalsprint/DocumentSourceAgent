import { clsx } from 'clsx'
import { SectionCard } from './SectionCard'

type Props = {
  isRunning: boolean
  onRunAll: () => void
  liveEvents: Array<{ ts: string; message: string }>
}

export function CrawlStatusPanel({ isRunning, onRunAll, liveEvents }: Props) {
  return (
    <SectionCard
      title="Crawl Operations"
      subtitle="Trigger and monitor the direct pipeline"
      action={
        <button
          onClick={onRunAll}
          disabled={isRunning}
          className={clsx(
            'rounded-lg px-4 py-2 text-sm font-semibold transition',
            isRunning ? 'cursor-not-allowed bg-slate-600 text-slate-300' : 'bg-accent text-slate-950 hover:bg-emerald-300',
          )}
        >
          {isRunning ? 'Running...' : 'Run All Companies'}
        </button>
      }
    >
      <div className="space-y-2">
        <p className="text-sm text-slate-300">
          Pipeline mode: <span className="font-semibold text-slate-100">Direct / Sync</span>
        </p>
        <p className="text-sm text-slate-300">
          Live status: <span className={isRunning ? 'text-warn' : 'text-accent'}>{isRunning ? 'Active' : 'Idle'}</span>
        </p>
        <ul className="mt-3 max-h-48 space-y-2 overflow-auto rounded-lg border border-slate-700/80 bg-slate-900/40 p-3">
          {liveEvents.length === 0 ? (
            <li className="text-xs text-slate-500">No live events yet. Socket events are optional and appear when configured.</li>
          ) : (
            liveEvents.map((event, idx) => (
              <li key={`${event.ts}-${idx}`} className="text-xs text-slate-300">
                <span className="mr-2 text-slate-500">{event.ts.slice(11, 19)}</span>
                {event.message}
              </li>
            ))
          )}
        </ul>
      </div>
    </SectionCard>
  )
}
