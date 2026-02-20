import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

type Props = {
  financial: number
  nonFinancial: number
  unknown: number
}

export function DocCategoryChart({ financial, nonFinancial, unknown }: Props) {
  const data = [
    { category: 'Financial', count: financial },
    { category: 'Non-Financial', count: nonFinancial },
    { category: 'Unknown', count: unknown },
  ]

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f3344" />
          <XAxis dataKey="category" stroke="#8ca2b7" />
          <YAxis stroke="#8ca2b7" allowDecimals={false} />
          <Tooltip />
          <Bar dataKey="count" fill="#00b894" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
