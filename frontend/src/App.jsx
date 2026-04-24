import { useState, useCallback } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { List, Globe, Plus } from 'lucide-react'
import MapView from './components/MapView'
import SnapViewer from './components/SnapViewer'
import CategoryBar from './components/CategoryBar'
import FeedDrawer from './components/FeedDrawer'
import UploadModal from './components/UploadModal'

export default function App() {
  const [category, setCategory] = useState('All')
  const [snapArticles, setSnapArticles] = useState(null)
  const [feedOpen, setFeedOpen] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)

  const handleArticleClick = useCallback((articles) => {
    setFeedOpen(false)
    setSnapArticles(articles)
  }, [])

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', background: '#0a0a0a' }}>
      {/* Map — fills the entire viewport */}
      <MapView category={category} onArticleClick={handleArticleClick} />

      {/* Category filter bar — centered at top, scrollable */}
      <CategoryBar active={category} onChange={setCategory} />

      {/* Logo — top-left */}
      <div style={{
        position: 'absolute', top: 16, left: 16, zIndex: 20,
        display: 'flex', alignItems: 'center', gap: 8,
        background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(12px)',
        borderRadius: 20, padding: '8px 14px',
        border: '1px solid rgba(255,255,255,0.1)',
      }}>
        <Globe size={18} color="#fff" />
        <span style={{ color: '#fff', fontWeight: 800, fontSize: 16, letterSpacing: -0.5 }}>GeoNews</span>
      </div>

      {/* Bottom nav — centered */}
      <div style={{
        position: 'absolute', bottom: 32, left: '50%', transform: 'translateX(-50%)',
        zIndex: 20, display: 'flex', gap: 12,
      }}>
        <motion.button
          whileTap={{ scale: 0.92 }}
          onClick={() => setFeedOpen(true)}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            background: 'rgba(255,255,255,0.92)', border: 'none',
            borderRadius: 28, padding: '12px 24px', cursor: 'pointer',
            fontSize: 14, fontWeight: 700, color: '#000',
            boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          }}
        >
          <List size={18} /> News Feed
        </motion.button>

        <motion.button
          whileTap={{ scale: 0.92 }}
          onClick={() => setUploadOpen(true)}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            background: '#3b82f6', border: 'none',
            borderRadius: 28, padding: '12px 20px', cursor: 'pointer',
            fontSize: 14, fontWeight: 700, color: '#fff',
            boxShadow: '0 8px 32px rgba(59,130,246,0.4)',
          }}
        >
          <Plus size={18} /> Report
        </motion.button>
      </div>

      {/* Snap Viewer — story-style article overlay */}
      <AnimatePresence>
        {snapArticles && (
          <SnapViewer
            articles={snapArticles}
            initialIndex={0}
            onClose={() => setSnapArticles(null)}
          />
        )}
      </AnimatePresence>

      {/* Upload Modal — GPS-based news reporting */}
      <UploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        token={null}
      />

      {/* Feed Drawer — scrollable news list */}
      <FeedDrawer
        open={feedOpen}
        onClose={() => setFeedOpen(false)}
        category={category}
        onArticleClick={handleArticleClick}
      />
    </div>
  )
}

