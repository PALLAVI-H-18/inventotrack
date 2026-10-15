// ------------------------------------------------------------------
// Login.jsx (Oct 2 + Oct 9) - login form with validation.
// On success the token is stored and the user lands on the dashboard.
// ------------------------------------------------------------------
import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../AuthContext.jsx'
import { Alert, Button, Field, inputClass } from '../components/ui.jsx'

export default function Login() {
  const { user, login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false) // eye button: show what you typed

  // Already logged in? Skip the login page.
  if (user) return <Navigate to="/" replace />

  function validate() {
    const found = {}
    if (!email.trim()) found.email = 'Email is required'
    else if (!/^\S+@\S+\.\S+$/.test(email.trim())) found.email = 'Enter a valid email address'
    if (!password) found.password = 'Password is required'
    return found
  }

  async function handleSubmit(event) {
    event.preventDefault() // stop the browser reloading the page
    setApiError('')
    const found = validate()
    setErrors(found)
    if (Object.keys(found).length > 0) return

    setLoading(true)
    try {
      await login(email.trim(), password) // on success, "user" is set and the Navigate above takes over
    } catch (error) {
      setApiError(error.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-brand-50 p-4">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <p className="text-4xl">🌿</p>
          <h1 className="mt-2 text-3xl font-bold text-brand-900">InventoTrack</h1>
          <p className="mt-1 text-sm text-slate-500">Real-time stock monitoring and replenishment</p>
        </div>

        <form
          onSubmit={handleSubmit}
          noValidate
          className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
        >
          {apiError && <Alert type="error">{apiError}</Alert>}

          <Field label="Email" htmlFor="email" error={errors.email}>
            <input
              id="email"
              type="email"
              className={inputClass}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoComplete="username"
            />
          </Field>

          <Field label="Password" htmlFor="password" error={errors.password}>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                className={`${inputClass} pr-16`}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-3 text-sm font-semibold text-brand-700 hover:underline"
              >
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>
          </Field>

          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign in'}
          </Button>
        </form>

      </div>
    </div>
  )
}
