// ------------------------------------------------------------------
// StockPanel.jsx - shown right after a product is chosen / scanned.
// Shows how many are left, how many were sold, and a warning when stock is low or finished.
//   <StockPanel product={product} />
// ------------------------------------------------------------------
import { StatusBadge } from './ui.jsx'

function Number({ label, value, tone = 'text-slate-900' }) {
  return (
    <div className="rounded-lg bg-white/70 px-3 py-2 text-center">
      <p className={`text-2xl font-bold ${tone}`}>{value}</p>
      <p className="text-xs text-slate-500">{label}</p>
    </div>
  )
}

export default function StockPanel({ product }) {
  if (!product) return null
  const tone =
    product.status === 'out_of_stock'
      ? { box: 'border-red-200 bg-red-50', num: 'text-red-700' }
      : product.status === 'low_stock'
        ? { box: 'border-amber-200 bg-amber-50', num: 'text-amber-700' }
        : { box: 'border-green-200 bg-green-50', num: 'text-green-700' }

  return (
    <div className={`rounded-xl border p-4 ${tone.box}`} data-testid="stock-panel">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-semibold text-slate-900">{product.name}</p>
          <p className="text-xs text-slate-500">
            {product.brand ? `${product.brand} · ` : ''}ID {product.product_id}
            {product.is_restricted ? ' · Restricted' : ''}
          </p>
        </div>
        <StatusBadge status={product.status} />
      </div>
      <div className="grid grid-cols-3 gap-2">
        <Number label="In stock now" value={product.total_quantity} tone={tone.num} />
        <Number label="Sold today" value={product.sold_today ?? 0} />
        <Number label="Sold in total" value={product.total_sold ?? 0} />
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Minimum level: {product.min_stock_level}. Expired batches are not counted.
      </p>
    </div>
  )
}
