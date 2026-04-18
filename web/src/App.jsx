import { useState, useCallback } from 'react'
import Header from './components/Header'
import DeviceCard from './components/DeviceCard'
import SceneCard from './components/SceneCard'
import PiMonitor from './components/PiMonitor'
import LogViewer from './components/LogViewer'
import { useDevices, useScenes, useHealth, usePis, useWebSocket, useLogs } from './hooks/useNexus'

function App() {
  const { devices, loading, refresh, sendCommand } = useDevices()
  const { scenes, trigger } = useScenes()
  const health = useHealth()
  const { pis } = usePis()
  const { logs } = useLogs()
  const [activeTab, setActiveTab] = useState('dashboard')

  const handleWsMessage = useCallback((data) => {
    if (data.event === 'device_update' || data.event === 'scene_complete') {
      refresh()
    }
  }, [refresh])

  useWebSocket(handleWsMessage)

  const categories = devices.reduce((acc, d) => {
    const cat = d.category || 'other'
    if (!acc[cat]) acc[cat] = []
    acc[cat].push(d)
    return acc
  }, {})

  const CATEGORY_LABELS = {
    computers: 'Computer',
    pis: 'Raspberry Pis',
    cameras: 'Kameras',
    speakers: 'Lautsprecher',
    lights: 'Lichter',
    plugs: 'Steckdosen',
  }

  const tabs = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'devices', label: 'Geräte' },
    { id: 'scenes', label: 'Szenen' },
    { id: 'pis', label: 'Pi Monitor' },
    { id: 'logs', label: 'Logs' },
  ]

  return (
    <div className="min-h-screen">
      <Header health={health} />

      {/* Tab Navigation */}
      <nav className="border-b border-[#1e1e2e] bg-[#0a0a0f]">
        <div className="max-w-7xl mx-auto px-6 flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 text-sm font-medium transition-all cursor-pointer border-b-2 ${
                activeTab === tab.id
                  ? 'text-[#00D4FF] border-[#00D4FF]'
                  : 'text-gray-500 border-transparent hover:text-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-8 h-8 border-2 border-[#00D4FF] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {/* Dashboard */}
            {activeTab === 'dashboard' && (
              <div className="space-y-8">
                {/* Quick Scenes */}
                <section>
                  <h2 className="text-lg font-semibold text-white mb-4">Szenen</h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {scenes.map((scene) => (
                      <SceneCard key={scene.name} scene={scene} onTrigger={trigger} />
                    ))}
                  </div>
                </section>

                {/* All Devices */}
                <section>
                  <h2 className="text-lg font-semibold text-white mb-4">Geräte</h2>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                    {devices.map((device) => (
                      <DeviceCard key={device.device_id} device={device} onCommand={sendCommand} />
                    ))}
                  </div>
                </section>

                {/* Pi Status */}
                {pis.length > 0 && (
                  <section>
                    <h2 className="text-lg font-semibold text-white mb-4">Pi Status</h2>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      {pis.map((pi) => (
                        <PiMonitor key={pi.id} pi={pi} />
                      ))}
                    </div>
                  </section>
                )}
              </div>
            )}

            {/* Devices Tab */}
            {activeTab === 'devices' && (
              <div className="space-y-8">
                {Object.entries(categories).map(([cat, devs]) => (
                  <section key={cat}>
                    <h2 className="text-lg font-semibold text-white mb-4">
                      {CATEGORY_LABELS[cat] || cat}
                      <span className="text-gray-500 text-sm font-normal ml-2">({devs.length})</span>
                    </h2>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                      {devs.map((device) => (
                        <DeviceCard key={device.device_id} device={device} onCommand={sendCommand} />
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            )}

            {/* Scenes Tab */}
            {activeTab === 'scenes' && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {scenes.map((scene) => (
                  <SceneCard key={scene.name} scene={scene} onTrigger={trigger} />
                ))}
              </div>
            )}

            {/* Pi Monitor Tab */}
            {activeTab === 'pis' && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {pis.map((pi) => (
                  <PiMonitor key={pi.id} pi={pi} />
                ))}
                {pis.length === 0 && (
                  <p className="text-gray-500 text-sm">Keine Pis gefunden</p>
                )}
              </div>
            )}

            {/* Logs Tab */}
            {activeTab === 'logs' && (
              <LogViewer logs={logs} />
            )}
          </>
        )}
      </main>
    </div>
  )
}

export default App
