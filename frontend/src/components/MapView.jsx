import { useEffect, useRef } from 'react'
import mapboxgl from 'mapbox-gl'

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN

export default function MapView() {
  const containerRef = useRef(null)

  useEffect(() => {
    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: 'mapbox://styles/mapbox/dark-v11',
      center: [0, 20],
      zoom: 2.5,
      projection: 'globe',
    })

    map.on('style.load', () => {
      // Atmospheric fog for globe effect
      map.setFog({
        color: 'rgb(8,8,8)',
        'high-color': 'rgb(15,15,25)',
        'horizon-blend': 0.04,
      })
    })

    map.addControl(
      new mapboxgl.NavigationControl({ showCompass: false }),
      'bottom-right'
    )

    return () => map.remove()
  }, [])

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
