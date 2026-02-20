type Props = {
  label: string
  value: string | number
  tone?: 'default' | 'good' | 'warn'
}

export function KpiCard({ label, value, tone = 'default' }: Props) {
  const toneClass =
    tone === 'good'
      ? 'text-accent'
      : tone === 'warn'
      ? 'text-warn'
      : 'text-slate-100'

  return (
    <article className="rounded-xl border border-slate-700/70 bg-panel/90 p-4 shadow-panel">
      <p className="text-xs uppercase tracking-wider text-slate-400">{label}</p>
      <p className={`mt-2 text-3xl font-semibold ${toneClass}`}>{value}</p>
    </article>
  )
}
