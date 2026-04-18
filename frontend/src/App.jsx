export default function App() {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: '100%',
      height: '100%',
      flexDirection: 'column',
      gap: '12px',
    }}>
      <h1 style={{ fontSize: '2rem', fontWeight: 700, letterSpacing: '-0.5px' }}>
        GeoNews
      </h1>
      <p style={{ color: '#6b7280', fontSize: '1rem' }}>
        Real-time geospatial news aggregator
      </p>
    </div>
  )
}
