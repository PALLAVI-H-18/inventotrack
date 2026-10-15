// ------------------------------------------------------------------
// Alerts.jsx - restock alerts.
//  OWNER: sees every low / out-of-stock product, can send an alert to staff, and sees which alerts
//         are still open or already done.
//  STAFF: sees the alerts the owner sent ("bring this product to the shop") and marks them done.
// ------------------------------------------------------------------
import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../AuthContext.jsx'
import { api } from '../api.js'
import { Alert, Button, Card, PageHeader, Spinner, StatusBadge, inputClass } from '../components/ui.jsx'

function when(text) {
  return text ? text.slice(0, 16).replace('T', ' ') : ''
}

function AlertCard({ n, canFinish, onFinish, onRemove, busy }) {
  const done = n.status === 'done'
  return (
    <div className={`rounded-xl border p-4 ${done ? 'border-slate-200 bg-slate-50' : 'border-amber-300 bg-amber-50'}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-slate-900">{n.product_name}</p>
          <p className="mt-1 text-sm text-slate-700">{n.message}</p>
        </div>
        <StatusBadge status={n.stock_status} />
      </div>
      <p className="mt-2 text-xs text-slate-500">
        In stock now: <strong>{n.current_stock}</strong> · Sent by {n.created_by_name || 'owner'} on {when(n.created_at)}
        {done && ` · Done by ${n.done_by_name || 'staff'} on ${when(n.done_at)}`}
      </p>
      {done && onRemove && (
        <div className="mt-3">
          <Button variant="secondary" onClick={() => onRemove(n.notification_id)} disabled={busy}>
            🗑️ Remove
          </Button>
        </div>
      )}
      {canFinish && !done && (
        <div className="mt-3">
          <Button onClick={() => onFinish(n.notification_id)} disabled={busy}>
            ✓ Brought to the shop
          </Button>
        </div>
      )}
    </div>
  )
}

export default function Alerts() {
  const { isOwner } = useAuth()
  const [products, setProducts] = useState(null)
  const [alerts, setAlerts] = useState(null)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [notes, setNotes] = useState({})
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const [p, a] = await Promise.all([api('/products'), api('/notifications')])
      setProducts(p)
      setAlerts(a)
    } catch (err) {
      setError(err.message)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function send(product) {
    setError('')
    setInfo('')
    setBusy(true)
    try {
      await api('/notifications', {
        method: 'POST',
        body: { product_id: product.product_id, message: (notes[product.product_id] || '').trim() },
      })
      setInfo(`Alert sent to staff for ${product.name}.`)
      setNotes({ ...notes, [product.product_id]: '' })
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function finish(id) {
    setError('')
    setInfo('')
    setBusy(true)
    try {
      await api(`/notifications/${id}/done`, { method: 'POST' })
      setInfo('Marked as done. The owner can now see it.')
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function remove(id) {
    setError('')
    setInfo('')
    setBusy(true)
    try {
      await api(`/notifications/${id}`, { method: 'DELETE' })
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function clearDone() {
    setError('')
    setInfo('')
    setBusy(true)
    try {
      const data = await api('/notifications/done', { method: 'DELETE' })
      setInfo(`Removed ${data.removed} finished alert(s).`)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (!alerts && !error) return <Spinner label="Loading alerts..." />

  const open = (alerts || []).filter((n) => n.status === 'open')
  const done = (alerts || []).filter((n) => n.status === 'done')
  const openIds = new Set(open.map((n) => n.product_id))
  const needAttention = (products || [])
    .filter((p) => p.status !== 'healthy')
    .sort((a, b) => (a.status === 'out_of_stock' ? -1 : 1) - (b.status === 'out_of_stock' ? -1 : 1))

  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader
        title="Alerts"
        subtitle={
          isOwner
            ? 'Low and out-of-stock products. Send an alert so staff bring them to the shop.'
            : 'Products the owner wants you to bring to the shop.'
        }
      />
      {error && <Alert type="error">{error}</Alert>}
      {info && <Alert type="success">{info}</Alert>}

      {isOwner && (
        <Card title={`Needs attention (${needAttention.length})`}>
          {needAttention.length === 0 ? (
            <p className="text-sm text-slate-500">All products are healthy. Nothing to send.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {needAttention.map((p) => (
                <li key={p.product_id} className="flex flex-wrap items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-slate-900">{p.name}</p>
                    <p className="text-xs text-slate-500">
                      {p.total_quantity} left (minimum {p.min_stock_level})
                    </p>
                  </div>
                  <StatusBadge status={p.status} />
                  {openIds.has(p.product_id) ? (
                    <span className="text-xs font-semibold text-amber-700">Alert already sent</span>
                  ) : (
                    <>
                      <input
                        className={`${inputClass} sm:w-48`}
                        placeholder="Note (optional)"
                        aria-label={`Note for ${p.name}`}
                        value={notes[p.product_id] || ''}
                        onChange={(e) => setNotes({ ...notes, [p.product_id]: e.target.value })}
                      />
                      <Button onClick={() => send(p)} disabled={busy}>
                        🔔 Alert staff
                      </Button>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      <div>
        <h2 className="mb-3 text-lg font-semibold text-slate-800">
          {isOwner ? `Sent to staff - waiting (${open.length})` : `To bring to the shop (${open.length})`}
        </h2>
        {open.length === 0 ? (
          <p className="text-sm text-slate-500">{isOwner ? 'No open alerts.' : 'Nothing pending. You are all caught up.'}</p>
        ) : (
          <div className="space-y-3">
            {open.map((n) => (
              <AlertCard key={n.notification_id} n={n} canFinish onFinish={finish} busy={busy} />
            ))}
          </div>
        )}
      </div>

      {done.length > 0 && (
        <div>
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="text-lg font-semibold text-slate-800">Done ({done.length})</h2>
            <Button variant="secondary" onClick={clearDone} disabled={busy}>
              🗑️ Clear all done
            </Button>
          </div>
          <div className="space-y-3">
            {done.slice(0, 10).map((n) => (
              <AlertCard key={n.notification_id} n={n} onRemove={remove} busy={busy} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
