import { useState, useEffect } from 'react'
import { motion, AnimatePresence, useMotionValue, useTransform } from 'framer-motion'
import { X, Heart, ExternalLink, ChevronLeft, ChevronRight } from 'lucide-react'
import { fetchArticle, likeArticle } from '../api/news'

const CAT_COLORS = {
  Politics: '#ef4444', Technology: '#3b82f6', AI: '#8b5cf6',
  Finance: '#10b981', Health: '#f59e0b', Sports: '#f97316',
  Entertainment: '#ec4899', General: '#6b7280',
}

function timeAgo(dateStr) {
  const diff = (Date.now() - new Date(dateStr)) / 1000
  if (diff < 60) return `${Math.round(diff)}s ago`
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
}

function ProgressBar({ total, current }) {
  return (
    <div style={{ display: 'flex', gap: 4, padding: '0 16px', paddingTop: 12 }}>
      {Array.from({ length: total }).map((_, i) => (
        <div key={i} style={{ flex: 1, height: 3, borderRadius: 2, background: 'rgba(255,255,255,0.3)', overflow: 'hidden' }}>
          <motion.div
            initial={{ width: i < current ? '100%' : '0%' }}
            animate={{ width: i < current ? '100%' : i === current ? '100%' : '0%' }}
            transition={i === current ? { duration: 8, ease: 'linear' } : { duration: 0 }}
            style={{ height: '100%', background: '#fff', borderRadius: 2 }}
          />
        </div>
      ))}
    </div>
  )
}

function ArticleCard({ article, onClose, onNext, onPrev, index, total, onLike, likedIds }) {
  const [detail, setDetail] = useState(null)
  const [liked, setLiked] = useState(likedIds.has(article.article_id))
  const dragY = useMotionValue(0)
  const opacity = useTransform(dragY, [0, 200], [1, 0])
  const scale = useTransform(dragY, [0, 200], [1, 0.92])

  useEffect(() => {
    fetchArticle(article.article_id).then(setDetail).catch(() => {})
    setLiked(likedIds.has(article.article_id))
  }, [article.article_id])

  const handleLike = async () => {
    if (liked) return
    setLiked(true)
    onLike(article.article_id)
    try { await likeArticle(article.article_id) } catch {}
  }

  const catColor = CAT_COLORS[article.category] || '#6b7280'

  // Our API returns a top-level `summary` field (not a translations array)
  const summary = detail?.summary || detail?.body?.slice(0, 300) || ''

  // Prefer image from stub (fast); fall back to full detail once loaded
  const imageUrl = article.image_url || detail?.image_url

  // geo_place_name may come from stub (feed) or from full detail (map click)
  const placeName = article.geo_place_name || detail?.geo_place_name

  // original source link from detail
  const sourceUrl = article.original_url || detail?.source_url

  return (
    <motion.div
      style={{
        position: 'absolute', inset: 0,
        y: dragY, opacity, scale,
        borderRadius: 24, overflow: 'hidden',
        background: '#111',
        boxShadow: '0 24px 80px rgba(0,0,0,0.8)',
      }}
      drag="y"
      dragConstraints={{ top: 0, bottom: 0 }}
      dragElastic={{ top: 0, bottom: 0.4 }}
      onDragEnd={(_, info) => { if (info.offset.y > 120) onClose() }}
    >
      {/* Background image */}
      {imageUrl && (
        <div style={{ position: 'absolute', inset: 0 }}>
          <img
            src={imageUrl}
            alt=""
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
          <div style={{
            position: 'absolute', inset: 0,
            background: 'linear-gradient(to bottom, rgba(0,0,0,0.4) 0%, rgba(0,0,0,0.1) 30%, rgba(0,0,0,0.7) 60%, rgba(0,0,0,0.95) 100%)',
          }} />
        </div>
      )}
      {!imageUrl && (
        <div style={{
          position: 'absolute', inset: 0,
          background: `linear-gradient(135deg, ${catColor}33 0%, #0a0a0a 60%)`,
        }} />
      )}

      {/* Top bar */}
      <div style={{ position: 'relative', zIndex: 10 }}>
        <ProgressBar total={total} current={index} />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px 0' }}>
          <span style={{
            background: catColor, color: '#fff', fontSize: 11, fontWeight: 700,
            padding: '4px 10px', borderRadius: 20, textTransform: 'uppercase', letterSpacing: 1,
          }}>
            {article.category}
          </span>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ color: 'rgba(255,255,255,0.6)', fontSize: 12 }}>
              {timeAgo(article.published_at)}
            </span>
            <button onClick={onClose} style={{
              background: 'rgba(0,0,0,0.4)', border: 'none', borderRadius: '50%',
              width: 36, height: 36, cursor: 'pointer', color: '#fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              backdropFilter: 'blur(8px)',
            }}>
              <X size={18} />
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0,
        padding: '24px 20px 32px', zIndex: 10,
      }}>
        {placeName && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <span style={{ fontSize: 16 }}>📍</span>
            <span style={{ color: 'rgba(255,255,255,0.7)', fontSize: 13, fontWeight: 500 }}>
              {placeName}
            </span>
          </div>
        )}

        <h2 style={{
          color: '#fff', fontSize: 22, fontWeight: 700, lineHeight: 1.3,
          marginBottom: 12, textShadow: '0 2px 8px rgba(0,0,0,0.5)',
        }}>
          {article.title}
        </h2>

        {summary && (
          <p style={{
            color: 'rgba(255,255,255,0.8)', fontSize: 14, lineHeight: 1.6,
            marginBottom: 16, display: '-webkit-box', WebkitLineClamp: 3,
            WebkitBoxOrient: 'vertical', overflow: 'hidden',
          }}>
            {summary}
          </p>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button onClick={handleLike} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: liked ? 'rgba(239,68,68,0.3)' : 'rgba(255,255,255,0.1)',
            border: liked ? '1px solid #ef4444' : '1px solid rgba(255,255,255,0.2)',
            borderRadius: 24, padding: '8px 16px', cursor: 'pointer', color: '#fff',
            backdropFilter: 'blur(8px)', transition: 'all 0.2s',
          }}>
            <Heart size={16} fill={liked ? '#ef4444' : 'none'} color={liked ? '#ef4444' : '#fff'} />
            <span style={{ fontSize: 13, fontWeight: 600 }}>
              {(detail?.likes ?? article.likes ?? 0) + (liked ? 1 : 0)}
            </span>
          </button>

          {sourceUrl && (
            <a href={sourceUrl} target="_blank" rel="noopener noreferrer" style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.2)',
              borderRadius: 24, padding: '8px 16px', color: '#fff',
              textDecoration: 'none', fontSize: 13, fontWeight: 600,
              backdropFilter: 'blur(8px)',
            }}>
              <ExternalLink size={14} /> Read full
            </a>
          )}

          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <button onClick={onPrev} disabled={index === 0} style={{
              width: 40, height: 40, borderRadius: '50%', border: 'none',
              background: index === 0 ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.15)',
              color: index === 0 ? 'rgba(255,255,255,0.3)' : '#fff',
              cursor: index === 0 ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              backdropFilter: 'blur(8px)',
            }}>
              <ChevronLeft size={20} />
            </button>
            <button onClick={onNext} disabled={index === total - 1} style={{
              width: 40, height: 40, borderRadius: '50%', border: 'none',
              background: index === total - 1 ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.9)',
              color: index === total - 1 ? 'rgba(255,255,255,0.3)' : '#000',
              cursor: index === total - 1 ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <ChevronRight size={20} />
            </button>
          </div>
        </div>

        {/* Swipe hint */}
        <div style={{ textAlign: 'center', marginTop: 12, color: 'rgba(255,255,255,0.3)', fontSize: 11 }}>
          swipe down to close
        </div>
      </div>

      {/* Tap zones for prev/next */}
      <div
        onClick={onPrev}
        style={{ position: 'absolute', left: 0, top: 60, bottom: 200, width: '30%', zIndex: 5, cursor: 'pointer' }}
      />
      <div
        onClick={onNext}
        style={{ position: 'absolute', right: 0, top: 60, bottom: 200, width: '30%', zIndex: 5, cursor: 'pointer' }}
      />
    </motion.div>
  )
}

export default function SnapViewer({ articles, initialIndex = 0, onClose }) {
  const [index, setIndex] = useState(initialIndex)
  const [direction, setDirection] = useState(1)
  const [likedIds, setLikedIds] = useState(new Set())

  const goNext = () => {
    if (index < articles.length - 1) { setDirection(1); setIndex(i => i + 1) }
    else onClose()
  }
  const goPrev = () => {
    if (index > 0) { setDirection(-1); setIndex(i => i - 1) }
  }
  const handleLike = (id) => setLikedIds(prev => new Set([...prev, id]))

  const article = articles[index]

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      style={{
        position: 'fixed', inset: 0, zIndex: 100,
        background: 'rgba(0,0,0,0.85)',
        backdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <motion.div
        initial={{ scale: 0.6, opacity: 0, y: 60 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.8, opacity: 0, y: 40 }}
        transition={{ type: 'spring', damping: 22, stiffness: 300 }}
        style={{
          width: '100%', maxWidth: 420,
          height: '88vh', maxHeight: 780,
          margin: '0 16px',
          position: 'relative',
        }}
      >
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={article.article_id}
            custom={direction}
            initial={{ x: direction * 60, opacity: 0, scale: 0.96 }}
            animate={{ x: 0, opacity: 1, scale: 1 }}
            exit={{ x: direction * -60, opacity: 0, scale: 0.96 }}
            transition={{ type: 'spring', damping: 25, stiffness: 320, duration: 0.25 }}
            style={{ position: 'absolute', inset: 0 }}
          >
            <ArticleCard
              article={article}
              index={index}
              total={articles.length}
              onClose={onClose}
              onNext={goNext}
              onPrev={goPrev}
              onLike={handleLike}
              likedIds={likedIds}
            />
          </motion.div>
        </AnimatePresence>
      </motion.div>
    </motion.div>
  )
}
