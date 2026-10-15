// ------------------------------------------------------------------
// api.js  -  the ONLY place that talks to the backend.
// Every page calls api('/some-route') instead of using fetch directly.
// ------------------------------------------------------------------

// Backend address. Comes from the .env file so it can be changed in one place.
export const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000'

const TOKEN_KEY = 'inventotrack_token'
const USER_KEY = 'inventotrack_user'

// ---- keeping the login in the browser (localStorage) ----
export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY))
  } catch {
    return null
  }
}

export function saveSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

// When the server says "401 not logged in / token expired", this function is called
// (AuthContext sets it to "log the user out and go to the login page").
let onUnauthorized = null
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

// The backend ALWAYS sends errors as { "error": "message", "details": { field: "problem" } }.
// "details" only exists when specific fields are wrong, so we show those problems to the user.
function buildError(data, status) {
  let message = data?.error || `Request failed (${status})`
  const problems = data?.details ? Object.values(data.details) : []
  if (problems.length > 0 && message === 'Validation failed') message = problems.join('. ')
  const error = new Error(message)
  error.status = status
  error.details = data?.details || null
  return error
}

// ---- the one function every page uses ----
//   api('/products')
//   api('/sales', { method: 'POST', body: { product_id: 1, quantity_sold: 2 } })
export async function api(path, { method = 'GET', body } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  // Attach the login token to every request. This is the "Authorization: Bearer" header
  // you tested in Postman.
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  let response
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    // fetch itself failed: server is off, wrong address, or no internet
    throw new Error('Cannot reach the server. Is the backend running?')
  }

  let data = null
  try {
    data = await response.json()
  } catch {
    // response had no JSON body
  }

  // Token missing/expired -> send the user back to login
  if (response.status === 401 && token && onUnauthorized) {
    clearSession()
    onUnauthorized()
  }

  if (!response.ok) {
    throw buildError(data, response.status)
  }

  return data
}

// ---- download a file (Excel) ----
// A plain <a href> cannot send the login token, so we fetch the file with the token,
// turn it into a Blob and let the browser save it.
export async function download(path, fallbackName = 'report.xlsx') {
  let response
  try {
    response = await fetch(`${API_URL}${path}`, { headers: { Authorization: `Bearer ${getToken()}` } })
  } catch {
    throw new Error('Cannot reach the server. Is the backend running?')
  }
  if (!response.ok) {
    let data = null
    try {
      data = await response.json()
    } catch {
      // not JSON
    }
    throw buildError(data, response.status)
  }
  // the server sends the name in the Content-Disposition header, e.g. filename=inventory_2026-10-14.xlsx
  const match = /filename="?([^";]+)"?/.exec(response.headers.get('Content-Disposition') || '')
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = match ? match[1] : fallbackName
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
  return link.download
}
