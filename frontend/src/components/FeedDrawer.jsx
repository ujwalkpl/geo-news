import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, MapPin, Heart } from 'lucide-react'
import { fetchFeed } from '../api/news'

const CAT_COLORS = {
  Politics: '#ef4444', Technology: '#3b82f6', AI: '#8b5cf6',
  Finance: '#10b981', Health: '#f59e0b', Sports: '#f97316',
  Entertainment: '#ec4899', General: '#6b7280',
}

function timeAgo(dateStr) {
  const diff = (Date.now() - new Date(dateStr)) / 1000
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
}

export default function FeedDrawer({ open, onClose, category, onArticleClick }) {
  const [articles, setArticles] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    fetchFeed(1, category)
      .then(data => { setArticles(data || []) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [open, category])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ y: '100%' }}
          animate={{ y: 0 }}
          exit={{ y: '100%' }}
          transition={{ type: 'spring', damping: 28, stiffness: 300 }}
          style={{
            position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 50,
            height: '75vh', background: 'rgba(14,14,14,0.97)',
            borderRadius: '24px 24px 0 0', overflow: 'hidden',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(255,255,255,0.08)',
            boxShadow: '0 -20px 60px rgba(0,0,0,0.6)',
          }}
        >
          {/* Handle */}
          <div style={{ display: 'flex', justifyContent: 'center', padding: '12px 0 4px' }}>
            <div style={{ width: 40, height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.2)' }} />
          </div>

          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 20px 16px' }}>
            <h3 style={{ color: '#fff', fontSize: 18, fontWeight: 700 }}>
              {(!category || category === 'All') ? '🌍 Latest News' : `${category} News`}
            </h3>
            <button onClick={onClose} style={{
              background: 'rgba(255,255,255,0.08)', border: 'none', borderRadius: '50%',
              width: 36, height: 36, cursor: 'pointer', color: '#fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <X size={18} />
            </button>
          </div>

          {/* Feed */}
          <div style={{ overflowY: 'auto', height: 'calc(100% - 90px)', padding: '0 16px 24px' }}>
            {loading ? (
              <div style={{ textAlign: 'center', color: 'rgba(255,255,255,0.4)', paddingTop: 40, fontSize: 14 }}>
                Loading...
              </div>
            ) : articles.length === 0 ? (
              <div style={{ textAlign: 'center', color: 'rgba(255,255,255,0.4)', paddingTop: 40, fontSize: 14 }}>
                No articles yet. Check back soon.
              </div>
            ) : articles.map((a, i) => (
              <motion.div
                key={a.article_id}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                onClick={() => onArticleClick([a])}
                style={{
                  display: 'flex', gap: 12, padding: '12px 0',
                  borderBottom: '1px solid rgba(255,255,255,0.06)',
                  cursor: 'pointer',
                }}
              >
                {a.image_url && (
                  <img
                    src={a.image_url}
                    alt=""
                    style={{ width: 80, height: 64, borderRadius: 10, objectFit: 'cover', flexShrink: 0 }}
                  />
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
                    <span style={{
                      fontSize: 10, fontWeight: 700, color: CAT_COLORS[a.category] || '#6b7280',
                      textTransform: 'uppercase', letterSpacing: 0.8,
                    }}>
                      {a.category}
                    </span>
                    <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: 11 }}>
                      {timeAgo(a.published_at)}
                    </span>
                  </div>
                  <p style={{
                    color: '#f1f5f9', fontSize: 14, fontWeight: 600, lineHeight: 1.4,
                    display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                    overflow: 'hidden', marginBottom: 4,
                  }}>
                    {a.title}
                  </p>
                  <div style={{ display: 'flex', gap: 12 }}>
                    {a.geo_place_name && (
                      <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 11, display: 'flex', alignItems: 'center', gap: 3 }}>
                        <MapPin size={10} /> {a.geo_place_name}
                      </span>
                    )}
                    <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 11, display: 'flex', alignItems: 'center', gap: 3 }}>
                      <Heart size={10} /> {a.likes || 0}
                    </span>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
