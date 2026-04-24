const CATEGORIES = ['All', 'Politics', 'Technology', 'AI', 'Finance', 'Health', 'Sports', 'Entertainment', 'General']

const EMOJI = {
  All: '🌍', Politics: '🏛️', Technology: '💻', AI: '🤖',
  Finance: '📈', Health: '🏥', Sports: '⚽', Entertainment: '🎬', General: '📰',
}

export default function CategoryBar({ active, onChange }) {
  return (
    <div style={{
      position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)',
      zIndex: 20, display: 'flex', gap: 8, overflowX: 'auto',
      padding: '0 16px', scrollbarWidth: 'none', maxWidth: '100vw',
    }}>
      {CATEGORIES.map(cat => (
        <button
          key={cat}
          onClick={() => onChange(cat)}
          style={{
            flexShrink: 0,
            padding: '8px 16px',
            borderRadius: 24,
            border: 'none',
            cursor: 'pointer',
            fontSize: 13,
            fontWeight: 600,
            backdropFilter: 'blur(12px)',
            transition: 'all 0.2s',
            background: active === cat
              ? 'rgba(255,255,255,0.95)'
              : 'rgba(0,0,0,0.55)',
            color: active === cat ? '#000' : '#fff',
            boxShadow: active === cat ? '0 4px 16px rgba(0,0,0,0.3)' : 'none',
          }}
        >
          {EMOJI[cat]} {cat}
        </button>
      ))}
    </div>
  )
}
