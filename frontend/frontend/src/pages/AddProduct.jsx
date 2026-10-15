// ------------------------------------------------------------------
// AddProduct.jsx (Oct 4) - owner-only form. If the backend finds the name in the
// restricted list it sends back "restricted_match" + "warning", which we show.
// ------------------------------------------------------------------
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { parseNewProductQr, parseQr } from '../qr.js'
import QrScanner from '../components/QrScanner.jsx'
import { Alert, Button, Card, Field, PageHeader, inputClass } from '../components/ui.jsx'

const CATEGORIES = ['Insecticide', 'Fungicide', 'Herbicide', 'Bio-pesticide', 'Other']
const SEASONS = ['Kharif', 'Rabi', 'Monsoon', 'Year-round']
const EMPTY = { name: '', brand: '', category: 'Insecticide', season: 'Year-round', min_stock_level: '10' }

export default function AddProduct() {
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState('')
  const [result, setResult] = useState(null)
  const [saving, setSaving] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [scanMsg, setScanMsg] = useState(null)

  // one small helper updates any field:  onChange={set('brand')}
  const set = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  // Scanning a "new product" QR fills the form; the owner checks it and presses Add product.
  function handleScan(text) {
    setScanning(false)
    setResult(null)
    setApiError('')
    const info = parseNewProductQr(text)
    if (info) {
      setForm({
        name: info.name,
        brand: info.brand,
        category: CATEGORIES.includes(info.category) ? info.category : EMPTY.category,
        season: SEASONS.includes(info.season) ? info.season : EMPTY.season,
        min_stock_level: /^\d+$/.test(info.min_stock_level) ? info.min_stock_level : EMPTY.min_stock_level,
      })
      setErrors({})
      setScanMsg({ type: 'success', text: `Scanned "${info.name}". Check the details below, then press Add product.` })
    } else if (/^INVENTO:/i.test(String(text).trim()) && parseQr(text)) {
      setScanMsg({ type: 'warning', text: 'This is the QR of a product already in the shop. Use Add Stock to add a batch for it.' })
    } else {
      setScanMsg({ type: 'error', text: 'This is not an InventoTrack new-product QR. Create one on the QR Labels page.' })
    }
  }

  function validate() {
    const found = {}
    if (!form.name.trim()) found.name = 'Product name is required'
    const min = Number(form.min_stock_level)
    if (form.min_stock_level === '' || !Number.isInteger(min) || min < 0) {
      found.min_stock_level = 'Enter a whole number, 0 or more'
    }
    return found
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setApiError('')
    setResult(null)
    const found = validate()
    setErrors(found)
    if (Object.keys(found).length > 0) return

    setSaving(true)
    try {
      const data = await api('/products', {
        method: 'POST',
        body: {
          name: form.name.trim(),
          brand: form.brand.trim(),
          category: form.category,
          season: form.season,
          min_stock_level: Number(form.min_stock_level),
        },
      })
      setResult({ ...data, name: form.name.trim() })
      setForm(EMPTY)
      setScanMsg(null)
    } catch (err) {
      setApiError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-2xl">
      <PageHeader
        title="Add product"
        subtitle="Register a new pesticide. It is checked against the restricted list automatically."
      />

      <div className="mb-4 space-y-3">
        {apiError && <Alert type="error">{apiError}</Alert>}
        {scanMsg && <Alert type={scanMsg.type}>{scanMsg.text}</Alert>}

        {result && result.is_restricted && (
          <Alert type="warning" title={`Restricted pesticide detected: ${result.name}`}>
            <p>
              Matches <strong>{result.restricted_match}</strong> ({result.restricted_reason}).
            </p>
            <p className="mt-1">{result.warning}</p>
            <p className="mt-1">
              Next step: <Link className="underline" to="/add-stock">add stock for it</Link>.
            </p>
          </Alert>
        )}

        {result && !result.is_restricted && (
          <Alert type="success" title={`"${result.name}" added`}>
            It is not on the restricted list. Next step:{' '}
            <Link className="underline" to="/add-stock">add stock for it</Link>.
          </Alert>
        )}
      </div>

      {scanning && (
        <div className="mb-4">
          <QrScanner onScan={handleScan} onClose={() => setScanning(false)} />
        </div>
      )}

      <Card>
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <Button type="button" variant="secondary" onClick={() => { setScanMsg(null); setScanning(true) }}>
            📷 Scan new-product QR
          </Button>
          <Field label="Product name *" htmlFor="name" error={errors.name} hint="Example: Chlorpyrifos 20% EC">
            <input id="name" className={inputClass} value={form.name} onChange={set('name')} />
          </Field>

          <Field label="Brand" htmlFor="brand">
            <input id="brand" className={inputClass} value={form.brand} onChange={set('brand')} />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Category" htmlFor="category">
              <select id="category" className={inputClass} value={form.category} onChange={set('category')}>
                {CATEGORIES.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </Field>
            <Field label="Season" htmlFor="season" hint="Used later for seasonal restock suggestions">
              <select id="season" className={inputClass} value={form.season} onChange={set('season')}>
                {SEASONS.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </Field>
          </div>

          <Field
            label="Minimum stock level"
            htmlFor="min_stock_level"
            error={errors.min_stock_level}
            hint="Below this number the product shows as Low stock"
          >
            <input
              id="min_stock_level"
              type="number"
              min="0"
              className={inputClass}
              value={form.min_stock_level}
              onChange={set('min_stock_level')}
            />
          </Field>

          <Button type="submit" disabled={saving}>
            {saving ? 'Saving...' : 'Add product'}
          </Button>
        </form>
      </Card>
    </div>
  )
}
