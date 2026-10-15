// ------------------------------------------------------------------
// RouteGuards.jsx - protected routes (Oct 9) and role-based routes (Oct 10).
//   RequireAuth  : not logged in            -> sent to /login
//   RequireOwner : logged in but only staff -> sent back to the dashboard
// ------------------------------------------------------------------
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../AuthContext.jsx'

export function RequireAuth() {
  const { user } = useAuth()
  return user ? <Outlet /> : <Navigate to="/login" replace />
}

export function RequireOwner() {
  const { isOwner } = useAuth()
  return isOwner ? <Outlet /> : <Navigate to="/" replace />
}
