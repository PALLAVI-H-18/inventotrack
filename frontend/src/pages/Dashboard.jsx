// ------------------------------------------------------------------
// Dashboard.jsx (Oct 6 + Oct 8) - stat cards + low-stock list + expiry alerts.
// The owner also sees money values. Staff cannot call /dashboard/summary
// (the backend returns 403), so we only call it for the owner.
// ------------------------------------------------------------------
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../AuthContext.jsx'
import { api } from '../api.js'
import { Alert, Card, PageHeader, Spinner, StatCard, StatusBadge, formatINR } from '../components/ui.jsx'

// days_left -> colour (red = urgent, amber = soon, green = fine)
function DaysBadge({ days }) {
  let cls = 'bg-green-100 text-green-800'
  if (days <= 7) cls = 'bg-red-100 text-red-800'
  else if (days <= 14) cls = 'bg-amber-100 text-amber-800'
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${cls}`}>
      {days === 0 ? 'Expires today' : `${days} day${days === 1 ? '' : 's'} left`}
    </span>
  )
}

export default function Dashboard() {
  const { user, isOwner } = useAuth()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const calls = [api('/products'), api('/dashboard/expiring'), api('/notifications?status=open')]
        if (isOwner) calls.push(api('/dashboard/summary'), api('/suggestions'))
        const [products, expiring, openAlerts, summary, restock] = await Promise.all(calls)
        if (!cancelled) setData({ products, expiring, openAlerts, summary: summary || null, restock: restock?.summary || null })
      } catch (err) {
        if (!cancelled) setError(err.message)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [isOwner])

  if (error) return <Alert type="error">{error}</Alert>
  if (!data) return <Spinner label="Loading dashboard..." />

  const { products, expiring, openAlerts, summary, restock } = data
  const count = (status) => products.filter((p) => p.status === status).length
  const needAttention = products.filter((p) => p.status !== 'healthy')

  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" subtitle={`Welcome back, ${user.name}. Here is your shop today.`} />

      {!isOwner && openAlerts.length > 0 && (
        <Alert type="warning" title={`${openAlerts.length} product(s) the owner wants you to bring to the shop`}>
          {openAlerts.slice(0, 3).map((n) => n.product_name).join(', ')}
          {openAlerts.length > 3 ? '...' : ''}{' '}
          <Link to="/alerts" className="font-semibold underline">
            Open alerts
          </Link>
        </Alert>
      )}

      {isOwner && needAttention.length > 0 && (
        <Alert type="error" title={`${count('out_of_stock')} out of stock, ${count('low_stock')} low stock`}>
          <Link to="/alerts" className="font-semibold underline">
            Send an alert to staff so they bring these to the shop
          </Link>
        </Alert>
      )}

      {isOwner && restock && restock.order_now + restock.order_soon > 0 && (
        <Alert type="warning" title={`${restock.order_now + restock.order_soon} product(s) need restocking`}>
          {restock.order_now} to order now, {restock.order_soon} soon ({restock.total_units_to_order} units in total).{' '}
          <Link to="/suggestions" className="font-semibold underline">
            See what to order and why
          </Link>
        </Alert>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Total products" value={products.length} />
        <StatCard label="Healthy" value={count('healthy')} tone="green" />
        <StatCard label="Low stock" value={count('low_stock')} tone="amber" />
        <StatCard label="Out of stock" value={count('out_of_stock')} tone="red" />
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Expiring in 30 days" value={expiring.length} tone="amber" hint="batches" />
        {isOwner && summary && (
          <>
            <StatCard label="Inventory value" value={formatINR(summary.total_inventory_value)} tone="brand" hint="sellable stock" />
            <StatCard label="Expired stock" value={summary.expired_batch_count} tone="red" hint="batches still on shelf" />
            <StatCard label="Value lost to expiry" value={formatINR(summary.expired_stock_value)} tone="red" />
          </>
        )}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card title="Needs attention (low or out of stock)">
          {needAttention.length === 0 ? (
            <p className="text-sm text-slate-500">All products are healthy. 🎉</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {needAttention.map((p) => (
                <li key={p.product_id} className="flex items-center justify-between gap-3 py-2.5">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{p.name}</p>
                    <p className="text-xs text-slate-500">
                      {p.total_quantity} in stock (minimum {p.min_stock_level})
                    </p>
                  </div>
                  <StatusBadge status={p.status} />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Expiry alerts (next 30 days)">
          {expiring.length === 0 ? (
            <p className="text-sm text-slate-500">No batches are about to expire.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {expiring.map((b) => (
                <li key={b.batch_id} className="flex items-center justify-between gap-3 py-2.5">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{b.product_name}</p>
                    <p className="text-xs text-slate-500">
                      Batch {b.batch_no} - {b.quantity_remaining} units - expires {b.expiry_date}
                    </p>
                  </div>
                  <DaysBadge days={b.days_left} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
