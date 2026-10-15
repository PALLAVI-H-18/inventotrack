// ------------------------------------------------------------------
// AuthContext.jsx - remembers WHO is logged in and shares it with every page.
// Any page can write:  const { user, isOwner, login, logout } = useAuth()
// ------------------------------------------------------------------
import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, clearSession, getStoredUser, getToken, saveSession, setUnauthorizedHandler } from './api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  // On page refresh, restore the user from the browser if a token is still stored.
  const [user, setUser] = useState(() => (getToken() ? getStoredUser() : null))

  const logout = useCallback(() => {
    clearSession()
    setUser(null)
  }, [])

  // If any request gets a 401, api.js calls logout automatically.
  useEffect(() => {
    setUnauthorizedHandler(logout)
  }, [logout])

  async function login(email, password) {
    const data = await api('/auth/login', { method: 'POST', body: { email, password } })
    saveSession(data.token, data.user)
    setUser(data.user)
    return data.user
  }

  const value = { user, isOwner: user?.role === 'owner', login, logout }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}
