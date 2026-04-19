import { useEffect, useRef } from 'react'
import mapboxgl from 'mapbox-gl'
import { MOCK_ARTICLES } from '../api/mockArticles'

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN

const CAT_COLORS = {
  Politics:      '#ef4444',
  Technology:    '#3b82f6',
  AI:            '#8b5cf6',
  Finance:       '#10b981',
  Health:        '#f59e0b',
  Sports:        '#f97316',
  Entertainment: '#ec4899',
  General:       '#6b7280',
}

function toGeoJSON(articles) {
  // Group articles at the same location into one feature
  const groups = {}
  articles.forEach(a => {
    if (a.lat == null || a.lng == null) return
    const key = `${parseFloat(a.lat).toFixed(2)},${parseFloat(a.lng).toFixed(2)}`
    if (!groups[key]) groups[key] = []
    groups[key].push(a)
  })

  return {
    type: 'FeatureCollection',
    features: Object.values(groups).map(group => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [group[0].lng, group[0].lat] },
      properties: {
        count: group.length,
        color: CAT_COLORS[group[0].category] || '#6b7280',
        group: JSON.stringify(group),
      },
    })),
  }
}

export default function MapView({ category, onArticleClick }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const onArticleClickRef = useRef(onArticleClick)
  onArticleClickRef.current = onArticleClick

  useEffect(() => {
    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: 'mapbox://styles/mapbox/dark-v11',
      center: [0, 20],
      zoom: 2.5,
      projection: 'globe',
    })
    mapRef.current = map

    map.on('style.load', () => {
      map.setFog({
        color: 'rgb(8,8,8)',
        'high-color': 'rgb(15,15,25)',
        'horizon-blend': 0.04,
      })

      // Filter articles by category if one is selected
      const filtered = category
        ? MOCK_ARTICLES.filter(a => a.category === category)
        : MOCK_ARTICLES

      map.addSource('articles', {
        type: 'geojson',
        data: toGeoJSON(filtered),
      })

      // Soft glow halo
      map.addLayer({
        id: 'articles-halo',
        type: 'circle',
        source: 'articles',
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['get', 'count'], 1, 24, 10, 34],
          'circle-color': ['get', 'color'],
          'circle-opacity': 0.2,
          'circle-blur': 0.8,
        },
      })

      // Main dot
      map.addLayer({
        id: 'articles-dot',
        type: 'circle',
        source: 'articles',
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['get', 'count'], 1, 13, 10, 21],
          'circle-color': ['get', 'color'],
          'circle-blur': 0.3,
        },
      })

      // Count label for grouped dots
      map.addLayer({
        id: 'articles-label',
        type: 'symbol',
        source: 'articles',
        filter: ['>', ['get', 'count'], 1],
        layout: {
          'text-field': ['to-string', ['get', 'count']],
          'text-size': 11,
          'text-font': ['DIN Pro Bold', 'Arial Unicode MS Bold'],
          'text-allow-overlap': true,
          'text-ignore-placement': true,
        },
        paint: { 'text-color': '#ffffff' },
      })

      // Click handler
      map.on('click', 'articles-dot', e => {
        if (!e.features.length) return
        const group = JSON.parse(e.features[0].properties.group)
        onArticleClickRef.current(group)
      })
      map.on('mouseenter', 'articles-dot', () => { map.getCanvas().style.cursor = 'pointer' })
      map.on('mouseleave', 'articles-dot', () => { map.getCanvas().style.cursor = '' })
    })

    map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), 'bottom-right')

    return () => map.remove()
  }, [category])  // re-render when category filter changes

  return (
    <>
      <style>{`
        .mapboxgl-ctrl-bottom-right { bottom: 80px !important; right: 16px !important; }
        .mapboxgl-ctrl-group { background: rgba(0,0,0,0.7) !important; border: 1px solid rgba(255,255,255,0.1) !important; }
        .mapboxgl-ctrl-group button { background: transparent !important; color: #fff !important; }
        .mapboxgl-ctrl-logo { display: none !important; }
        .mapboxgl-ctrl-attrib { display: none !important; }
      `}</style>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />
    </>
  )
}
