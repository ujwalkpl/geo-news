import { useEffect, useRef } from 'react'

/**
 * Connects to the GeoNews WebSocket server and calls onMessage for each
 * non-ping event. Automatically reconnects on disconnect.
 *
 * @param {string|null} url      - WebSocket URL (wss://...). Pass null to disable.
 * @param {function}    onMessage - Called with parsed JSON payload on each message.
 */
export function useWebSocket(url, onMessage) {
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  useEffect(() => {
    if (!url) return

    let ws = null
    let reconnectTimer = null
    let destroyed = false

    function connect() {
      ws = new WebSocket(url)

      ws.onopen = () => {
        console.log('[WS] connected to', url)
      }

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          if (data.type === 'ping') return   // server keepalive — ignore
          onMessageRef.current(data)
        } catch {
          // malformed JSON — ignore
        }
      }

      ws.onclose = (e) => {
        if (destroyed) return
        console.log('[WS] disconnected, reconnecting in 3s…', e.code)
        reconnectTimer = setTimeout(connect, 3000)
      }

      ws.onerror = () => {
        ws.close()   // onclose will handle reconnect
      }
    }

    connect()

    return () => {
      destroyed = true
      clearTimeout(reconnectTimer)
      ws?.close()
    }
  }, [url])
}
