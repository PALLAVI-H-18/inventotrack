// ------------------------------------------------------------------
// Users.jsx - owner-only form to create a login for a new staff member (or another owner).
// Calls POST /auth/register.
// ------------------------------------------------------------------
import { useState } from 'react'
import { api } from '../api.js'
import { Alert, Button, Card, Field, PageHeader, inputClass } from '../components/ui.jsx'

const empty = { name: '', email: '', password: '', role: 'staff' }

export default function Users() {
  const [form, setForm] = useState(empty)
  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState('')
  const [success, setSuccess] = useState('')
  const [saving, setSaving] = useState(false)

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value })

  function validate() {
    const found = {}
    if (!form.name.trim()) found.name = 'Name is required'
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim())) found.email = 'Enter a valid email like name@example.com'
    if (form.password.length < 6) found.password = 'Password must be at least 6 characters'
    return found
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setApiError('')
    setSuccess('')
    const found = validate()
    setErrors(found)
    if (Object.keys(found).length > 0) return

    setSaving(true)
    try {
      await api('/auth/register', { method: 'POST', body: { ...form, name: form.name.trim(), email: form.email.trim() } })
      setSuccess(`Created the ${form.role} account for ${form.email.trim()}.`)
      setForm(empty)
    } catch (err) {
      if (err.details) setErrors(err.details)
      setApiError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-xl">
      <PageHeader title="Add user" subtitle="Create a login for a staff member. Staff can sell stock but cannot see prices or owner pages." />
      <div className="mb-4 space-y-3">
        {apiError && <Alert type="error">{apiError}</Alert>}
        {success && <Alert type="success">{success}</Alert>}
      </div>
      <Card>
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <Field label="Full name *" htmlFor="uname" error={errors.name}>
            <input id="uname" className={inputClass} value={form.name} onChange={set('name')} />
          </Field>
          <Field label="Email *" htmlFor="uemail" error={errors.email}>
            <input id="uemail" type="email" className={inputClass} value={form.email} onChange={set('email')} />
          </Field>
          <Field label="Password *" htmlFor="upass" error={errors.password} hint="At least 6 characters. Share it with the person privately.">
            <input id="upass" type="password" autoComplete="new-password" className={inputClass} value={form.password} onChange={set('password')} />
          </Field>
          <Field label="Role" htmlFor="urole" error={errors.role}>
            <select id="urole" className={inputClass} value={form.role} onChange={set('role')}>
              <option value="staff">Staff</option>
              <option value="owner">Owner</option>
            </select>
          </Field>
          <Button type="submit" disabled={saving}>
            {saving ? 'Creating...' : 'Create user'}
          </Button>
        </form>
      </Card>
    </div>
  )
}
