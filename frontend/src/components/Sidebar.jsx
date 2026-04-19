export default function Sidebar({ articles, onClose }) {
  if (!articles || articles.length === 0) return null

  return (
    <div style={{
      position: 'absolute',
      top: 0,
      right: 0,
      bottom: 0,
      width: '340px',
      zIndex: 10,
      background: 'rgba(10,10,10,0.92)',
      borderLeft: '1px solid rgba(255,255,255,0.08)',
      display: 'flex',
      flexDirection: 'column',
      backdropFilter: 'blur(12px)',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '16px 20px',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
      }}>
        <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>
          {articles.length} article{articles.length > 1 ? 's' : ''}
        </span>
        <button
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            color: '#9ca3af',
            cursor: 'pointer',
            fontSize: '1.2rem',
            lineHeight: 1,
          }}
        >
          ✕
        </button>
      </div>

      {/* Article list */}
      <div style={{ overflowY: 'auto', flex: 1, padding: '12px' }}>
        {articles.map((article, i) => (
          <div
            key={article.article_id || i}
            style={{
              padding: '14px',
              borderRadius: '10px',
              background: 'rgba(255,255,255,0.04)',
              marginBottom: '10px',
              border: '1px solid rgba(255,255,255,0.06)',
              cursor: 'pointer',
            }}
          >
            {article.image_url && (
              <img
                src={article.image_url}
                alt=""
                style={{ width: '100%', borderRadius: '6px', marginBottom: '10px', objectFit: 'cover', height: '140px' }}
              />
            )}
            <div style={{ fontSize: '0.7rem', color: '#6b7280', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {article.category || 'General'}
            </div>
            <div style={{ fontSize: '0.9rem', fontWeight: 600, lineHeight: 1.4, color: '#f9fafb' }}>
              {article.title}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
