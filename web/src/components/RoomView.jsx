import { Monitor, Sofa, Bed } from 'lucide-react'
import DeviceCard from './DeviceCard'

const ROOM_ICONS = {
  monitor: Monitor,
  sofa: Sofa,
  bed: Bed,
}

export default function RoomView({ rooms, onCommand }) {
  const entries = Object.entries(rooms)

  if (entries.length === 0) {
    return <p className="text-gray-500 text-sm">Keine Räume konfiguriert</p>
  }

  return (
    <div className="space-y-8">
      {entries.map(([roomId, room]) => {
        const Icon = ROOM_ICONS[room.icon] || Monitor
        const devices = room.device_states || []

        return (
          <section key={roomId}>
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 rounded-lg bg-[#1e1e2e] text-[#00D4FF]">
                <Icon size={20} />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">{room.name}</h2>
                <p className="text-xs text-gray-500">{devices.length} Geräte</p>
              </div>
            </div>
            {devices.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {devices.map((device) => (
                  <DeviceCard key={device.device_id} device={device} onCommand={onCommand} />
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-sm ml-11">Keine Geräte in diesem Raum</p>
            )}
          </section>
        )
      })}
    </div>
  )
}
