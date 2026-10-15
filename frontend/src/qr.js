// ------------------------------------------------------------------
// qr.js - what is written inside a product's QR code, and how to read it back.
// The QR holds only the product number, like   INVENTO:12
// (no prices, no secrets), so anybody can scan it but the app still asks you to log in.
// ------------------------------------------------------------------
const PREFIX = 'INVENTO:'

export function qrValue(productId) {
  return `${PREFIX}${productId}`
}

// Returns the product id (a number) or null when the text is not one of our codes.
// A plain number such as "12" is accepted too, so a code can be typed by hand.
export function parseQr(text) {
  const clean = String(text || '').trim()
  const digits = clean.toUpperCase().startsWith(PREFIX) ? clean.slice(PREFIX.length).trim() : clean
  if (!/^\d+$/.test(digits)) return null
  const id = Number(digits)
  return id > 0 ? id : null
}

// ---- QR for a product that is NOT in the shop yet --------------------------------------
// Holds the details needed to fill the "Add product" form:  INVENTO-NEW|name|brand|category|season|minStock
// A supplier (or you) can print this on the carton; scanning it on "Add product" fills the form.
const NEW_PREFIX = 'INVENTO-NEW|'

export function newProductQrValue({ name, brand, category, season, min_stock_level }) {
  const clean = (v) => String(v ?? '').replace(/\|/g, ' ').trim() // "|" is the separator
  return NEW_PREFIX + [name, brand, category, season, min_stock_level].map(clean).join('|')
}

// Returns {name, brand, category, season, min_stock_level} or null if it is not a new-product code.
export function parseNewProductQr(text) {
  const clean = String(text || '').trim()
  if (!clean.toUpperCase().startsWith(NEW_PREFIX)) return null
  const [name = '', brand = '', category = '', season = '', min = ''] = clean.slice(NEW_PREFIX.length).split('|').map((s) => s.trim())
  if (!name) return null
  return { name, brand, category, season, min_stock_level: min }
}
