// ------------------------------------------------------------------
// Layout.jsx - the frame around every page after login:
//   left sidebar (menu) + top bar (name, role, logout) + the page itself.
// The owner-only menu items are hidden for staff (Oct 10).
// ------------------------------------------------------------------
import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext.jsx'
import { Button } from './ui.jsx'

const NAV = [
  { to: '/', label: 'Dashboard', icon: '📊', ownerOnly: false, end: true },
  { to: '/products', label: 'Products', icon: '📦', ownerOnly: false },
  { to: '/sale', label: 'Record Sale', icon: '🧾', ownerOnly: false },
  { to: '/add-product', label: 'Add Product', icon: '➕', ownerOnly: true },
  { to: '/add-stock', label: 'Add Stock', icon: '🚚', ownerOnly: true },
  { to: '/suggestions', label: 'Restock Advice', icon: '💡', ownerOnly: true },
  { to: '/forecast', label: 'Forecast', icon: '📈', ownerOnly: true },
  { to: '/compliance', label: 'Compliance Log', icon: '🛡️', ownerOnly: true },
  { to: '/reports', label: 'Reports (Excel)', icon: '📥', ownerOnly: true },
  { to: '/users', label: 'Add User', icon: '👤', ownerOnly: true },
]

export default function Layout() {
  const { user, isOwner, logout } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false) // sidebar on phones

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  // Staff only get the items that are not owner-only
  const items = NAV.filter((item) => !item.ownerOnly || isOwner)

  return (
    <div className="min-h-screen md:flex">
      {/* dark overlay behind the sidebar on phones */}
      {menuOpen && (
        <div className="fixed inset-0 z-20 bg-black/40 md:hidden" onClick={() => setMenuOpen(false)} />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-30 w-64 transform bg-brand-900 text-white transition-transform md:static md:translate-x-0 ${
          menuOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="border-b border-white/10 px-6 py-5">
          <p className="text-xl font-bold">🌿 InventoTrack</p>
          <p className="text-xs text-green-200">Pesticide shop inventory</p>
        </div>
        <nav className="space-y-1 p-3">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-4 py-2.5 text-sm font-medium transition ${
                  isActive ? 'bg-white/15 text-white' : 'text-green-100 hover:bg-white/10'
                }`
              }
            >
              <span>{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 md:px-8">
          <button
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-lg md:hidden"
            onClick={() => setMenuOpen(true)}
            aria-label="Open menu"
          >
            ☰
          </button>
          <div className="ml-auto flex items-center gap-3">
            <div className="text-right">
              <p className="text-sm font-semibold text-slate-800">{user.name}</p>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                  isOwner ? 'bg-brand-100 text-brand-800' : 'bg-slate-200 text-slate-700'
                }`}
              >
                {isOwner ? 'Owner' : 'Staff'}
              </span>
            </div>
            <Button variant="secondary" onClick={handleLogout}>
              Logout
            </Button>
          </div>
        </header>

        {/* the current page is drawn here */}
        <main className="p-4 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
