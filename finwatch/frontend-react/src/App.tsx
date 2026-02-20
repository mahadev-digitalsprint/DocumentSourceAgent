import { useState } from 'react'
import { QuickIntakePage } from './modules/simple/QuickIntakePage'
import { CompanyRunsPage } from './modules/simple/CompanyRunsPage'
import { DownloadsPage } from './modules/simple/DownloadsPage'

type SimpleTab = 'INTAKE' | 'RUNS' | 'DOWNLOADS'

const TABS: Array<{ id: SimpleTab; label: string; hint: string }> = [
  { id: 'INTAKE', label: 'Add + Run', hint: 'Create company and fetch docs now' },
  { id: 'RUNS', label: 'Run Control', hint: 'Run one/all companies quickly' },
  { id: 'DOWNLOADS', label: 'Downloads', hint: 'Quarterly/Yearly files and folders' },
]

function tabStyle(active: boolean) {
  return `rounded-lg border px-3 py-2 text-left transition ${
    active
      ? 'border-accent/70 bg-accent/20 text-accent'
      : 'border-slate-700 bg-slate-900/50 text-slate-200 hover:border-slate-500 hover:bg-slate-800/70'
  }`
}

export default function App() {
  const [tab, setTab] = useState<SimpleTab>('INTAKE')
  const active = TABS.find((item) => item.id === tab) ?? TABS[0]

  return (
    <div className="mx-auto min-h-screen max-w-[1500px] px-4 py-4 md:px-6">
      <header className="mb-4 rounded-2xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
        <p className="text-xs uppercase tracking-widest text-cyan-300">FinWatch</p>
        <h1 className="mt-1 text-2xl font-semibold text-slate-50">Document Fetch Console</h1>
        <p className="mt-1 text-sm text-slate-300">
          Simple workflow: add company URL, run pipeline, then view downloaded quarterly/yearly documents.
        </p>
      </header>

      <nav className="mb-4 grid gap-2 md:grid-cols-3">
        {TABS.map((item) => (
          <button key={item.id} className={tabStyle(tab === item.id)} onClick={() => setTab(item.id)} type="button">
            <p className="text-sm font-semibold">{item.label}</p>
            <p className="text-xs text-slate-400">{item.hint}</p>
          </button>
        ))}
      </nav>

      <section className="mb-4 rounded-xl border border-slate-700/70 bg-slate-900/50 px-3 py-2 text-sm text-slate-300">
        Active page: <span className="font-semibold text-slate-100">{active.label}</span> - {active.hint}
      </section>

      {tab === 'INTAKE' ? <QuickIntakePage /> : null}
      {tab === 'RUNS' ? <CompanyRunsPage /> : null}
      {tab === 'DOWNLOADS' ? <DownloadsPage /> : null}
    </div>
  )
}
