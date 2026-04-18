import { useState, useEffect, useCallback, useRef } from 'react'

const API_BASE = '/api/v1'

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export function useDevices() {
  const [devices, setDevices] = useState([])
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      const data = await api('/devices')
      setDevices(data)
    } catch (e) {
      console.error('Failed to load devices:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const sendCommand = useCallback(async (deviceId, command, params = {}) => {
    await api(`/devices/${deviceId}/command`, {
      method: 'POST',
      body: JSON.stringify({ command, params }),
    })
    await refresh()
  }, [refresh])

  return { devices, loading, refresh, sendCommand }
}

export function useScenes() {
  const [scenes, setScenes] = useState([])

  useEffect(() => {
    api('/scenes').then(setScenes).catch(console.error)
  }, [])

  const trigger = useCallback(async (sceneName) => {
    return api(`/scenes/${sceneName}/trigger`, { method: 'POST', body: '{}' })
  }, [])

  return { scenes, trigger }
}

export function useHealth() {
  const [health, setHealth] = useState(null)

  const refresh = useCallback(async () => {
    try {
      setHealth(await api('/health'))
    } catch (e) {
      setHealth({ status: 'error', error: e.message })
    }
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 10000)
    return () => clearInterval(interval)
  }, [refresh])

  return health
}

export function usePis() {
  const [pis, setPis] = useState([])

  const refresh = useCallback(async () => {
    try {
      setPis(await api('/pis'))
    } catch (e) {
      console.error('Failed to load pis:', e)
    }
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 15000)
    return () => clearInterval(interval)
  }, [refresh])

  return { pis, refresh }
}

export function useLogs() {
  const [logs, setLogs] = useState([])

  const refresh = useCallback(async () => {
    try {
      setLogs(await api('/logs?limit=50'))
    } catch (e) {
      console.error('Failed to load logs:', e)
    }
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 5000)
    return () => clearInterval(interval)
  }, [refresh])

  return { logs, refresh }
}

export function useWebSocket(onMessage) {
  const wsRef = useRef(null)

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const ws = new WebSocket(`${protocol}//${host}/ws/realtime`)

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage?.(data)
      } catch (e) {
        console.error('WS parse error:', e)
      }
    }

    ws.onopen = () => console.log('WebSocket connected')
    ws.onclose = () => {
      console.log('WebSocket disconnected, reconnecting...')
      setTimeout(() => wsRef.current = null, 3000)
    }

    wsRef.current = ws
    return () => ws.close()
  }, [onMessage])
}
