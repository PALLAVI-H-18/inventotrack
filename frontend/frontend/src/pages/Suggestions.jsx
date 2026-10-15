// ------------------------------------------------------------------
// Suggestions.jsx (Oct 14) - owner-only restock advice WITH the reason ("why").
//   target stock   = predicted demand next month + minimum stock level
//   order quantity = target stock - usable stock now (never below 0)
// ------------------------------------------------------------------
import { Fragment, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { Alert, Button, Card, PageHeader, PriorityBadge, Spinner, StatCard } from '../components/ui.jsx'

export default function Suggestions() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [onlyNeeded, setOnlyNeeded] = useState(true)
  const [openId, setOpenId] = useState(null) // which row shows its "why"

  useEffect(() => {
    let cancelled = false
    api('/suggestions')
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [])

  const rows = useMemo(() => {
    if (!data) return []
    return onlyNeeded ? data.suggestions.filter((s) => s.recommended_order > 0) : data.suggestions
  }, [data, onlyNeeded])

  if (error) return <Alert type="error">{error}</Alert>
  if (!data) return <Spinner label="Working out restock advice..." />
  const { summary } = data

  return (
    <div className="space-y-6">
      <PageHeader
        title="Restock suggestions"
        subtitle="How much to order next month, and why. Click a row to read the reasoning."
        action={
          <Link to="/add-stock">
            <Button>Add stock</Button>
          </Link>
        }
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Order now" value={summary.order_now} tone="red" hint="products" />
        <StatCard label="Order soon" value={summary.order_soon} tone="amber" hint="products" />
        <StatCard label="Stock is fine" value={summary.ok} tone="green" hint="products" />
        <StatCard label="Units to order" value={summary.total_units_to_order} tone="brand" hint="in total" />
      </div>

      <Alert type="info">
        <strong>Rule:</strong> order = (predicted demand + minimum stock) - usable stock. Expired batches are not counted
        as stock. With fewer than 8 months of sales the simple rule 2 x minimum stock is used instead.
      </Alert>

      <Card>
        <label className="mb-4 flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={onlyNeeded} onChange={(e) => setOnlyNeeded(e.target.checked)} />
          Show only products that need ordering
        </label>

        {rows.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">Nothing to order right now. 🎉</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2 pr-3">Product</th>
                  <th className="px-3">Season</th>
                  <th className="px-3 text-right">In stock</th>
                  <th className="px-3 text-right">Expected demand</th>
                  <th className="px-3 text-right">Target</th>
                  <th className="px-3 text-right">Order</th>
                  <th className="pl-3">Priority</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <Fragment key={s.product_id}>
                    <tr
                      className="cursor-pointer border-b border-slate-100 hover:bg-slate-50"
                      onClick={() => setOpenId(openId === s.product_id ? null : s.product_id)}
                    >
                      <td className="py-2.5 pr-3 font-medium text-slate-800">
                        {s.product_name}
                        {s.is_restricted && <span className="ml-2 text-xs text-amber-700">restricted</span>}
                      </td>
                      <td className="px-3 text-slate-600">{s.season}</td>
                      <td className="px-3 text-right">{s.current_stock}</td>
                      <td className="px-3 text-right">{s.predicted_demand ?? '-'}</td>
                      <td className="px-3 text-right">{s.target_stock}</td>
                      <td className="px-3 text-right font-semibold">{s.recommended_order}</td>
                      <td className="pl-3">
                        <PriorityBadge priority={s.priority} />
                      </td>
                    </tr>
                    {openId === s.product_id && (
                      <tr className="border-b border-slate-100 bg-slate-50">
                        <td colSpan={7} className="px-3 py-3 text-sm text-slate-700">
                          <p className="font-semibold">Why?</p>
                          <p className="mt-1">{s.why}</p>
                          <p className="mt-2 text-xs text-slate-500">
                            Basis: {s.basis === 'forecast' ? `forecast (${s.method})` : 'minimum-stock rule (not enough history)'}
                            {' | '}Min stock: {s.min_stock_level}
                            {' | '}Expiring within 30 days: {s.expiring_within_30_days}
                          </p>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
