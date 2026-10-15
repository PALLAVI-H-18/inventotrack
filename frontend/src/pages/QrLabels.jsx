// ------------------------------------------------------------------
// QrLabels.jsx - owner-only page that makes a printable QR label for every product.
// Stick the label on the shelf/box; scanning it on "Record Sale" selects the product.
// QR content is "INVENTO:<product_id>" (see src/qr.js).
// ------------------------------------------------------------------
import { useEffect, useState } from 'react'
import QRCode from 'qrcode'
import { api } from '../api.js'
import { newProductQrValue, qrValue } from '../qr.js'
import { Alert, Button, Card, Field, PageHeader, Spinner, inputClass } from '../components/ui.jsx'

function Label({ product }) {
  const [src, setSrc] = useState('')
  useEffect(() => {
    let cancelled = false
    QRCode.toDataURL(qrValue(product.product_id), { width: 220, margin: 1 })
      .then((url) => !cancelled && setSrc(url))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [product.product_id])

  return (
    <div className="break-inside-avoid rounded-lg border border-slate-300 bg-white p-3 text-center">
      {src ? <img src={src} alt={`QR code for ${product.name}`} className="mx-auto h-32 w-32" /> : <div className="mx-auto h-32 w-32" />}
      <p className="mt-2 text-sm font-semibold text-slate-800">{product.name}</p>
      {product.brand && <p className="text-xs text-slate-500">{product.brand}</p>}
      <p className="text-xs text-slate-500">ID {product.product_id}</p>
      {product.is_restricted ? <p className="mt-1 text-xs font-semibold text-red-600">RESTRICTED</p> : null}
    </div>
  )
}

const CATEGORIES = ['Insecticide', 'Fungicide', 'Herbicide', 'Bio-pesticide', 'Other']
const SEASONS = ['Kharif', 'Rabi', 'Monsoon', 'Year-round']

// Makes a QR for a product that is not registered yet. Scan it on "Add product" to fill the form.
function NewProductQr() {
  const [f, setF] = useState({ name: '', brand: '', category: 'Insecticide', season: 'Year-round', min_stock_level: '10' })
  const [src, setSrc] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const value = f.name.trim() ? newProductQrValue(f) : ''

  useEffect(() => {
    let cancelled = false
    if (!value) {
      setSrc('')
      return undefined
    }
    QRCode.toDataURL(value, { width: 260, margin: 1 })
      .then((url) => !cancelled && setSrc(url))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [value])

  return (
    <Card title="QR for a NEW product">
      <p className="mb-4 text-sm text-slate-600">
        Fill in the details of a product that is not in the shop yet. Scanning this QR on the Add Product page fills the form for you.
      </p>
      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-3">
          <Field label="Product name *" htmlFor="nq_name">
            <input id="nq_name" className={inputClass} value={f.name} onChange={set('name')} />
          </Field>
          <Field label="Brand" htmlFor="nq_brand">
            <input id="nq_brand" className={inputClass} value={f.brand} onChange={set('brand')} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Category" htmlFor="nq_cat">
              <select id="nq_cat" className={inputClass} value={f.category} onChange={set('category')}>
                {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
            <Field label="Season" htmlFor="nq_season">
              <select id="nq_season" className={inputClass} value={f.season} onChange={set('season')}>
                {SEASONS.map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
          </div>
          <Field label="Minimum stock level" htmlFor="nq_min">
            <input id="nq_min" type="number" min="0" className={inputClass} value={f.min_stock_level} onChange={set('min_stock_level')} />
          </Field>
        </div>
        <div className="flex flex-col items-center justify-center">
          {src ? (
            <img src={src} alt="QR code for a new product" className="h-48 w-48" />
          ) : (
            <p className="text-sm text-slate-500">Type a product name to see its QR code.</p>
          )}
        </div>
      </div>
    </Card>
  )
}

export default function QrLabels() {
  const [products, setProducts] = useState(null)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')

  useEffect(() => {
    api('/products').then(setProducts).catch((e) => setError(e.message))
  }, [])

  if (!products && !error) return <Spinner label="Loading products..." />

  const q = search.trim().toLowerCase()
  const shown = (products || []).filter((p) => !q || `${p.name} ${p.brand || ''}`.toLowerCase().includes(q))

  return (
    <div>
      <div className="print:hidden">
        <PageHeader
          title="QR labels"
          subtitle="Print these and stick one on each product. Scan it on the Record Sale page to pick the product instantly."
          action={<Button onClick={() => window.print()}>🖨️ Print labels</Button>}
        />
        {error && <Alert type="error">{error}</Alert>}
        <Card>
          <input
            className={inputClass}
            placeholder="Search products..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </Card>
      </div>
      <div className="mt-4 print:hidden">
        <NewProductQr />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 print:grid-cols-3">
        {shown.map((p) => (
          <Label key={p.product_id} product={p} />
        ))}
      </div>
      {products && shown.length === 0 && <p className="mt-4 text-sm text-slate-500">No products match.</p>}
    </div>
  )
}
