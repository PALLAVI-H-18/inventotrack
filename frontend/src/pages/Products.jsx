// ------------------------------------------------------------------
// Products.jsx (Oct 3 + Oct 8) - product list with search, filters,
// green/amber/red status badges and a batch viewer.
// ------------------------------------------------------------------
import { Fragment, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext.jsx'
import { api } from '../api.js'
import { Alert, Button, Card, PageHeader, Spinner, StatusBadge, formatINR, inputClass, todayStr } from '../components/ui.jsx'

export default function Products() {
  const { isOwner } = useAuth()
  const navigate = useNavigate()

  const [products, setProducts] = useState(null)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [categoryFilter, setCategoryFilter] = useState('all')

  // batch viewer: which product is expanded + its batches
  const [openId, setOpenId] = useState(null)
  const [batchInfo, setBatchInfo] = useState(null)
  const [batchError, setBatchError] = useState('')
  const [batchLoading, setBatchLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    api('/products')
      .then((data) => !cancelled && setProducts(data))
      .catch((err) => !cancelled && setError(err.message))
    return () => {
      cancelled = true
    }
  }, [])

  const categories = useMemo(
    () => [...new Set((products || []).map((p) => p.category).filter(Boolean))].sort(),
    [products],
  )

  // The filtered list is recalculated whenever search or a filter changes
  const visible = useMemo(() => {
    const term = search.trim().toLowerCase()
    return (products || []).filter((p) => {
      const matchesSearch =
        !term || p.name.toLowerCase().includes(term) || (p.brand || '').toLowerCase().includes(term)
      const matchesStatus = statusFilter === 'all' || p.status === statusFilter
      const matchesCategory = categoryFilter === 'all' || p.category === categoryFilter
      return matchesSearch && matchesStatus && matchesCategory
    })
  }, [products, search, statusFilter, categoryFilter])

  async function toggleBatches(productId) {
    if (openId === productId) {
      setOpenId(null)
      return
    }
    setOpenId(productId)
    setBatchInfo(null)
    setBatchError('')
    setBatchLoading(true)
    try {
      setBatchInfo(await api(`/products/${productId}/batches`))
    } catch (err) {
      setBatchError(err.message)
    } finally {
      setBatchLoading(false)
    }
  }

  if (error) return <Alert type="error">{error}</Alert>
  if (!products) return <Spinner label="Loading products..." />

  const today = todayStr()

  return (
    <div>
      <PageHeader
        title="Products"
        subtitle="Stock shown here counts only batches that have not expired."
        action={
          isOwner && (
            <Link to="/add-product">
              <Button>+ Add product</Button>
            </Link>
          )
        }
      />

      <Card className="mb-4">
        <div className="grid gap-3 md:grid-cols-3">
          <input
            className={inputClass}
            placeholder="Search by name or brand..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search products"
          />
          <select className={inputClass} value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Filter by status">
            <option value="all">All statuses</option>
            <option value="healthy">Healthy</option>
            <option value="low_stock">Low stock</option>
            <option value="out_of_stock">Out of stock</option>
          </select>
          <select className={inputClass} value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} aria-label="Filter by category">
            <option value="all">All categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          Showing {visible.length} of {products.length} products
        </p>
      </Card>

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Product</th>
              <th className="px-4 py-3">Category</th>
              <th className="px-4 py-3">Season</th>
              <th className="px-4 py-3 text-right">In stock</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {visible.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No products match your search.
                </td>
              </tr>
            )}
            {visible.map((p) => (
              <Fragment key={p.product_id}>
                <tr className="hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-800">{p.name}</p>
                    <p className="text-xs text-slate-500">
                      {p.brand}
                      {p.is_restricted ? (
                        <span className="ml-2 rounded bg-red-100 px-1.5 py-0.5 font-semibold text-red-700">RESTRICTED</span>
                      ) : null}
                    </p>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{p.category}</td>
                  <td className="px-4 py-3 text-slate-600">{p.season}</td>
                  <td className="px-4 py-3 text-right font-semibold">{p.total_quantity}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={p.status} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      <Button variant="secondary" onClick={() => toggleBatches(p.product_id)}>
                        {openId === p.product_id ? 'Hide batches' : 'Batches'}
                      </Button>
                      <Button
                        disabled={p.status === 'out_of_stock'}
                        onClick={() => navigate('/sale', { state: { productId: p.product_id } })}
                      >
                        Sell
                      </Button>
                    </div>
                  </td>
                </tr>

                {openId === p.product_id && (
                  <tr className="bg-slate-50">
                    <td colSpan={6} className="px-4 py-4">
                      {batchLoading && <Spinner label="Loading batches..." />}
                      {batchError && <Alert type="error">{batchError}</Alert>}
                      {batchInfo && (
                        <div>
                          <p className="mb-2 text-xs font-semibold uppercase text-slate-500">
                            Batches (oldest expiry first - this is the order stock is sold)
                          </p>
                          <table className="w-full text-xs">
                            <thead className="text-slate-500">
                              <tr>
                                <th className="py-1 text-left">Batch</th>
                                <th className="py-1 text-right">Remaining</th>
                                <th className="py-1 text-left pl-6">Expiry</th>
                                {batchInfo.batches.some((b) => b.price_per_unit !== undefined) && (
                                  <th className="py-1 text-right">Price / unit</th>
                                )}
                                <th className="py-1 text-left pl-6">State</th>
                              </tr>
                            </thead>
                            <tbody>
                              {batchInfo.batches.map((b) => {
                                const expired = b.expiry_date < today
                                return (
                                  <tr key={b.batch_id} className="border-t border-slate-200">
                                    <td className="py-1.5">{b.batch_no}</td>
                                    <td className="py-1.5 text-right">{b.quantity_remaining}</td>
                                    <td className="py-1.5 pl-6">{b.expiry_date}</td>
                                    {b.price_per_unit !== undefined && (
                                      <td className="py-1.5 text-right">{formatINR(b.price_per_unit)}</td>
                                    )}
                                    <td className="py-1.5 pl-6">
                                      {expired ? (
                                        <span className="font-semibold text-red-600">Expired - not sold</span>
                                      ) : b.quantity_remaining === 0 ? (
                                        <span className="text-slate-400">Empty</span>
                                      ) : (
                                        <span className="text-green-700">Available</span>
                                      )}
                                    </td>
                                  </tr>
                                )
                              })}
                              {batchInfo.batches.length === 0 && (
                                <tr>
                                  <td colSpan={5} className="py-2 text-slate-500">
                                    No batches yet for this product.
                                  </td>
                                </tr>
                              )}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
