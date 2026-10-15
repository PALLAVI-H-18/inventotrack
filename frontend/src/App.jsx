// ------------------------------------------------------------------
// App.jsx - the list of all pages (routes) and who may open them.
// ------------------------------------------------------------------
import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import { RequireAuth, RequireOwner } from './components/RouteGuards.jsx'
import Login from './pages/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Products from './pages/Products.jsx'
import RecordSale from './pages/RecordSale.jsx'
import AddProduct from './pages/AddProduct.jsx'
import AddStock from './pages/AddStock.jsx'
import Suggestions from './pages/Suggestions.jsx'
import Forecast from './pages/Forecast.jsx'
import Compliance from './pages/Compliance.jsx'
import Reports from './pages/Reports.jsx'
import Users from './pages/Users.jsx'

export default function App() {
  return (
    <Routes>
      {/* anyone can open the login page */}
      <Route path="/login" element={<Login />} />

      {/* everything inside needs a login */}
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="products" element={<Products />} />
          <Route path="sale" element={<RecordSale />} />

          {/* owner-only pages */}
          <Route element={<RequireOwner />}>
            <Route path="add-product" element={<AddProduct />} />
            <Route path="add-stock" element={<AddStock />} />
            <Route path="suggestions" element={<Suggestions />} />
            <Route path="forecast" element={<Forecast />} />
            <Route path="compliance" element={<Compliance />} />
            <Route path="reports" element={<Reports />} />
            <Route path="users" element={<Users />} />
          </Route>
        </Route>
      </Route>

      {/* any unknown address goes to the dashboard */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
