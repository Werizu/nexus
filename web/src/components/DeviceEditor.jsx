import { useState, useEffect } from 'react'
import { X } from 'lucide-react'

const CATEGORIES = [
  { value: 'computers', label: 'Computer' },
  { value: 'pis', label: 'Raspberry Pi' },
  { value: 'lights', label: 'Lichter' },
  { value: 'plugs', label: 'Steckdosen' },
  { value: 'cameras', label: 'Kameras' },
  { value: 'speakers', label: 'Lautsprecher' },
]

const PLUGINS = [
  { value: 'pc_control', label: 'PC Control' },
  { value: 'pi_manager', label: 'Pi Manager' },
  { value: 'hue_lights', label: 'Hue / IKEA Lichter' },
  { value: 'tasmota', label: 'Tasmota' },
  { value: 'ikea_lights', label: 'IKEA Lights' },
  { value: 'alexa_bridge', label: 'Alexa Bridge' },
  { value: 'jarvis_bridge', label: 'Jarvis Bridge' },
]

const CATEGORY_FIELDS = {
  computers: [
    { key: 'ip', label: 'IP-Adresse', placeholder: '100.123.253.88' },
    { key: 'mac_address', label: 'MAC-Adresse', placeholder: '2C:F0:5D:99:03:63' },
    { key: 'os', label: 'Betriebssystem', type: 'select', options: ['windows', 'macos', 'linux'] },
    { key: 'ssh_user', label: 'SSH User', placeholder: 'marlon' },
    { key: 'ssh_key', label: 'SSH Key', placeholder: '~/.ssh/id_rsa' },
  ],
  pis: [
    { key: 'hostname', label: 'Hostname / IP', placeholder: '100.122.236.58' },
    { key: 'ssh_user', label: 'SSH User', placeholder: 'marlon' },
    { key: 'ssh_key', label: 'SSH Key', placeholder: '~/.ssh/pi_manager_rsa' },
    { key: 'role', label: 'Rolle', type: 'select', options: ['primary', 'secondary'] },
  ],
  lights: [
    { key: 'bridge_ip', label: 'Bridge IP', placeholder: '192.168.178.48' },
    { key: 'hue_id', label: 'Hue/IKEA ID', placeholder: '3' },
  ],
  plugs: [
    { key: 'bridge_ip', label: 'Bridge IP', placeholder: '192.168.178.48' },
    { key: 'hue_id', label: 'Hue/IKEA ID', placeholder: '8' },
  ],
}

export default function DeviceEditor({ device, onSave, onClose }) {
  const isEdit = !!device

  const [id, setId] = useState('')
  const [name, setName] = useState('')
  const [category, setCategory] = useState('computers')
  const [plugin, setPlugin] = useState('pc_control')
  const [room, setRoom] = useState('')
  const [fields, setFields] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (device) {
      setId(device.device_id || device.id || '')
      setName(device.name || '')
      setCategory(device.category || 'computers')
      setPlugin(device.plugin || device.config?.plugin || '')
      setRoom(device.room || device.config?.room || '')
      setFields(device.config || {})
    }
  }, [device])

  const handleSave = async () => {
    const deviceId = id.trim() || name.trim().replace(/\s+/g, '_').toLowerCase()
    if (!deviceId || !name.trim()) {
      setError('Name und ID sind erforderlich')
      return
    }

    const deviceData = {
      id: deviceId,
      name: name.trim(),
      category,
      plugin,
      room,
      ...fields,
    }

    setSaving(true)
    setError('')
    try {
      await onSave(deviceData, !isEdit)
      onClose()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const updateField = (key, value) => {
    setFields(prev => ({ ...prev, [key]: value }))
  }

  const categoryFields = CATEGORY_FIELDS[category] || []

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-5 border-b border-[#1e1e2e]">
          <h2 className="text-lg font-semibold text-white">
            {isEdit ? 'Gerät bearbeiten' : 'Neues Gerät'}
          </h2>
          <button onClick={onClose} className="text-gray-500 hover:text-white cursor-pointer">
            <X size={20} />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Name</label>
              <input
                type="text"
                value={name}
                onChange={e => {
                  setName(e.target.value)
                  if (!isEdit) setId(e.target.value.trim().replace(/\s+/g, '_').toLowerCase())
                }}
                placeholder="z.B. Desktop PC"
                className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00D4FF]"
              />
              {id && <p className="text-xs text-gray-600 mt-1">ID: {id}</p>}
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Kategorie</label>
              <select
                value={category}
                onChange={e => setCategory(e.target.value)}
                disabled={isEdit}
                className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00D4FF] disabled:opacity-50"
              >
                {CATEGORIES.map(c => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Plugin</label>
            <select
              value={plugin}
              onChange={e => setPlugin(e.target.value)}
              className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00D4FF]"
            >
              <option value="">Kein Plugin</option>
              {PLUGINS.map(p => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>

          {categoryFields.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs text-gray-500 font-medium">Konfiguration</p>
              {categoryFields.map(f => (
                <div key={f.key}>
                  <label className="block text-xs text-gray-400 mb-1">{f.label}</label>
                  {f.type === 'select' ? (
                    <select
                      value={fields[f.key] || ''}
                      onChange={e => updateField(f.key, e.target.value)}
                      className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00D4FF]"
                    >
                      <option value="">--</option>
                      {f.options.map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={fields[f.key] || ''}
                      onChange={e => updateField(f.key, e.target.value)}
                      placeholder={f.placeholder || ''}
                      className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00D4FF]"
                    />
                  )}
                </div>
              ))}
            </div>
          )}

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
