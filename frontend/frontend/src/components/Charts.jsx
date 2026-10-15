// ------------------------------------------------------------------
// Charts.jsx - a small bar chart drawn with plain SVG (no chart library needed).
// Used on the Forecast page: past months in green, the predicted month in amber.
// ------------------------------------------------------------------
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// "2026-03" -> "Mar 26"
function shortMonth(value) {
  const [year, month] = value.split('-')
  return `${MONTHS[Number(month) - 1]} ${year.slice(2)}`
}

export function MonthlyChart({ history, forecastMonth, predicted }) {
  const bars = history.map((h) => ({ label: h.month, value: h.quantity, predicted: false }))
  if (forecastMonth && predicted !== undefined && predicted !== null) {
    bars.push({ label: forecastMonth, value: predicted, predicted: true })
  }
  if (bars.length === 0) return <p className="text-sm text-slate-500">No sales history yet.</p>

  const width = 640
  const height = 260
  const left = 40
  const bottom = 46
  const top = 18
  const plotHeight = height - top - bottom
  const maxValue = Math.max(...bars.map((b) => b.value), 1)
  const slot = (width - left - 10) / bars.length
  const barWidth = Math.min(34, slot * 0.7)
  const ticks = [0, 0.5, 1].map((t) => Math.round(maxValue * t))

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="w-full"
      role="img"
      aria-label={`Units sold per month, with the predicted demand for ${forecastMonth || 'next month'}`}
    >
      {ticks.map((t) => {
        const y = top + plotHeight - (t / maxValue) * plotHeight
        return (
          <g key={t}>
            <line x1={left} x2={width - 10} y1={y} y2={y} stroke="#e2e8f0" />
            <text x={left - 6} y={y + 4} textAnchor="end" fontSize="11" fill="#64748b">
              {t}
            </text>
          </g>
        )
      })}
      {bars.map((b, i) => {
        const h = (b.value / maxValue) * plotHeight
        const x = left + i * slot + (slot - barWidth) / 2
        const y = top + plotHeight - h
        return (
          <g key={b.label}>
            <title>{`${shortMonth(b.label)}: ${b.value} units${b.predicted ? ' (predicted)' : ''}`}</title>
            <rect
              x={x}
              y={y}
              width={barWidth}
              height={Math.max(h, 1)}
              rx="3"
              fill={b.predicted ? '#f59e0b' : '#16a34a'}
              stroke={b.predicted ? '#b45309' : 'none'}
              strokeDasharray={b.predicted ? '4 2' : undefined}
              opacity={b.predicted ? 0.9 : 1}
            />
            <text x={x + barWidth / 2} y={y - 4} textAnchor="middle" fontSize="10" fill="#334155">
              {b.value}
            </text>
            <text
              x={x + barWidth / 2}
              y={height - bottom + 14}
              textAnchor="end"
              fontSize="10"
              fill="#64748b"
              transform={`rotate(-40 ${x + barWidth / 2} ${height - bottom + 14})`}
            >
              {shortMonth(b.label)}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
