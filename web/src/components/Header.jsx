import { Wifi, WifiOff, LogOut, Settings } from 'lucide-react'

export default function Header({ health, user, onLogout, onSettings }) {
  const ok = health?.status === 'ok'
  const mqtt = health?.mqtt_connected
  const deviceCount = health?.devices_registered || 0
  const pluginCount = health?.plugins ? Object.keys(health.plugins).length : 0

  return (
    <header className="border-b border-[#1e1e2e] bg-[#0a0a0f]/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#00D4FF] to-[#0066FF] flex items-center justify-center">
            <span className="text-white font-bold text-sm">N</span>
          </div>
          <div>
            <h1 className="text-lg font-bold text-white tracking-tight">NEXUS</h1>
            <p className="text-[10px] text-gray-500 -mt-0.5">Smart Home Control</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-gray-500">{deviceCount} Geräte</span>
            <span className="text-gray-600">|</span>
            <span className="text-gray-500">{pluginCount} Plugins</span>
          </div>

          <div className="flex items-center gap-2">
            {mqtt ? (
              <Wifi size={14} className="text-emerald-400" />
            ) : (
              <WifiOff size={14} className="text-red-400" />
            )}
            <div className={`w-2 h-2 rounded-full ${ok ? 'bg-emerald-400' : 'bg-red-400'}`} />
          </div>

          {user && (
            <div className="flex items-center gap-2 ml-2 pl-2 border-l border-[#1e1e2e]">
              <span className="text-xs text-gray-400">{user.display_name}</span>
              <button onClick={onSettings} className="text-gray-500 hover:text-gray-300 cursor-pointer" title="Einstellungen">
                <Settings size={14} />
              </button>
              <button onClick={onLogout} className="text-gray-500 hover:text-red-400 cursor-pointer" title="Abmelden">
                <LogOut size={14} />
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
