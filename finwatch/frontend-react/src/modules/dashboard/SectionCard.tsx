import type { PropsWithChildren, ReactNode } from 'react'

type Props = PropsWithChildren<{
  title: string
  subtitle?: string
  action?: ReactNode
}>

export function SectionCard({ title, subtitle, action, children }: Props) {
  return (
    <section className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
      <header className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
          {subtitle ? <p className="text-sm text-slate-400">{subtitle}</p> : null}
        </div>
        {action}
      </header>
      {children}
    </section>
  )
}
