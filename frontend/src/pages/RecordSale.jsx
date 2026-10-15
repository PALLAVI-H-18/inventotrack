// ------------------------------------------------------------------
// RecordSale.jsx (Oct 5) - record a sale.
//  * shows how many units are available (stock check before sending)
//  * restricted products show a warning and make "Buyer ID" mandatory
//  * after the sale it shows WHICH batches the stock came from (FIFO)
// ------------------------------------------------------------------
import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { api } from '../api.js'
import { parseQr } from '../qr.js'
import QrScanner from '../components/QrScanner.jsx'
import StockPanel from '../components/StockPanel.jsx'
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
  const [scanning, setScanning] = useState(false)
  const [scanMsg, setScanMsg] = useState(null)
  const quantityRef = useRef(null)

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

  function handleScan(text) {
    setScanning(false)
    setResult(null)
    setErrors({})
    const id = parseQr(text)
    const found = id && (products || []).find((p) => p.product_id === id)
    if (!found) {
      setScanMsg({ type: 'error', text: 'This QR code does not match any product in the shop.' })
      return
    }
    if (found.status === 'out_of_stock' || found.total_quantity <= 0) {
      setScanMsg({ type: 'error', text: `${found.name} is out of stock.` })
      return
    }
    setProductId(String(found.product_id))
    setScanMsg({ type: 'success', text: `Scanned: ${found.name}` })
    setTimeout(() => quantityRef.current?.focus(), 50)
  }

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
        {scanMsg && <Alert type={scanMsg.type}>{scanMsg.text}</Alert>}
        {result && (
          <Alert type="success" title={`Sold ${result.total_quantity_sold} x ${result.product_name}`}>
            <p className="mb-2">
              <strong>{result.remaining_stock} left in stock</strong>
              {result.stock_status === 'low_stock' && ' - LOW STOCK, tell the owner.'}
              {result.stock_status === 'out_of_stock' && ' - OUT OF STOCK, tell the owner.'}
            </p>
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

      {scanning && (
        <div className="mb-4">
          <QrScanner onScan={handleScan} onClose={() => setScanning(false)} />
        </div>
      )}

      <Card>
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <Button type="button" variant="secondary" onClick={() => { setScanMsg(null); setScanning(true) }}>
            📷 Scan QR code
          </Button>
          <Field label="Product *" htmlFor="product" error={errors.product}>
            <select
              id="product"
              className={inputClass}
              value={productId}
              onChange={(e) => {
                setProductId(e.target.value)
                setScanMsg(null)
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

          <StockPanel product={product} />

          {product?.is_restricted ? (
            <Alert type="warning" title="Restricted pesticide">
              The law requires the buyer to be identified for this product. Enter their ID below.
            </Alert>
          ) : null}

          <Field label="Quantity *" htmlFor="quantity" error={errors.quantity}>
            <input
              id="quantity"
              ref={quantityRef}
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
