// ------------------------------------------------------------------
// QrScanner.jsx - opens the camera and reads a product QR code.
//   <QrScanner onScan={(text) => ...} onClose={() => ...} />
// Works on a phone (back camera) and on a laptop webcam. The browser only allows the camera
// on https:// addresses or on localhost, which is the case for your Render site.
// If the camera is not available the person can type the code (or product number) instead.
// ------------------------------------------------------------------
import { useEffect, useRef, useState } from 'react'
import { Html5Qrcode } from 'html5-qrcode'
import { Alert, Button, Card, inputClass } from './ui.jsx'

const REGION_ID = 'qr-camera-region'

function friendlyCameraError(err) {
  const text = String(err?.name || err?.message || err || '')
  if (!window.isSecureContext) return 'The camera only works on an https:// address (or localhost).'
  if (/NotAllowed|Permission/i.test(text)) return 'Camera permission was denied. Allow the camera for this site in the browser settings.'
  if (/NotFound|Devices/i.test(text)) return 'No camera was found on this device.'
  if (/NotReadable|TrackStart/i.test(text)) return 'The camera is being used by another app. Close it and try again.'
  return 'Could not start the camera. You can type the code below instead.'
}

export default function QrScanner({ onScan, onClose }) {
  const [error, setError] = useState('')
  const [starting, setStarting] = useState(true)
  const [typed, setTyped] = useState('')
  const handled = useRef(false) // a QR is seen many times a second; use only the first

  useEffect(() => {
    const scanner = new Html5Qrcode(REGION_ID)
    let active = true
    let started = false

    function stopCamera() {
      scanner
        .stop()
        .then(() => scanner.clear())
        .catch(() => {})
    }

    scanner
      .start(
        { facingMode: 'environment' }, // back camera on phones
        { fps: 10, qrbox: { width: 240, height: 240 } },
        (text) => {
          if (handled.current) return
          handled.current = true
          onScan(text)
        },
        () => {}, // called for every frame without a QR - ignore
      )
      .then(() => {
        started = true
        if (active) setStarting(false)
        else stopCamera() // the screen was closed while the camera was still starting
      })
      .catch((err) => {
        if (!active) return
        setStarting(false)
        setError(friendlyCameraError(err))
      })

    return () => {
      active = false
      if (started) stopCamera()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function submitTyped(event) {
    event.preventDefault()
    if (!typed.trim() || handled.current) return
    handled.current = true
    onScan(typed.trim())
  }

  return (
    <Card title="Scan a product QR code">
      <div className="space-y-4">
        {error && <Alert type="warning">{error}</Alert>}
        <div
          id={REGION_ID}
          className="mx-auto w-full max-w-sm overflow-hidden rounded-lg bg-slate-900"
          style={{ minHeight: error ? 0 : 240 }}
        />
        {starting && !error && <p className="text-center text-sm text-slate-500">Starting the camera...</p>}
        {!error && !starting && (
          <p className="text-center text-sm text-slate-500">Hold the QR code in front of the camera.</p>
        )}

        <form onSubmit={submitTyped} className="flex gap-2">
          <input
            aria-label="Type the code or product number"
            className={inputClass}
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder="No camera? Type the code, e.g. INVENTO:12 or 12"
          />
          <Button type="submit" variant="secondary">
            Use
          </Button>
        </form>

        <div className="text-right">
          <Button type="button" variant="secondary" onClick={onClose}>
            Close camera
          </Button>
        </div>
      </div>
    </Card>
  )
}
