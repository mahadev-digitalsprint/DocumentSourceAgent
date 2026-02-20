import { Suspense, lazy, useState } from 'react'

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
  }
}

export default function App() {
  const [module, setModule] = useState<AppModule>('DASHBOARD')

  return (
    <div>
      <nav className="sticky top-0 z-20 border-b border-slate-700/70 bg-bg/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-2 px-4 py-3 md:px-8">
          <button
            onClick={() => setModule('DASHBOARD')}
            className={`rounded-md px-3 py-1 text-sm font-semibold ${
              module === 'DASHBOARD' ? 'bg-accent text-slate-950' : 'bg-slate-800 text-slate-200'
            }`}
          >
            Dashboard
          </button>
          <button
            onClick={() => setModule('COMPANIES')}
            className={`rounded-md px-3 py-1 text-sm font-semibold ${
              module === 'COMPANIES' ? 'bg-accent text-slate-950' : 'bg-slate-800 text-slate-200'
            }`}
          >
            Company Manager
          </button>
          <button
            onClick={() => setModule('JOBS')}
            className={`rounded-md px-3 py-1 text-sm font-semibold ${
              module === 'JOBS' ? 'bg-accent text-slate-950' : 'bg-slate-800 text-slate-200'
            }`}
          >
            Jobs Monitor
          </button>
          <button
            onClick={() => setModule('DOCUMENTS')}
            className={`rounded-md px-3 py-1 text-sm font-semibold ${
              module === 'DOCUMENTS' ? 'bg-accent text-slate-950' : 'bg-slate-800 text-slate-200'
            }`}
          >
            Documents
          </button>
          <button
            onClick={() => setModule('WEBWATCH')}
            className={`rounded-md px-3 py-1 text-sm font-semibold ${
              module === 'WEBWATCH' ? 'bg-accent text-slate-950' : 'bg-slate-800 text-slate-200'
            }`}
          >
            Web Watcher
          </button>
          <button
            onClick={() => setModule('METADATA')}
            className={`rounded-md px-3 py-1 text-sm font-semibold ${
              module === 'METADATA' ? 'bg-accent text-slate-950' : 'bg-slate-800 text-slate-200'
            }`}
          >
            Metadata
          </button>
          <button
            onClick={() => setModule('ANALYTICS')}
            className={`rounded-md px-3 py-1 text-sm font-semibold ${
              module === 'ANALYTICS' ? 'bg-accent text-slate-950' : 'bg-slate-800 text-slate-200'
            }`}
          >
            Analytics
          </button>
          <button
            onClick={() => setModule('CHANGES')}
            className={`rounded-md px-3 py-1 text-sm font-semibold ${
              module === 'CHANGES' ? 'bg-accent text-slate-950' : 'bg-slate-800 text-slate-200'
            }`}
          >
            Changes
          </button>
          <button
            onClick={() => setModule('ALERTS')}
            className={`rounded-md px-3 py-1 text-sm font-semibold ${
              module === 'ALERTS' ? 'bg-accent text-slate-950' : 'bg-slate-800 text-slate-200'
            }`}
          >
            Email Alerts
          </button>
          <button
            onClick={() => setModule('SETTINGS')}
            className={`rounded-md px-3 py-1 text-sm font-semibold ${
              module === 'SETTINGS' ? 'bg-accent text-slate-950' : 'bg-slate-800 text-slate-200'
            }`}
          >
            Settings
          </button>
          <button
            onClick={() => setModule('CRAWLER')}
            className={`rounded-md px-3 py-1 text-sm font-semibold ${
              module === 'CRAWLER' ? 'bg-accent text-slate-950' : 'bg-slate-800 text-slate-200'
            }`}
          >
            Crawler Ops
          </button>
        </div>
      </nav>

      <Suspense
        fallback={
          <div className="mx-auto max-w-7xl px-4 py-8 text-sm text-slate-400 md:px-8">
            Loading module...
          </div>
        }
      >
        {renderModule(module)}
      </Suspense>
    </div>
  )
}
