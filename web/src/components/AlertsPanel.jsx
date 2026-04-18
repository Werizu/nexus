import { AlertTriangle, CheckCheck, X, Cpu, HardDrive, Thermometer, Gauge } from 'lucide-react'

const ALERT_ICONS = {
  cpu: Gauge,
  ram: Gauge,
  disk: HardDrive,
  gpu_temp: Thermometer,
  gpu_load: Cpu,
}

const SEVERITY_STYLES = {
  critical: 'border-red-500/40 bg-red-500/10',
  warning: 'border-yellow-500/40 bg-yellow-500/10',
}

const SEVERITY_BADGE = {
  critical: 'bg-red-500/20 text-red-400',
  warning: 'bg-yellow-500/20 text-yellow-400',
}

function timeAgo(timestamp) {
  const diff = Date.now() / 1000 - timestamp
  if (diff < 60) return 'gerade eben'
  if (diff < 3600) return `vor ${Math.floor(diff / 60)} Min`
  if (diff < 86400) return `vor ${Math.floor(diff / 3600)} Std`
  return `vor ${Math.floor(diff / 86400)} Tagen`
}

export default function AlertsPanel({ alerts, onAcknowledge, onAcknowledgeAll }) {
  const unacked = alerts.filter(a => !a.acknowledged)
  const acked = alerts.filter(a => a.acknowledged)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle size={18} className="text-yellow-400" />
          <h2 className="text-sm font-semibold text-white">
            Alerts {unacked.length > 0 && <span className="text-yellow-400">({unacked.length})</span>}
          </h2>
        </div>
        {unacked.length > 0 && (
          <button
            onClick={onAcknowledgeAll}
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-[#1e1e2e] hover:bg-[#2a2a3e] text-xs text-gray-400 hover:text-white transition-all cursor-pointer"
          >
            <CheckCheck size={14} /> Alle bestätigen
          </button>
        )}
      </div>

      {alerts.length === 0 && (
        <div className="text-center py-8 text-gray-500 text-sm">
          Keine Alerts vorhanden
        </div>
      )}

      {unacked.length > 0 && (
        <div className="space-y-2">
          {unacked.map(alert => (
            <AlertItem key={alert.id} alert={alert} onAcknowledge={onAcknowledge} />
          ))}
        </div>
      )}

      {acked.length > 0 && (
        <div className="space-y-2 mt-4">
          <div className="text-xs text-gray-500 uppercase tracking-wider">Bestätigt</div>
          {acked.map(alert => (
            <AlertItem key={alert.id} alert={alert} acknowledged />
          ))}
        </div>
      )}
    </div>
  )
}

function AlertItem({ alert, onAcknowledge, acknowledged }) {
  const Icon = ALERT_ICONS[alert.type] || AlertTriangle
  const severityStyle = SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.warning
  const badgeStyle = SEVERITY_BADGE[alert.severity] || SEVERITY_BADGE.warning

  return (
    <div className={`border rounded-xl p-3 flex items-start gap-3 ${acknowledged ? 'border-[#1e1e2e] bg-[#12121a] opacity-60' : severityStyle}`}>
      <div className={`p-1.5 rounded-lg ${badgeStyle}`}>
        <Icon size={16} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm text-white font-medium">{alert.message}</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${badgeStyle}`}>
            {alert.severity}
          </span>
        </div>
        <div className="text-xs text-gray-500 mt-0.5">
          {alert.device_id} · {timeAgo(alert.timestamp)}
        </div>
      </div>
      {!acknowledged && onAcknowledge && (
        <button
          onClick={() => onAcknowledge(alert.id)}
          className="p-1 rounded-lg hover:bg-white/10 text-gray-500 hover:text-white transition-all cursor-pointer"
        >
          <X size={14} />
        </button>
      )}
    </div>
  )
}
