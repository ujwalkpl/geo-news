export default function Navbar({ category, onCategoryChange }) {
  const categories = ['All', 'Politics', 'Technology', 'AI', 'Finance', 'Health', 'Sports', 'Entertainment']

  return (
    <div style={{
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      zIndex: 10,
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      padding: '14px 20px',
      background: 'linear-gradient(to bottom, rgba(0,0,0,0.85), transparent)',
    }}>
      {/* Logo */}
      <span style={{ fontWeight: 700, fontSize: '1.1rem', letterSpacing: '-0.3px', marginRight: '8px' }}>
        GeoNews
      </span>

      {/* Category filters */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {categories.map(cat => (
          <button
            key={cat}
            onClick={() => onCategoryChange(cat === 'All' ? null : cat)}
            style={{
              padding: '5px 14px',
              borderRadius: '999px',
              border: '1px solid rgba(255,255,255,0.15)',
              background: (category === cat || (cat === 'All' && !category))
                ? 'rgba(255,255,255,0.15)'
                : 'rgba(0,0,0,0.4)',
              color: '#fff',
              fontSize: '0.78rem',
              cursor: 'pointer',
              fontWeight: 500,
              transition: 'background 0.2s',
            }}
          >
            {cat}
          </button>
        ))}
      </div>
    </div>
  )
}
