import { Suspense, lazy, useEffect, useState } from 'react'

const DashboardPage = lazy(() => import('./modules/dashboard/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const CompanyManagerPage = lazy(() => import('./modules/companies/CompanyManagerPage').then((m) => ({ default: m.CompanyManagerPage })))
const JobsMonitorPage = lazy(() => import('./modules/jobs/JobsMonitorPage').then((m) => ({ default: m.JobsMonitorPage })))
const DocumentExplorerPage = lazy(() =>
  import('./modules/documents/DocumentExplorerPage').then((m) => ({ default: m.DocumentExplorerPage })),
)
const WebWatcherPage = lazy(() => import('./modules/webwatch/WebWatcherPage').then((m) => ({ default: m.WebWatcherPage })))
const MetadataIntelligencePage = lazy(() =>
  import('./modules/metadata/MetadataIntelligencePage').then((m) => ({ default: m.MetadataIntelligencePage })),
)
const AnalyticsPage = lazy(() => import('./modules/analytics/AnalyticsPage').then((m) => ({ default: m.AnalyticsPage })))
const ChangesCenterPage = lazy(() => import('./modules/changes/ChangesCenterPage').then((m) => ({ default: m.ChangesCenterPage })))
const EmailAlertsPage = lazy(() => import('./modules/alerts/EmailAlertsPage').then((m) => ({ default: m.EmailAlertsPage })))
const SystemSettingsPage = lazy(() => import('./modules/settings/SystemSettingsPage').then((m) => ({ default: m.SystemSettingsPage })))
const CrawlerOpsPage = lazy(() => import('./modules/crawler/CrawlerOpsPage').then((m) => ({ default: m.CrawlerOpsPage })))
const SourceIntelligencePage = lazy(() =>
  import('./modules/sources/SourceIntelligencePage').then((m) => ({ default: m.SourceIntelligencePage })),
)

type AppModule =
  | 'DASHBOARD'
  | 'COMPANIES'
  | 'JOBS'
  | 'DOCUMENTS'
  | 'WEBWATCH'
  | 'METADATA'
  | 'ANALYTICS'
  | 'CHANGES'
  | 'ALERTS'
  | 'SETTINGS'
  | 'CRAWLER'
  | 'SOURCES'

type ModuleGroup = 'Operations' | 'Intelligence' | 'Platform'

type ModuleSpec = {
  id: AppModule
  label: string
  group: ModuleGroup
  hint: string
}

const MODULES: ModuleSpec[] = [
  { id: 'DASHBOARD', label: 'Dashboard', group: 'Operations', hint: 'Live KPIs and status' },
  { id: 'COMPANIES', label: 'Companies', group: 'Operations', hint: 'Manage tracked entities' },
  { id: 'JOBS', label: 'Jobs Monitor', group: 'Operations', hint: 'Queue/direct runs and scheduler' },
  { id: 'CRAWLER', label: 'Crawler Ops', group: 'Operations', hint: 'Diagnostics and cooldown control' },
  { id: 'DOCUMENTS', label: 'Documents', group: 'Intelligence', hint: 'Search and inspect files' },
  { id: 'METADATA', label: 'Metadata', group: 'Intelligence', hint: 'Classifier outputs and review queue' },
  { id: 'WEBWATCH', label: 'Web Watcher', group: 'Intelligence', hint: 'Website diff tracking' },
  { id: 'SOURCES', label: 'Source Intel', group: 'Intelligence', hint: 'Domain yield and dead-letter queue' },
  { id: 'ANALYTICS', label: 'Analytics', group: 'Intelligence', hint: 'Trends and operational metrics' },
  { id: 'CHANGES', label: 'Changes', group: 'Intelligence', hint: 'Document/page change center' },
  { id: 'ALERTS', label: 'Email Alerts', group: 'Platform', hint: 'Receiver-only notifications' },
  { id: 'SETTINGS', label: 'Settings', group: 'Platform', hint: 'Runtime and health checks' },
]

const MODULE_GROUPS: ModuleGroup[] = ['Operations', 'Intelligence', 'Platform']

const MODULE_BY_ID = MODULES.reduce<Record<AppModule, ModuleSpec>>((acc, item) => {
  acc[item.id] = item
  return acc
}, {} as Record<AppModule, ModuleSpec>)

function renderModule(module: AppModule) {
  switch (module) {
    case 'DASHBOARD':
      return <DashboardPage />
    case 'COMPANIES':
      return <CompanyManagerPage />
    case 'JOBS':
      return <JobsMonitorPage />
    case 'DOCUMENTS':
      return <DocumentExplorerPage />
    case 'WEBWATCH':
      return <WebWatcherPage />
    case 'METADATA':
      return <MetadataIntelligencePage />
    case 'ANALYTICS':
      return <AnalyticsPage />
    case 'CHANGES':
      return <ChangesCenterPage />
    case 'ALERTS':
      return <EmailAlertsPage />
    case 'SETTINGS':
      return <SystemSettingsPage />
    case 'CRAWLER':
      return <CrawlerOpsPage />
    case 'SOURCES':
      return <SourceIntelligencePage />
  }
}

export default function App() {
  const [module, setModule] = useState<AppModule>(() => {
    const fromStorage = window.localStorage.getItem('finwatch.activeModule')
    const valid = MODULES.find((item) => item.id === fromStorage)
    return (valid?.id as AppModule) ?? 'DASHBOARD'
  })
  const activeSpec = MODULE_BY_ID[module]

  useEffect(() => {
    window.localStorage.setItem('finwatch.activeModule', module)
  }, [module])

  const navButtonClass = (isActive: boolean) =>
    `w-full rounded-lg border px-3 py-2 text-left transition ${
      isActive
        ? 'border-accent/70 bg-accent/15 text-accent'
        : 'border-slate-700/70 bg-slate-900/35 text-slate-200 hover:border-slate-500 hover:bg-slate-800/70'
    }`

  return (
    <div className="mx-auto flex min-h-screen max-w-[1600px] gap-4 px-4 py-4 md:px-6">
      <aside className="hidden w-72 shrink-0 md:block">
        <div className="sticky top-4 rounded-2xl border border-slate-700/70 bg-panel/80 p-4 shadow-panel">
          <div className="mb-4 border-b border-slate-700/70 pb-4">
            <p className="text-xs uppercase tracking-widest text-cyan-300">FinWatch</p>
            <h1 className="mt-2 text-xl font-semibold text-slate-50">Document Intelligence Console</h1>
          </div>
          <div className="space-y-4">
            {MODULE_GROUPS.map((group) => (
              <div key={group}>
                <p className="mb-2 text-xs uppercase tracking-widest text-slate-400">{group}</p>
                <div className="space-y-2">
                  {MODULES.filter((item) => item.group === group).map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setModule(item.id)}
                      className={navButtonClass(module === item.id)}
                    >
                      <p className="text-sm font-semibold">{item.label}</p>
                      <p className="text-xs text-slate-400">{item.hint}</p>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </aside>

      <div className="flex-1">
        <header className="mb-4 rounded-2xl border border-slate-700/70 bg-panel/80 p-4 shadow-panel">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-widest text-cyan-300">{activeSpec.group}</p>
              <h2 className="mt-1 text-2xl font-semibold text-slate-50">{activeSpec.label}</h2>
              <p className="mt-1 text-sm text-slate-300">{activeSpec.hint}</p>
            </div>
            <p className="rounded-md border border-slate-700/70 bg-slate-900/40 px-3 py-1 text-xs text-slate-400">
              {new Date().toISOString().replace('T', ' ').slice(0, 16)} UTC
            </p>
          </div>
          <div className="mt-4 flex gap-2 overflow-x-auto pb-1 md:hidden">
            {MODULES.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setModule(item.id)}
                className={`whitespace-nowrap rounded-md border px-3 py-1 text-xs font-semibold ${
                  module === item.id
                    ? 'border-accent/70 bg-accent text-slate-950'
                    : 'border-slate-700 bg-slate-900/50 text-slate-200'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </header>

        <Suspense
          fallback={
            <div className="rounded-2xl border border-slate-700/70 bg-panel/70 px-4 py-8 text-sm text-slate-300">
              Loading module...
            </div>
          }
        >
          {renderModule(module)}
        </Suspense>
      </div>
    </div>
  )
}
