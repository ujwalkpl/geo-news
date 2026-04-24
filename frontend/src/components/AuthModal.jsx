import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Mail, Lock, User, Loader, AlertCircle } from 'lucide-react'
import { login, register } from '../api/auth'

export default function AuthModal({ open, onClose, onAuth }) {
  const [tab, setTab] = useState('login')       // 'login' | 'register'
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function reset() {
    setEmail(''); setUsername(''); setPassword(''); setError(''); setLoading(false)
  }

  function switchTab(t) { setTab(t); setError('') }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (tab === 'login') {
        const { access_token } = await login({ email, password })
        onAuth(access_token)
        reset(); onClose()
      } else {
        await register({ email, username, password })
        // auto-login after register
        const { access_token } = await login({ email, password })
        onAuth(access_token)
        reset(); onClose()
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const inputStyle = {
    width: '100%', background: 'rgba(255,255,255,0.07)',
    border: '1px solid rgba(255,255,255,0.12)', borderRadius: 12,
    padding: '11px 14px 11px 40px', color: '#fff', fontSize: 14,
    outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit',
  }
  const iconStyle = {
    position: 'absolute', left: 13, top: '50%', transform: 'translateY(-50%)',
    color: 'rgba(255,255,255,0.35)', pointerEvents: 'none',
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          style={{
            position: 'fixed', inset: 0, zIndex: 200,
            background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(6px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
          onClick={(e) => e.target === e.currentTarget && onClose()}
        >
          <motion.div
            initial={{ scale: 0.92, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.92, opacity: 0, y: 20 }}
            transition={{ type: 'spring', damping: 24, stiffness: 300 }}
            style={{
              width: '100%', maxWidth: 380, margin: '0 16px',
              background: 'rgba(16,16,18,0.98)',
              borderRadius: 24, border: '1px solid rgba(255,255,255,0.1)',
              boxShadow: '0 24px 80px rgba(0,0,0,0.7)',
              overflow: 'hidden',
            }}
          >
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '20px 20px 0' }}>
              <h3 style={{ color: '#fff', fontSize: 18, fontWeight: 700 }}>
                {tab === 'login' ? 'Sign in' : 'Create account'}
              </h3>
              <button onClick={onClose} style={{
                background: 'rgba(255,255,255,0.08)', border: 'none', borderRadius: '50%',
                width: 34, height: 34, cursor: 'pointer', color: '#fff',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <X size={16} />
              </button>
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', margin: '16px 20px 0', background: 'rgba(255,255,255,0.06)', borderRadius: 12, padding: 4 }}>
              {['login', 'register'].map(t => (
                <button key={t} onClick={() => switchTab(t)} style={{
                  flex: 1, padding: '8px 0', border: 'none', borderRadius: 10, cursor: 'pointer',
                  fontSize: 13, fontWeight: 600,
                  background: tab === t ? 'rgba(255,255,255,0.12)' : 'transparent',
                  color: tab === t ? '#fff' : 'rgba(255,255,255,0.4)',
                  transition: 'all 0.2s',
                }}>
                  {t === 'login' ? 'Sign in' : 'Register'}
                </button>
              ))}
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} style={{ padding: '16px 20px 24px' }}>

              {tab === 'register' && (
                <div style={{ position: 'relative', marginBottom: 10 }}>
                  <span style={iconStyle}><User size={15} /></span>
                  <input
                    type="text" placeholder="Username" value={username}
                    onChange={e => setUsername(e.target.value)}
                    required minLength={3} maxLength={50}
                    style={inputStyle}
                  />
                </div>
              )}

              <div style={{ position: 'relative', marginBottom: 10 }}>
                <span style={iconStyle}><Mail size={15} /></span>
                <input
                  type="email" placeholder="Email" value={email}
                  onChange={e => setEmail(e.target.value)}
                  required style={inputStyle}
                />
              </div>

              <div style={{ position: 'relative', marginBottom: 14 }}>
                <span style={iconStyle}><Lock size={15} /></span>
                <input
                  type="password" placeholder="Password" value={password}
                  onChange={e => setPassword(e.target.value)}
                  required minLength={6} maxLength={72}
                  style={inputStyle}
                />
              </div>

              {error && (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  background: 'rgba(239,68,68,0.15)', borderRadius: 10,
                  padding: '10px 14px', marginBottom: 12,
                }}>
                  <AlertCircle size={14} color="#ef4444" />
                  <span style={{ fontSize: 12, color: '#ef4444' }}>{error}</span>
                </div>
              )}

              <motion.button
                type="submit"
                whileTap={{ scale: 0.97 }}
                disabled={loading}
                style={{
                  width: '100%', background: loading ? 'rgba(59,130,246,0.5)' : '#3b82f6',
                  border: 'none', borderRadius: 14, padding: '13px 0',
                  color: '#fff', fontSize: 14, fontWeight: 700,
                  cursor: loading ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                }}
              >
                {loading
                  ? <><Loader size={16} style={{ animation: 'spin 1s linear infinite' }} /> Please wait…</>
                  : tab === 'login' ? 'Sign in' : 'Create account'
                }
              </motion.button>
            </form>

            <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
