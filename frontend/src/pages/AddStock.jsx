// ------------------------------------------------------------------
// AddStock.jsx (Oct 4) - owner-only form that adds a new BATCH to a product.
// Each batch has its own expiry date - that is what makes FIFO selling possible.
// ------------------------------------------------------------------
import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Alert, Button, Card, Field, PageHeader, Spinner, inputClass, todayStr } from '../components/ui.jsx'

// These match the 3 suppliers created by seed_data.py (there is no suppliers API yet).
const SUPPLIERS = [
  { id: 1, name: 'AgroDistributors Pvt Ltd' },
  { id: 2, name: 'Krishi Suppliers' },
  { id: 3, name: 'Farm Input Traders' },
]

const emptyForm = () => ({
  product_id: '',
  supplier_id: '',
  batch_no: '',
  quantity_received: '',
  price_per_unit: '',
  purchase_date: todayStr(),
  expiry_date: '',
})

export default function AddStock() {
  const [products, setProducts] = useState(null)
  const [form, setForm] = useState(emptyForm())
  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState('')
  const [success, setSuccess] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let cancelled = false
    api('/products')
      .then((data) => !cancelled && setProducts(data))
      .catch((err) => !cancelled && setApiError(err.message))
    return () => {
      cancelled = true
    }
  }, [])

  const set = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  function validate() {
    const found = {}
    const today = todayStr()
    if (!form.product_id) found.product_id = 'Choose a product'
    if (!form.batch_no.trim()) found.batch_no = 'Batch number is required'

    const qty = Number(form.quantity_received)
    if (form.quantity_received === '' || !Number.isInteger(qty) || qty <= 0) {
      found.quantity_received = 'Enter a whole number greater than 0'
    }
    const price = Number(form.price_per_unit)
    if (form.price_per_unit === '' || Number.isNaN(price) || price <= 0) {
      found.price_per_unit = 'Enter a price greater than 0'
    }

    if (!form.purchase_date) found.purchase_date = 'Purchase date is required'
    else if (form.purchase_date > today) found.purchase_date = 'Purchase date cannot be in the future'

    if (!form.expiry_date) found.expiry_date = 'Expiry date is required'
    else if (form.purchase_date && form.expiry_date <= form.purchase_date) {
      found.expiry_date = 'Expiry must be after the purchase date'
    } else if (form.expiry_date < today) {
      found.expiry_date = 'This batch has already expired - check the date'
    }
    return found
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setApiError('')
    setSuccess(null)
    const found = validate()
    setErrors(found)
    if (Object.keys(found).length > 0) return

    setSaving(true)
    try {
      const body = {
        product_id: Number(form.product_id),
        batch_no: form.batch_no.trim(),
        quantity_received: Number(form.quantity_received),
        price_per_unit: Number(form.price_per_unit),
        purchase_date: form.purchase_date,
        expiry_date: form.expiry_date,
      }
      if (form.supplier_id) body.supplier_id = Number(form.supplier_id)

      const data = await api('/batches', { method: 'POST', body })
      const product = products.find((p) => String(p.product_id) === form.product_id)
      setSuccess(`Batch ${body.batch_no} added to ${product ? product.name : 'product'} (batch id ${data.batch_id}).`)
      setForm({ ...emptyForm(), product_id: form.product_id }) // keep the product selected for the next batch
    } catch (err) {
      setApiError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (!products && !apiError) return <Spinner label="Loading products..." />

  return (
    <div className="max-w-2xl">
      <PageHeader title="Add stock" subtitle="Record a new delivery as a batch with its own expiry date." />

      <div className="mb-4 space-y-3">
        {apiError && <Alert type="error">{apiError}</Alert>}
        {success && <Alert type="success">{success}</Alert>}
      </div>

      <Card>
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <Field label="Product *" htmlFor="product_id" error={errors.product_id}>
            <select id="product_id" className={inputClass} value={form.product_id} onChange={set('product_id')}>
              <option value="">Select a product...</option>
              {(products || []).map((p) => (
                <option key={p.product_id} value={p.product_id}>
                  {p.name}
                  {p.is_restricted ? ' (restricted)' : ''}
                </option>
              ))}
            </select>
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Batch number *" htmlFor="batch_no" error={errors.batch_no}>
              <input id="batch_no" className={inputClass} value={form.batch_no} onChange={set('batch_no')} />
            </Field>
            <Field label="Supplier" htmlFor="supplier_id">
              <select id="supplier_id" className={inputClass} value={form.supplier_id} onChange={set('supplier_id')}>
                <option value="">Not specified</option>
                {SUPPLIERS.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Quantity received *" htmlFor="quantity_received" error={errors.quantity_received}>
              <input
                id="quantity_received"
                type="number"
                min="1"
                className={inputClass}
                value={form.quantity_received}
                onChange={set('quantity_received')}
              />
            </Field>
            <Field label="Price per unit (₹) *" htmlFor="price_per_unit" error={errors.price_per_unit}>
              <input
                id="price_per_unit"
                type="number"
                min="0"
                step="0.01"
                className={inputClass}
                value={form.price_per_unit}
                onChange={set('price_per_unit')}
              />
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Purchase date *" htmlFor="purchase_date" error={errors.purchase_date}>
              <input id="purchase_date" type="date" className={inputClass} value={form.purchase_date} onChange={set('purchase_date')} />
            </Field>
            <Field label="Expiry date *" htmlFor="expiry_date" error={errors.expiry_date}>
              <input id="expiry_date" type="date" className={inputClass} value={form.expiry_date} onChange={set('expiry_date')} />
            </Field>
          </div>

          <Button type="submit" disabled={saving}>
            {saving ? 'Saving...' : 'Add batch'}
          </Button>
        </form>
      </Card>
    </div>
  )
}
