import { useEffect, useRef } from 'react'
import mapboxgl from 'mapbox-gl'
import { fetchMapArticles } from '../api/newsApi'
import { useWebSocket } from '../hooks/useWebSocket'

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN

const WS_URL = import.meta.env.VITE_WS_URL || null

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

function articleColor(category) {
  return CAT_COLORS[category] || '#6b7280'
}

/**
 * Group articles by ~0.01° grid cell so nearby articles share a dot.
 * Returns a Mapbox GeoJSON FeatureCollection.
 */
function toGeoJSON(articles) {
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
        color: articleColor(group[0].category),
        group: JSON.stringify(group),
      },
    })),
  }
}

function getBbox(map) {
  const b = map.getBounds()
  return `${b.getSouth()},${b.getWest()},${b.getNorth()},${b.getEast()}`
}

export default function MapView({ category, onArticleClick }) {
  const containerRef  = useRef(null)
  const mapRef        = useRef(null)
  const articlesRef   = useRef([])   // master list — updated by both REST fetch and WS
  const onArticleClickRef = useRef(onArticleClick)
  onArticleClickRef.current = onArticleClick

  // ── Helpers ────────────────────────────────────────────────────────────────

  function pushToMap(newArticles) {
    const map = mapRef.current
    if (!map) return
    const source = map.getSource('articles')
    if (!source) return

    // Merge: deduplicate by article_id, new articles win
    const existing = articlesRef.current
    const existingIds = new Set(existing.map(a => a.article_id))
    const merged = [
      ...existing,
      ...newArticles.filter(a => !existingIds.has(a.article_id)),
    ]
    articlesRef.current = merged
    source.setData(toGeoJSON(merged))
  }

  async function loadArticles(map) {
    try {
      const bbox = getBbox(map)
      const articles = await fetchMapArticles({ bbox, category: category || 'all' })
      // Replace viewport articles but keep any WS-injected articles outside viewport
      const inViewIds = new Set(articles.map(a => a.article_id))
      const outOfView = articlesRef.current.filter(a => !inViewIds.has(a.article_id))
      articlesRef.current = [...articles, ...outOfView]
      const source = map.getSource('articles')
      if (source) source.setData(toGeoJSON(articlesRef.current))
    } catch (err) {
      console.error('Failed to load articles:', err)
    }
  }

  // ── WebSocket: inject new articles as they arrive ─────────────────────────

  useWebSocket(WS_URL, (msg) => {
    if (msg.type !== 'new_article') return
    const { article_id, lat, lng, category: cat, title, score, image_url } = msg
    if (lat == null || lng == null) return

    // Skip if category filter is active and doesn't match
    if (category && category !== 'all' && cat !== category) return

    console.log('[WS] new article:', title)
    pushToMap([{ article_id, lat, lng, category: cat, title, score, image_url }])
  })

  // ── Map initialisation ────────────────────────────────────────────────────

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

      map.addSource('articles', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      })

      // Soft glow halo
      map.addLayer({
        id: 'articles-halo',
        type: 'circle',
        source: 'articles',
        paint: {
          'circle-radius':  ['interpolate', ['linear'], ['get', 'count'], 1, 24, 10, 34],
          'circle-color':   ['get', 'color'],
          'circle-opacity': 0.2,
          'circle-blur':    0.8,
        },
      })

      // Main dot
      map.addLayer({
        id: 'articles-dot',
        type: 'circle',
        source: 'articles',
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['get', 'count'], 1, 13, 10, 21],
          'circle-color':  ['get', 'color'],
          'circle-blur':   0.3,
        },
      })

      // Count badge for grouped dots
      map.addLayer({
        id: 'articles-label',
        type: 'symbol',
        source: 'articles',
        filter: ['>', ['get', 'count'], 1],
        layout: {
          'text-field':              ['to-string', ['get', 'count']],
          'text-size':               11,
          'text-font':               ['DIN Pro Bold', 'Arial Unicode MS Bold'],
          'text-allow-overlap':      true,
          'text-ignore-placement':   true,
        },
        paint: { 'text-color': '#ffffff' },
      })

      // Click → open sidebar
      map.on('click', 'articles-dot', e => {
        if (!e.features.length) return
        const group = JSON.parse(e.features[0].properties.group)
        onArticleClickRef.current(group)
      })
      map.on('mouseenter', 'articles-dot', () => { map.getCanvas().style.cursor = 'pointer' })
      map.on('mouseleave', 'articles-dot', () => { map.getCanvas().style.cursor = '' })

      loadArticles(map)
      map.on('moveend', () => loadArticles(map))
    })

    map.addControl(new mapboxgl.NavigationControl({ showCompass: false }), 'bottom-right')

    return () => map.remove()
  }, [])

  // Re-fetch when category filter changes
  useEffect(() => {
    if (mapRef.current) loadArticles(mapRef.current)
  }, [category])

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
