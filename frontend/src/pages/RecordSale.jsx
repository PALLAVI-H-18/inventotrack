// ------------------------------------------------------------------
// RecordSale.jsx (Oct 5) - record a sale.
//  * shows how many units are available (stock check before sending)
//  * restricted products show a warning and make "Buyer ID" mandatory
//  * after the sale it shows WHICH batches the stock came from (FIFO)
// ------------------------------------------------------------------
import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { api } from '../api.js'
import { Alert, Button, Card, Field, PageHeader, Spinner, inputClass } from '../components/ui.jsx'

export default function RecordSale() {
  const location = useLocation()
  // coming from the "Sell" button on the Products page pre-selects the product
  const preselected = location.state?.productId ? String(location.state.productId) : ''

  const [products, setProducts] = useState(null)
  const [productId, setProductId] = useState(preselected)
  const [quantity, setQuantity] = useState('')
  const [buyerId, setBuyerId] = useState('')
  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState('')
  const [result, setResult] = useState(null)
  const [saving, setSaving] = useState(false)

  async function loadProducts() {
    try {
      setProducts(await api('/products'))
    } catch (err) {
      setApiError(err.message)
    }
  }

  useEffect(() => {
    loadProducts()
  }, [])

  const product = (products || []).find((p) => String(p.product_id) === productId)

  function validate() {
    const found = {}
    if (!product) found.product = 'Choose a product'
    const qty = Number(quantity)
    if (quantity === '' || !Number.isInteger(qty) || qty <= 0) {
      found.quantity = 'Enter a whole number greater than 0'
    } else if (product && qty > product.total_quantity) {
      found.quantity = `Only ${product.total_quantity} units available`
    }
    if (product?.is_restricted && !buyerId.trim()) {
      found.buyerId = 'Buyer identification is required for restricted pesticides'
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
      const body = { product_id: Number(productId), quantity_sold: Number(quantity) }
      if (product.is_restricted) body.buyer_id_proof = buyerId.trim()
      const data = await api('/sales', { method: 'POST', body })
      setResult(data)
      setQuantity('')
      setBuyerId('')
      await loadProducts() // refresh the available stock shown on this page
    } catch (err) {
      setApiError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (!products && !apiError) return <Spinner label="Loading products..." />

  return (
    <div className="max-w-2xl">
      <PageHeader title="Record sale" subtitle="Stock is taken from the batch that expires first (FIFO)." />

      <div className="mb-4 space-y-3">
        {apiError && <Alert type="error">{apiError}</Alert>}
        {result && (
          <Alert type="success" title={`Sold ${result.total_quantity_sold} x ${result.product_name}`}>
            <p className="mb-2">Stock was taken from these batches:</p>
            <ul className="list-disc pl-5">
              {result.batches_used.map((b) => (
                <li key={b.batch_id}>
                  Batch #{b.batch_id}: {b.quantity_taken} units taken, {b.remaining_in_batch} left
                </li>
              ))}
            </ul>
          </Alert>
        )}
      </div>

      <Card>
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <Field label="Product *" htmlFor="product" error={errors.product}>
            <select
              id="product"
              className={inputClass}
              value={productId}
              onChange={(e) => {
                setProductId(e.target.value)
                setErrors({})
              }}
            >
              <option value="">Select a product...</option>
              {(products || []).map((p) => (
                <option key={p.product_id} value={p.product_id} disabled={p.status === 'out_of_stock'}>
                  {p.name} - {p.total_quantity} in stock{p.is_restricted ? ' (restricted)' : ''}
                </option>
              ))}
            </select>
          </Field>

          {product && (
            <p className="text-sm text-slate-600">
              Available to sell: <strong>{product.total_quantity}</strong> units (expired batches are not counted)
            </p>
          )}

          {product?.is_restricted ? (
            <Alert type="warning" title="Restricted pesticide">
              The law requires the buyer to be identified for this product. Enter their ID below.
            </Alert>
          ) : null}

          <Field label="Quantity *" htmlFor="quantity" error={errors.quantity}>
            <input
              id="quantity"
              type="number"
              min="1"
              className={inputClass}
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
            />
          </Field>

          {product?.is_restricted ? (
            <Field label="Buyer ID proof *" htmlFor="buyerId" error={errors.buyerId} hint="Example: Aadhaar XXXX-XXXX-1234">
              <input id="buyerId" className={inputClass} value={buyerId} onChange={(e) => setBuyerId(e.target.value)} />
            </Field>
          ) : null}

          <Button type="submit" disabled={saving}>
            {saving ? 'Recording...' : 'Record sale'}
          </Button>
        </form>
      </Card>
    </div>
  )
}
