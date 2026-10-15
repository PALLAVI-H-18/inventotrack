// ------------------------------------------------------------------
// Reports.jsx (Oct 15) - owner-only Excel downloads: inventory, sales, compliance log.
// ------------------------------------------------------------------
import { useState } from 'react'
import { download } from '../api.js'
import { Alert, Button, Card, Field, PageHeader, inputClass } from '../components/ui.jsx'

export default function Reports() {
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [busy, setBusy] = useState('') // which report is being prepared
  const [message, setMessage] = useState(null) // { type, text }

  async function get(key, path, name) {
    setBusy(key)
    setMessage(null)
    try {
      const saved = await download(path, name)
      setMessage({ type: 'success', text: `Downloaded ${saved}. Open it in Excel.` })
    } catch (err) {
      setMessage({ type: 'error', text: err.message })
    } finally {
      setBusy('')
    }
  }

  const range = new URLSearchParams()
  if (from) range.set('from', from)
  if (to) range.set('to', to)
  const rangeText = range.toString() ? `?${range.toString()}` : ''

  return (
    <div className="space-y-6">
      <PageHeader title="Reports" subtitle="Download your data as Excel files." />

      {message && <Alert type={message.type}>{message.text}</Alert>}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Inventory">
          <p className="mb-4 text-sm text-slate-600">
            All products and every batch with stock value. Expired batches are red, batches expiring within 30 days are amber.
          </p>
          <Button onClick={() => get('inv', '/reports/inventory/export', 'inventory.xlsx')} disabled={busy !== ''}>
            {busy === 'inv' ? 'Preparing...' : 'Download inventory'}
          </Button>
        </Card>

        <Card title="Sales">
          <p className="mb-4 text-sm text-slate-600">Every sale with the batch it came from. Use the dates below to limit it.</p>
          <Button onClick={() => get('sales', `/reports/sales/export${rangeText}`, 'sales.xlsx')} disabled={busy !== ''}>
            {busy === 'sales' ? 'Preparing...' : 'Download sales'}
          </Button>
        </Card>

        <Card title="Compliance log">
          <p className="mb-4 text-sm text-slate-600">Restricted pesticide sales with buyer IDs. Missing IDs are red.</p>
          <Button onClick={() => get('comp', `/reports/compliance/export${rangeText}`, 'compliance_log.xlsx')} disabled={busy !== ''}>
            {busy === 'comp' ? 'Preparing...' : 'Download compliance log'}
          </Button>
        </Card>
      </div>

      <Card title="Date range (for the sales and compliance reports)">
        <div className="flex flex-wrap items-end gap-4">
          <Field label="From" htmlFor="rfrom">
            <input id="rfrom" type="date" className={inputClass} value={from} onChange={(e) => setFrom(e.target.value)} />
          </Field>
          <Field label="To" htmlFor="rto">
            <input id="rto" type="date" className={inputClass} value={to} onChange={(e) => setTo(e.target.value)} />
          </Field>
          <Button variant="secondary" onClick={() => { setFrom(''); setTo('') }}>
            All dates
          </Button>
        </div>
      </Card>
    </div>
  )
}
