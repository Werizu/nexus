import { useState, useEffect } from 'react'
import { X } from 'lucide-react'

const ROOM_ICONS = [
  { value: 'monitor', label: 'Büro' },
  { value: 'sofa', label: 'Wohnzimmer' },
  { value: 'bed', label: 'Schlafzimmer' },
  { value: 'utensils', label: 'Küche' },
  { value: 'bath', label: 'Bad' },
  { value: 'door-open', label: 'Flur' },
  { value: 'warehouse', label: 'Garage' },
  { value: 'tree', label: 'Garten' },
  { value: 'home', label: 'Haus' },
  { value: 'server', label: 'Server' },
]

export default function RoomEditor({ room, roomId, allDevices = [], onSave, onClose }) {
  const isEdit = !!roomId

  const [id, setId] = useState('')
  const [name, setName] = useState('')
  const [icon, setIcon] = useState('monitor')
  const [selectedDevices, setSelectedDevices] = useState([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (room && roomId) {
      setId(roomId)
      setName(room.name || '')
      setIcon(room.icon || 'monitor')
      setSelectedDevices(room.devices || [])
    }
  }, [room, roomId])

  const toggleDevice = (deviceId) => {
    setSelectedDevices(prev =>
      prev.includes(deviceId) ? prev.filter(d => d !== deviceId) : [...prev, deviceId]
    )
  }

  const handleSave = async () => {
    const rid = id.trim() || name.trim().replace(/\s+/g, '_').toLowerCase()
    if (!rid || !name.trim()) {
      setError('Name ist erforderlich')
      return
    }

    setSaving(true)
    setError('')
    try {
      await onSave(rid, { name: name.trim(), icon, devices: selectedDevices })
      onClose()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const grouped = allDevices.reduce((acc, d) => {
    const cat = d.category || 'other'
    if (!acc[cat]) acc[cat] = []
    acc[cat].push(d)
    return acc
  }, {})

  const catLabels = {
    computers: 'Computer', pis: 'Raspberry Pis', lights: 'Lichter',
    plugs: 'Steckdosen', cameras: 'Kameras', speakers: 'Lautsprecher',
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-5 border-b border-[#1e1e2e]">
          <h2 className="text-lg font-semibold text-white">
            {isEdit ? 'Raum bearbeiten' : 'Neuer Raum'}
          </h2>
          <button onClick={onClose} className="text-gray-500 hover:text-white cursor-pointer">
            <X size={20} />
          </button>
        </div>

        <div className="p-5 space-y-5">
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Name</label>
            <input
              type="text"
              value={name}
              onChange={e => {
                setName(e.target.value)
                if (!isEdit) setId(e.target.value.trim().replace(/\s+/g, '_').toLowerCase())
              }}
              placeholder="z.B. Wohnzimmer"
              className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00D4FF]"
            />
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Icon</label>
            <div className="flex gap-2 flex-wrap">
              {ROOM_ICONS.map(i => (
                <button
                  key={i.value}
                  onClick={() => setIcon(i.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs cursor-pointer transition-all ${
                    icon === i.value
                      ? 'bg-[#00D4FF]/20 text-[#00D4FF] border border-[#00D4FF]/50'
                      : 'bg-[#0a0a0f] text-gray-400 border border-[#1e1e2e] hover:text-white'
                  }`}
                >
                  {i.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-2">Geräte zuordnen</label>
            <div className="space-y-3">
              {Object.entries(grouped).map(([cat, devs]) => (
                <div key={cat}>
                  <p className="text-xs text-gray-500 mb-1">{catLabels[cat] || cat}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {devs.map(d => (
                      <button
                        key={d.device_id}
                        onClick={() => toggleDevice(d.device_id)}
                        className={`px-2.5 py-1 rounded-lg text-xs cursor-pointer transition-all ${
                          selectedDevices.includes(d.device_id)
                            ? 'bg-[#00D4FF]/20 text-[#00D4FF] border border-[#00D4FF]/50'
                            : 'bg-[#0a0a0f] text-gray-400 border border-[#1e1e2e] hover:text-white'
                        }`}
                      >
                        {d.name}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}
        </div>

        <div className="flex justify-end gap-3 p-5 border-t border-[#1e1e2e]">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors cursor-pointer">
            Abbrechen
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm bg-[#00D4FF] text-black font-medium rounded-lg hover:bg-[#00b8d4] transition-colors disabled:opacity-50 cursor-pointer"
          >
            {saving ? 'Speichern...' : 'Speichern'}
          </button>
        </div>
      </div>
    </div>
  )
}
