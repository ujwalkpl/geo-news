import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, MapPin, Camera, Send, Loader, CheckCircle, AlertCircle } from 'lucide-react'
import { uploadArticle } from '../api/news'

export default function UploadModal({ open, onClose, token }) {
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [image, setImage] = useState(null)
  const [preview, setPreview] = useState(null)
  const [gps, setGps] = useState(null)           // { lat, lng, accuracy }
  const [gpsError, setGpsError] = useState(null)
  const [gpsLoading, setGpsLoading] = useState(false)
  const [status, setStatus] = useState('idle')   // idle | submitting | success | error
  const [errorMsg, setErrorMsg] = useState('')
  const fileRef = useRef(null)

  // Get GPS when modal opens
  useEffect(() => {
    if (!open) return
    setGps(null)
    setGpsError(null)
    setGpsLoading(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGps({ lat: pos.coords.latitude, lng: pos.coords.longitude, accuracy: pos.coords.accuracy })
        setGpsLoading(false)
      },
      (err) => {
        setGpsError('Could not get location: ' + err.message)
        setGpsLoading(false)
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    )
  }, [open])

  // Reset form when closed
  useEffect(() => {
    if (!open) {
      setTitle(''); setText(''); setImage(null); setPreview(null)
      setStatus('idle'); setErrorMsg('')
    }
  }, [open])

  function handleImage(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setImage(file)
    setPreview(URL.createObjectURL(file))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!gps) { setErrorMsg('Waiting for GPS location...'); return }
    if (!text.trim() || text.trim().length < 10) { setErrorMsg('Write at least 10 characters.'); return }
    if (!token) { setErrorMsg('You must be logged in to post.'); return }

    setStatus('submitting')
    setErrorMsg('')
    try {
      await uploadArticle({ title: title.trim(), text: text.trim(), lat: gps.lat, lng: gps.lng, accuracy: gps.accuracy, image, token })
      setStatus('success')
      setTimeout(() => { onClose(); setStatus('idle') }, 2200)
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Upload failed'
      setErrorMsg(typeof detail === 'string' ? detail : JSON.stringify(detail))
      setStatus('error')
    }
  }

  const canSubmit = gps && text.trim().length >= 10 && status !== 'submitting'

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          style={{
            position: 'fixed', inset: 0, zIndex: 100,
            background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(6px)',
            display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
          }}
          onClick={(e) => e.target === e.currentTarget && onClose()}
        >
          <motion.div
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 28, stiffness: 300 }}
            style={{
              width: '100%', maxWidth: 540,
              background: 'rgba(16,16,18,0.98)',
              borderRadius: '24px 24px 0 0',
              border: '1px solid rgba(255,255,255,0.1)',
              boxShadow: '0 -20px 60px rgba(0,0,0,0.6)',
              padding: '0 0 env(safe-area-inset-bottom)',
              overflow: 'hidden',
            }}
          >
            {/* Handle */}
            <div style={{ display: 'flex', justifyContent: 'center', padding: '12px 0 0' }}>
              <div style={{ width: 40, height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.2)' }} />
            </div>

            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 20px 8px' }}>
              <h3 style={{ color: '#fff', fontSize: 17, fontWeight: 700 }}>Report News</h3>
              <button onClick={onClose} style={{
                background: 'rgba(255,255,255,0.08)', border: 'none', borderRadius: '50%',
                width: 34, height: 34, cursor: 'pointer', color: '#fff',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <X size={16} />
              </button>
            </div>

            {/* Success state */}
            {status === 'success' ? (
              <div style={{ padding: '40px 20px', textAlign: 'center' }}>
                <CheckCircle size={48} color="#10b981" style={{ margin: '0 auto 16px' }} />
                <p style={{ color: '#fff', fontSize: 16, fontWeight: 700 }}>Posted!</p>
                <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: 13, marginTop: 6 }}>
                  Your report is being processed and will appear on the map shortly.
                </p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} style={{ padding: '8px 20px 24px' }}>

                {/* GPS indicator */}
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  background: 'rgba(255,255,255,0.05)', borderRadius: 12,
                  padding: '10px 14px', marginBottom: 14,
                }}>
                  <MapPin size={14} color={gps ? '#10b981' : gpsError ? '#ef4444' : '#f59e0b'} />
                  <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.7)' }}>
                    {gpsLoading && 'Getting your location…'}
                    {gps && `${gps.lat.toFixed(4)}, ${gps.lng.toFixed(4)} · ±${Math.round(gps.accuracy)}m`}
                    {gpsError && gpsError}
                  </span>
                  {gps && gps.accuracy > 100 && (
                    <span style={{ marginLeft: 'auto', fontSize: 11, color: '#f59e0b' }}>Weak signal</span>
                  )}
                </div>

                {/* Title */}
                <input
                  type="text"
                  placeholder="Headline (optional)"
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  maxLength={300}
                  style={{
                    width: '100%', background: 'rgba(255,255,255,0.07)',
                    border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12,
                    padding: '11px 14px', color: '#fff', fontSize: 14,
                    outline: 'none', marginBottom: 10, boxSizing: 'border-box',
                  }}
                />

                {/* Body */}
                <textarea
                  placeholder="What's happening at your location? (min 10 characters)"
                  value={text}
                  onChange={e => setText(e.target.value)}
                  maxLength={5000}
                  rows={4}
                  style={{
                    width: '100%', background: 'rgba(255,255,255,0.07)',
                    border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12,
                    padding: '11px 14px', color: '#fff', fontSize: 14,
                    outline: 'none', resize: 'none', marginBottom: 10,
                    boxSizing: 'border-box', fontFamily: 'inherit',
                  }}
                />

                {/* Image preview */}
                {preview && (
                  <div style={{ position: 'relative', marginBottom: 10 }}>
                    <img src={preview} alt="" style={{ width: '100%', borderRadius: 12, maxHeight: 180, objectFit: 'cover' }} />
                    <button
                      type="button"
                      onClick={() => { setImage(null); setPreview(null) }}
                      style={{
                        position: 'absolute', top: 8, right: 8,
                        background: 'rgba(0,0,0,0.6)', border: 'none', borderRadius: '50%',
                        width: 28, height: 28, color: '#fff', cursor: 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                      }}
                    ><X size={14} /></button>
                  </div>
                )}

                {/* Error */}
                {(status === 'error' || errorMsg) && (
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    background: 'rgba(239,68,68,0.15)', borderRadius: 10,
                    padding: '10px 14px', marginBottom: 10,
                  }}>
                    <AlertCircle size={14} color="#ef4444" />
                    <span style={{ fontSize: 12, color: '#ef4444' }}>{errorMsg}</span>
                  </div>
                )}

                {/* Actions */}
                <div style={{ display: 'flex', gap: 10 }}>
                  {/* Camera / file picker */}
                  <input
                    ref={fileRef}
                    type="file"
                    accept="image/*"
                    capture="environment"
                    onChange={handleImage}
                    style={{ display: 'none' }}
                  />
                  <button
                    type="button"
                    onClick={() => fileRef.current?.click()}
                    style={{
                      background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: 14, padding: '12px 16px', cursor: 'pointer', color: '#fff',
                      display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 600,
                    }}
                  >
                    <Camera size={16} /> {preview ? 'Retake' : 'Photo'}
                  </button>

                  {/* Submit */}
                  <motion.button
                    type="submit"
                    whileTap={{ scale: 0.96 }}
                    disabled={!canSubmit}
                    style={{
                      flex: 1, background: canSubmit ? '#3b82f6' : 'rgba(255,255,255,0.08)',
                      border: 'none', borderRadius: 14, padding: '12px 20px',
                      cursor: canSubmit ? 'pointer' : 'not-allowed',
                      color: canSubmit ? '#fff' : 'rgba(255,255,255,0.3)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      gap: 8, fontSize: 14, fontWeight: 700,
                      transition: 'background 0.2s',
                    }}
                  >
                    {status === 'submitting'
                      ? <><Loader size={16} style={{ animation: 'spin 1s linear infinite' }} /> Posting…</>
                      : <><Send size={16} /> Post News</>
                    }
                  </motion.button>
                </div>
              </form>
            )}
          </motion.div>

          <style>{`
            @keyframes spin { to { transform: rotate(360deg) } }
            input::placeholder, textarea::placeholder { color: rgba(255,255,255,0.3); }
          `}</style>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
