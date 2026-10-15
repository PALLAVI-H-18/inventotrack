// ------------------------------------------------------------------
// Compliance.jsx (Oct 11) - owner-only log of every restricted-pesticide sale and the
// buyer ID recorded for it. Sales with no buyer ID are highlighted in red.
// ------------------------------------------------------------------
import { useEffect, useState } from 'react'
import { api, download } from '../api.js'
import { Alert, Button, Card, Field, PageHeader, Spinner, StatCard, inputClass } from '../components/ui.jsx'

function query(from, to, missingOnly) {
  const params = new URLSearchParams()
  if (from) params.set('from', from)
  if (to) params.set('to', to)
  if (missingOnly) params.set('missing_only', 'true')
  const text = params.toString()
  return text ? `?${text}` : ''
}

export default function Compliance() {
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [missingOnly, setMissingOnly] = useState(false)
  const [applied, setApplied] = useState({ from: '', to: '', missingOnly: false })
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [shown, setShown] = useState(50)   // show 50 rows first; "Show more" adds 50

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    api(`/reports/restricted-sales${query(applied.from, applied.to, applied.missingOnly)}`)
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [applied])

  function apply(event) {
    event.preventDefault()
    setShown(50)
    setApplied({ from, to, missingOnly })
  }

  function reset() {
    setFrom('')
    setTo('')
    setMissingOnly(false)
    setApplied({ from: '', to: '', missingOnly: false })
  }

  async function exportExcel() {
    setExporting(true)
    setError('')
    try {
      await download(`/reports/compliance/export${query(applied.from, applied.to, applied.missingOnly)}`, 'compliance_log.xlsx')
    } catch (err) {
      setError(err.message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Compliance log"
        subtitle="Every sale of a restricted pesticide and who bought it."
        action={
          <Button variant="secondary" onClick={exportExcel} disabled={exporting}>
            {exporting ? 'Preparing...' : 'Export to Excel'}
          </Button>
        }
      />

      <Card>
        <form onSubmit={apply} className="flex flex-wrap items-end gap-4">
          <Field label="From" htmlFor="from">
            <input id="from" type="date" className={inputClass} value={from} onChange={(e) => setFrom(e.target.value)} />
          </Field>
          <Field label="To" htmlFor="to">
            <input id="to" type="date" className={inputClass} value={to} onChange={(e) => setTo(e.target.value)} />
          </Field>
          <label className="flex items-center gap-2 pb-2 text-sm text-slate-700">
            <input type="checkbox" checked={missingOnly} onChange={(e) => setMissingOnly(e.target.checked)} />
            Only sales with NO buyer ID
          </label>
          <Button type="submit">Apply</Button>
          <Button type="button" variant="secondary" onClick={reset}>
            Reset
          </Button>
        </form>
      </Card>

      {error && <Alert type="error">{error}</Alert>}
      {loading && <Spinner label="Loading log..." />}

      {data && !loading && (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard label="Restricted sales" value={data.summary.total_records} />
            <StatCard label="Units sold" value={data.summary.total_units} tone="brand" />
            <StatCard label="With buyer ID" value={data.summary.with_buyer_id} tone="green" />
            <StatCard label="Missing buyer ID" value={data.summary.missing_buyer_id} tone={data.summary.missing_buyer_id ? 'red' : 'green'} />
          </div>

          <Card>
            {data.records.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-500">No restricted sales match these filters.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="py-2 pr-3">Date</th>
                      <th className="px-3">Product</th>
                      <th className="px-3">Batch</th>
                      <th className="px-3 text-right">Qty</th>
                      <th className="px-3">Buyer ID</th>
                      <th className="pl-3">Sold by</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.records.slice(0, shown).map((r) => (
                      <tr key={r.sale_id} className={`border-b border-slate-100 ${r.has_buyer_id ? '' : 'bg-red-50'}`}>
                        <td className="py-2.5 pr-3">{r.sale_date}</td>
                        <td className="px-3 font-medium text-slate-800">{r.product_name}</td>
                        <td className="px-3 text-slate-600">{r.batch_no}</td>
                        <td className="px-3 text-right">{r.quantity_sold}</td>
                        <td className="px-3">
                          {r.has_buyer_id ? (
                            r.buyer_id_proof
                          ) : (
                            <span className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-800">MISSING</span>
                          )}
                        </td>
                        <td className="pl-3 text-slate-600">{r.sold_by_name || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {data.records.length > shown && (
              <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
                <span>Showing {shown} of {data.records.length} records (the Excel export has all of them)</span>
                <button type="button" onClick={() => setShown(shown + 50)} className="rounded-lg border border-slate-300 px-3 py-1.5 font-semibold text-slate-700 hover:bg-slate-50">
                  Show 50 more
                </button>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  )
}
