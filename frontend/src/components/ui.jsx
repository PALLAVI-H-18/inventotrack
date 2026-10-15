// ------------------------------------------------------------------
// ui.jsx - small reusable pieces (Oct 1). Every page reuses these so the
// whole app looks consistent:  Button, StatCard, StatusBadge, Alert, Spinner,
// Card, PageHeader, Field.
// ------------------------------------------------------------------

// ---------- helpers ----------
// Today's date as YYYY-MM-DD in the user's own time zone
export function todayStr() {
  const d = new Date()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${month}-${day}`
}

// 718402.44 -> "₹7,18,402.44"
export function formatINR(value) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(value || 0)
}

// Tailwind classes shared by every text box / dropdown
export const inputClass =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-200'

// ---------- Button ----------
export function Button({ children, variant = 'primary', className = '', ...props }) {
  const styles = {
    primary: 'bg-brand-600 text-white hover:bg-brand-700',
    secondary: 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-100',
    danger: 'bg-red-600 text-white hover:bg-red-700',
  }
  return (
    <button
      className={`inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

// ---------- StatCard: a number with a label (dashboard) ----------
export function StatCard({ label, value, tone = 'slate', hint }) {
  const tones = {
    slate: 'text-slate-800',
    green: 'text-green-700',
    amber: 'text-amber-600',
    red: 'text-red-600',
    brand: 'text-brand-700',
  }
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <p className={`mt-2 text-3xl font-bold ${tones[tone]}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </div>
  )
}

// ---------- StatusBadge: green / amber / red pill ----------
export function StatusBadge({ status }) {
  const map = {
    healthy: { label: 'Healthy', cls: 'bg-green-100 text-green-800' },
    low_stock: { label: 'Low stock', cls: 'bg-amber-100 text-amber-800' },
    out_of_stock: { label: 'Out of stock', cls: 'bg-red-100 text-red-800' },
  }
  const item = map[status] || { label: status, cls: 'bg-slate-100 text-slate-700' }
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${item.cls}`}>
      {item.label}
    </span>
  )
}

// ---------- PriorityBadge: restock priority pill ----------
export function PriorityBadge({ priority }) {
  const map = {
    order_now: { label: 'Order now', cls: 'bg-red-100 text-red-800' },
    order_soon: { label: 'Order soon', cls: 'bg-amber-100 text-amber-800' },
    ok: { label: 'OK', cls: 'bg-green-100 text-green-800' },
  }
  const item = map[priority] || { label: priority, cls: 'bg-slate-100 text-slate-700' }
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${item.cls}`}>{item.label}</span>
  )
}

// ---------- Alert: error / success / warning / info message box ----------
export function Alert({ type = 'error', title, children }) {
  const styles = {
    error: 'border-red-200 bg-red-50 text-red-800',
    success: 'border-green-200 bg-green-50 text-green-800',
    warning: 'border-amber-300 bg-amber-50 text-amber-900',
    info: 'border-blue-200 bg-blue-50 text-blue-800',
  }
  return (
    <div role="alert" className={`rounded-lg border px-4 py-3 text-sm ${styles[type]}`}>
      {title && <p className="font-semibold">{title}</p>}
      {children && <div className={title ? 'mt-1' : ''}>{children}</div>}
    </div>
  )
}

// ---------- Spinner: shown while data loads ----------
export function Spinner({ label = 'Loading...' }) {
  return (
    <div className="flex items-center gap-3 py-10 text-slate-500">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600" />
      <span className="text-sm">{label}</span>
    </div>
  )
}

// ---------- Card: white box with an optional title ----------
export function Card({ title, children, className = '' }) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm ${className}`}>
      {title && <h2 className="mb-4 text-base font-semibold text-slate-800">{title}</h2>}
      {children}
    </section>
  )
}

// ---------- PageHeader: title + subtitle at the top of a page ----------
export function PageHeader({ title, subtitle, action }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

// ---------- Field: label + input + error text ----------
export function Field({ label, htmlFor, error, hint, children }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1 block text-sm font-medium text-slate-700">
        {label}
      </label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
      {error && <p className="mt-1 text-xs font-medium text-red-600">{error}</p>}
    </div>
  )
}
