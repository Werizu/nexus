import { Cpu, Thermometer, HardDrive, Clock } from 'lucide-react'
import StatusBadge from './StatusBadge'

function MetricBar({ label, value, max = 100, unit = '%', color = 'bg-cyan-400' }) {
  const pct = Math.min((value / max) * 100, 100)
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-500">{label}</span>
        <span className="text-white font-mono">{value}{unit}</span>
      </div>
      <div className="h-1.5 bg-[#1e1e2e] rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function formatUptime(seconds) {
  if (!seconds) return '-'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

export default function PiMonitor({ pi }) {
  const state = pi.state || {}
  const online = state.online

  return (
    <div className="bg-[#12121a] border border-[#1e1e2e] rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
            <Cpu size={20} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">{pi.name}</h3>
            <p className="text-xs text-gray-500 font-mono">{pi.hostname}</p>
          </div>
        </div>
        <StatusBadge online={online} />
      </div>

      {online ? (
        <div className="space-y-3">
          <MetricBar
            label="CPU"
            value={state.cpu || 0}
            color={state.cpu > 80 ? 'bg-red-400' : state.cpu > 50 ? 'bg-orange-400' : 'bg-cyan-400'}
          />
          <MetricBar
            label="RAM"
            value={state.ram || 0}
            color={state.ram > 80 ? 'bg-red-400' : state.ram > 50 ? 'bg-orange-400' : 'bg-emerald-400'}
          />
          {state.disk !== undefined && (
            <MetricBar label="Disk" value={state.disk} color="bg-purple-400" />
          )}
          <div className="flex gap-3 mt-2 text-xs">
            <div className="flex items-center gap-1.5 text-gray-400">
              <Thermometer size={12} />
              <span className="font-mono text-white">{state.temp || '-'}°C</span>
            </div>
            <div className="flex items-center gap-1.5 text-gray-400">
              <Clock size={12} />
              <span className="font-mono text-white">{formatUptime(state.uptime)}</span>
            </div>
          </div>
        </div>
      ) : (
        <p className="text-xs text-gray-500">Nicht erreichbar</p>
      )}
    </div>
  )
}
