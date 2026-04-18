import { AlertCircle, Info, AlertTriangle, Bug } from 'lucide-react'

const LEVEL_CONFIG = {
  error:   { icon: AlertCircle,   color: 'text-red-400',    bg: 'bg-red-500/10' },
  warning: { icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-500/10' },
  info:    { icon: Info,          color: 'text-blue-400',   bg: 'bg-blue-500/10' },
  debug:   { icon: Bug,           color: 'text-gray-400',   bg: 'bg-gray-500/10' },
}

function formatTime(ts) {
  return new Date(ts * 1000).toLocaleTimeString('de-DE', {
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  })
}

export default function LogViewer({ logs }) {
  return (
    <div className="space-y-1">
      {logs.length === 0 && (
        <p className="text-gray-500 text-sm">Keine Logs vorhanden</p>
      )}
      {logs.map((log) => {
        const cfg = LEVEL_CONFIG[log.level] || LEVEL_CONFIG.info
        const Icon = cfg.icon
        return (
          <div key={log.id} className={`flex items-start gap-3 p-3 rounded-lg ${cfg.bg}`}>
            <Icon size={14} className={`mt-0.5 ${cfg.color}`} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 font-mono">{formatTime(log.timestamp)}</span>
                {log.device && (
                  <span className="text-xs text-gray-400 font-mono">[{log.device}]</span>
                )}
              </div>
              <p className="text-sm text-white mt-0.5">{log.message}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}
