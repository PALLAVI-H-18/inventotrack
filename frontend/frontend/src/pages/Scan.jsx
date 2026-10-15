// ------------------------------------------------------------------
// Scan.jsx - one "Scanner" page: scan any product QR, see its stock, then choose what to do.
//   everyone: Sell this product      owner: Add stock / Send alert
// ------------------------------------------------------------------
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext.jsx'
import { api } from '../api.js'
import { parseQr } from '../qr.js'
import QrScanner from '../components/QrScanner.jsx'
import StockPanel from '../components/StockPanel.jsx'
import { Alert, Button, PageHeader, Spinner } from '../components/ui.jsx'

export default function Scan() {
  const { isOwner } = useAuth()
  const navigate = useNavigate()
  const [products, setProducts] = useState(null)
  const [error, setError] = useState('')
  const [scanning, setScanning] = useState(true)
  const [productId, setProductId] = useState(null)

  useEffect(() => {
    api('/products').then(setProducts).catch((e) => setError(e.message))
  }, [])

  function handleScan(text) {
    setScanning(false)
    const id = parseQr(text)
    const found = id && (products || []).find((p) => p.product_id === id)
    if (!found) {
      setProductId(null)
      setError('This QR code does not match any product in the shop.')
      return
    }
    setError('')
    setProductId(found.product_id)
  }

  if (!products && !error) return <Spinner label="Loading products..." />
  const product = (products || []).find((p) => p.product_id === productId)

  return (
    <div className="max-w-2xl space-y-4">
      <PageHeader title="Scanner" subtitle="Scan a product's QR code to see its stock, then sell it or add stock." />
      {error && <Alert type="error">{error}</Alert>}

      {scanning && products ? (
        <QrScanner onScan={handleScan} onClose={() => setScanning(false)} />
      ) : (
        <Button onClick={() => { setError(''); setScanning(true) }}>📷 Scan another product</Button>
      )}

      {product && (
        <div className="space-y-3">
          <StockPanel product={product} />
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() => navigate('/sale', { state: { productId: product.product_id } })}
              disabled={product.total_quantity <= 0}
            >
              🧾 Sell this product
            </Button>
            {isOwner && (
              <>
                <Button variant="secondary" onClick={() => navigate('/add-stock', { state: { productId: product.product_id } })}>
                  🚚 Add stock
                </Button>
                {product.status !== 'healthy' && (
                  <Button variant="secondary" onClick={() => navigate('/alerts')}>
                    🔔 Alert staff
                  </Button>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
