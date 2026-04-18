import { Monitor, Cpu, Camera, Speaker, Lightbulb, Plug, Power, PowerOff, RotateCcw } from 'lucide-react'
import StatusBadge from './StatusBadge'

const CATEGORY_ICONS = {
  computers: Monitor,
  pis: Cpu,
  cameras: Camera,
  speakers: Speaker,
  lights: Lightbulb,
  plugs: Plug,
}

const CATEGORY_COLORS = {
  computers: 'text-blue-400',
  pis: 'text-cyan-400',
  cameras: 'text-purple-400',
  speakers: 'text-orange-400',
  lights: 'text-yellow-400',
  plugs: 'text-green-400',
}

export default function DeviceCard({ device, onCommand }) {
  const Icon = CATEGORY_ICONS[device.category] || Cpu
  const color = CATEGORY_COLORS[device.category] || 'text-gray-400'
  const state = device.state || {}
  const isOn = state.on || state.online
  const ip = device.config?.ip || device.config?.hostname || ''

  return (
    <div className="bg-[#12121a] border border-[#1e1e2e] rounded-xl p-4 hover:border-[#00D4FF]/30 transition-all">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg bg-[#1e1e2e] ${color}`}>
            <Icon size={20} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">{device.name}</h3>
            <p className="text-xs text-gray-500 font-mono">{ip}</p>
          </div>
        </div>
        <StatusBadge online={isOn} />
      </div>

      {/* State details */}
      {state.cpu !== undefined && (
        <div className="grid grid-cols-3 gap-2 mt-3 text-xs">
          <div className="bg-[#1e1e2e] rounded-lg p-2 text-center">
            <div className="text-gray-500">CPU</div>
            <div className="text-white font-mono">{state.cpu}%</div>
          </div>
          <div className="bg-[#1e1e2e] rounded-lg p-2 text-center">
            <div className="text-gray-500">RAM</div>
            <div className="text-white font-mono">{state.ram}%</div>
          </div>
          <div className="bg-[#1e1e2e] rounded-lg p-2 text-center">
            <div className="text-gray-500">{state.temp !== undefined ? 'Temp' : 'Disk'}</div>
            <div className="text-white font-mono">{state.temp !== undefined ? `${state.temp}°` : `${state.disk}%`}</div>
          </div>
        </div>
      )}

      {state.gpu && (
        <div className="grid grid-cols-3 gap-2 mt-2 text-xs">
          <div className="bg-[#1e1e2e] rounded-lg p-2 text-center col-span-2">
            <div className="text-gray-500">GPU</div>
            <div className="text-white font-mono text-[10px] truncate">{state.gpu.name}</div>
          </div>
          <div className="bg-[#1e1e2e] rounded-lg p-2 text-center">
            <div className="text-gray-500">GPU</div>
            <div className="text-white font-mono">{state.gpu.load}%</div>
          </div>
        </div>
      )}

      {state.energy && (
        <div className="mt-3 bg-[#1e1e2e] rounded-lg p-2 text-xs">
          <span className="text-gray-500">Verbrauch: </span>
          <span className="text-white font-mono">{state.energy.power_w}W</span>
          <span className="text-gray-500 ml-2">Heute: </span>
          <span className="text-white font-mono">{state.energy.today_kwh} kWh</span>
        </div>
      )}

      {/* Action buttons */}
      {device.plugin && (
        <div className="flex gap-2 mt-3">
          {device.category === 'computers' && !state.online && (
            <button
              onClick={() => onCommand(device.device_id, 'wake')}
              className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-xs text-emerald-400 transition-all cursor-pointer"
            >
              <Power size={12} /> Wake
            </button>
          )}
          {device.category === 'computers' && state.online && (
            <>
              <button
                onClick={() => { if (confirm('PC herunterfahren?')) onCommand(device.device_id, 'shutdown') }}
                className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-red-500/15 hover:bg-red-500/25 text-xs text-red-400 transition-all cursor-pointer"
              >
                <PowerOff size={12} /> Shutdown
              </button>
              <button
                onClick={() => { if (confirm('PC neustarten?')) onCommand(device.device_id, 'restart') }}
                className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg bg-orange-500/15 hover:bg-orange-500/25 text-xs text-orange-400 transition-all cursor-pointer"
              >
                <RotateCcw size={12} /> Restart
              </button>
            </>
          )}
          {(device.category === 'lights' || device.category === 'plugs') && (
            <>
              <button
                onClick={() => onCommand(device.device_id, 'on')}
                className="flex-1 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-xs text-emerald-400 transition-all cursor-pointer"
              >
                On
              </button>
              <button
                onClick={() => onCommand(device.device_id, 'off')}
                className="flex-1 py-1.5 rounded-lg bg-red-500/15 hover:bg-red-500/25 text-xs text-red-400 transition-all cursor-pointer"
              >
                Off
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
