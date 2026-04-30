import { useState, useEffect, useCallback, useRef } from 'react'

const API_BASE = '/api/v1'

function getToken() {
  return localStorage.getItem('nexus_token')
}

async function api(path, options = {}) {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${API_BASE}${path}`, { headers, ...options })
  if (res.status === 401) {
    localStorage.removeItem('nexus_token')
    localStorage.removeItem('nexus_user')
    window.location.reload()
    throw new Error('Session expired')
  }
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

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 10000)
    return () => clearInterval(interval)
  }, [refresh])

  const sendCommand = useCallback(async (deviceId, command, params = {}) => {
    await api(`/devices/${deviceId}/command`, {
      method: 'POST',
      body: JSON.stringify({ command, params }),
    })
    await refresh()
  }, [refresh])

  const saveDevice = useCallback(async (deviceData, isNew = false) => {
    if (isNew) {
      await api('/devices', { method: 'POST', body: JSON.stringify(deviceData) })
    } else {
      await api(`/devices/${deviceData.id}`, { method: 'PUT', body: JSON.stringify(deviceData) })
    }
    await refresh()
  }, [refresh])

  const deleteDevice = useCallback(async (deviceId) => {
    await api(`/devices/${deviceId}`, { method: 'DELETE' })
    await refresh()
  }, [refresh])

  return { devices, loading, refresh, sendCommand, saveDevice, deleteDevice }
}

export function useScenes() {
  const [scenes, setScenes] = useState([])

  const refresh = useCallback(async () => {
    try {
      setScenes(await api('/scenes'))
    } catch (e) {
      console.error('Failed to load scenes:', e)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const trigger = useCallback(async (sceneName) => {
    return api(`/scenes/${sceneName}/trigger`, { method: 'POST', body: '{}' })
  }, [])

  const saveScene = useCallback(async (sceneData, originalName) => {
    if (originalName && originalName !== sceneData.name) {
      await api(`/scenes/${originalName}`, { method: 'DELETE' })
    }
    const method = originalName ? 'PUT' : 'POST'
    const path = originalName && originalName === sceneData.name
      ? `/scenes/${sceneData.name}`
      : '/scenes'
    const result = await api(path, { method, body: JSON.stringify(sceneData) })
    await refresh()
    return result
  }, [refresh])

  const deleteScene = useCallback(async (sceneName) => {
    const result = await api(`/scenes/${sceneName}`, { method: 'DELETE' })
    await refresh()
    return result
  }, [refresh])

  return { scenes, trigger, saveScene, deleteScene, refresh }
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

export function useAlerts() {
  const [alerts, setAlerts] = useState([])

  const refresh = useCallback(async () => {
    try {
      setAlerts(await api('/alerts?limit=50'))
    } catch (e) {
      console.error('Failed to load alerts:', e)
    }
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 10000)
    return () => clearInterval(interval)
  }, [refresh])

  const acknowledge = useCallback(async (alertId) => {
    await api(`/alerts/${alertId}/ack`, { method: 'POST' })
    await refresh()
  }, [refresh])

  const acknowledgeAll = useCallback(async () => {
    await api('/alerts/ack-all', { method: 'POST' })
    await refresh()
  }, [refresh])

  const unackedCount = alerts.filter(a => !a.acknowledged).length

  return { alerts, refresh, acknowledge, acknowledgeAll, unackedCount }
}

export function useRooms() {
  const [rooms, setRooms] = useState({})

  const refresh = useCallback(async () => {
    try {
      setRooms(await api('/rooms'))
    } catch (e) {
      console.error('Failed to load rooms:', e)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const saveRoom = useCallback(async (roomId, roomData) => {
    const exists = rooms[roomId]
    if (exists) {
      await api(`/rooms/${roomId}`, { method: 'PUT', body: JSON.stringify(roomData) })
    } else {
      await api('/rooms', { method: 'POST', body: JSON.stringify({ id: roomId, ...roomData }) })
    }
    await refresh()
  }, [rooms, refresh])

  const deleteRoom = useCallback(async (roomId) => {
    await api(`/rooms/${roomId}`, { method: 'DELETE' })
    await refresh()
  }, [refresh])

  return { rooms, refresh, saveRoom, deleteRoom }
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
