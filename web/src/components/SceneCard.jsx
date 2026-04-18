import { useState } from 'react'
import { Play, Code, Sun, Film, Moon, DoorOpen, PowerOff, Home, Music, Coffee, Pencil, Trash2 } from 'lucide-react'

const SCENE_ICONS = {
  code: Code,
  sunrise: Sun,
  sun: Sun,
  film: Film,
  moon: Moon,
  'door-open': DoorOpen,
  'power-off': PowerOff,
  home: Home,
  music: Music,
  coffee: Coffee,
}

export default function SceneCard({ scene, onTrigger, onEdit, onDelete }) {
  const [running, setRunning] = useState(false)
  const Icon = SCENE_ICONS[scene.icon] || Play
  const color = scene.color || '#00D4FF'

  const handleTrigger = async () => {
    setRunning(true)
    try {
      await onTrigger(scene.name)
    } finally {
      setTimeout(() => setRunning(false), 2000)
    }
  }

  return (
    <div
      className="bg-[#12121a] border border-[#1e1e2e] rounded-xl p-4 hover:border-opacity-50 transition-all group"
      style={{ '--scene-color': color }}
    >
      <div className="flex items-center gap-3">
        <button
          onClick={handleTrigger}
          disabled={running}
          className="p-2.5 rounded-lg cursor-pointer transition-transform hover:scale-105 disabled:opacity-50"
          style={{ background: `${color}15`, color }}
        >
          <Icon size={22} className={running ? 'animate-spin' : ''} />
        </button>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-white truncate">{scene.display_name}</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            {scene.actions?.length || 0} Aktionen
          </p>
        </div>
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {onEdit && (
            <button
              onClick={() => onEdit(scene)}
              className="p-1.5 text-gray-500 hover:text-white cursor-pointer rounded hover:bg-[#1e1e2e] transition-colors"
            >
              <Pencil size={14} />
            </button>
          )}
          {onDelete && (
            <button
              onClick={() => onDelete(scene.name)}
              className="p-1.5 text-gray-500 hover:text-red-400 cursor-pointer rounded hover:bg-[#1e1e2e] transition-colors"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
        <button
          onClick={handleTrigger}
          disabled={running}
          className="cursor-pointer disabled:opacity-50"
        >
          <Play size={16} className={`text-gray-500 hover:text-white transition-colors ${running ? 'animate-spin' : ''}`} />
        </button>
      </div>
    </div>
  )
}
