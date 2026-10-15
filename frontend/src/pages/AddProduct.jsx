// ------------------------------------------------------------------
// AddProduct.jsx (Oct 4) - owner-only form. If the backend finds the name in the
// restricted list it sends back "restricted_match" + "warning", which we show.
// ------------------------------------------------------------------
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
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

  // one small helper updates any field:  onChange={set('brand')}
  const set = (field) => (event) => setForm({ ...form, [field]: event.target.value })

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

      <Card>
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
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
