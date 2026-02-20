import type { ChangeLog, PageChange } from '../../shared/types'
import { SectionCard } from './SectionCard'

type Props = {
  docChanges: ChangeLog[]
  pageChanges: PageChange[]
}

function rowTone(changeType: string) {
  if (changeType.includes('ADDED') || changeType === 'NEW') return 'text-accent'
  if (changeType.includes('DELETED') || changeType === 'REMOVED') return 'text-danger'
  return 'text-warn'
}

export function RecentChangesPanel({ docChanges, pageChanges }: Props) {
  return (
    <SectionCard title="Recent Changes" subtitle="Document and website deltas">
      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-300">Document Changes</h3>
          <ul className="space-y-2">
            {docChanges.slice(0, 6).map((item) => (
              <li key={`d-${item.id}`} className="rounded-lg border border-slate-700/70 p-3 text-sm">
                <p className={`font-medium ${rowTone(item.change_type)}`}>{item.change_type}</p>
                <p className="mt-1 text-slate-300">{item.company_name}</p>
                <p className="truncate text-xs text-slate-400">{item.document_url}</p>
              </li>
            ))}
            {docChanges.length === 0 ? <li className="text-sm text-slate-500">No document changes.</li> : null}
          </ul>
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-300">Page Changes</h3>
          <ul className="space-y-2">
            {pageChanges.slice(0, 6).map((item) => (
              <li key={`p-${item.id}`} className="rounded-lg border border-slate-700/70 p-3 text-sm">
                <p className={`font-medium ${rowTone(item.change_type)}`}>{item.change_type}</p>
                <p className="truncate text-slate-300">{item.page_url}</p>
                <p className="truncate text-xs text-slate-400">{item.diff_summary ?? 'No summary'}</p>
              </li>
            ))}
            {pageChanges.length === 0 ? <li className="text-sm text-slate-500">No page changes.</li> : null}
          </ul>
        </div>
      </div>
    </SectionCard>
  )
}
