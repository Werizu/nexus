import { useState, useEffect } from 'react'
import { X, Plus, Trash2, GripVertical } from 'lucide-react'

const ACTION_TYPES = [
  { value: 'light.on', label: 'Licht ein' },
  { value: 'light.off', label: 'Licht aus' },
  { value: 'light.brightness', label: 'Helligkeit', hasLevel: true },
  { value: 'light.color_temp', label: 'Farbtemperatur', hasLevel: true },
  { value: 'light.focus', label: 'Fokus-Modus' },
  { value: 'light.relax', label: 'Relax-Modus' },
  { value: 'plug.on', label: 'Steckdose ein' },
  { value: 'plug.off', label: 'Steckdose aus' },
  { value: 'pc.wake', label: 'PC aufwecken' },
  { value: 'pc.shutdown', label: 'PC herunterfahren' },
  { value: 'pc.restart', label: 'PC neustarten' },
  { value: 'wait', label: 'Warten', hasSeconds: true },
  { value: 'jarvis.speak', label: 'Jarvis Sprache', hasText: true },
]

const DEVICES = [
  { value: 'light_1', label: 'Light 1', category: 'lights' },
  { value: 'light_2', label: 'Light 2', category: 'lights' },
  { value: 'light_3', label: 'Light 3', category: 'lights' },
  { value: 'light_4', label: 'Light 4', category: 'lights' },
  { value: 'plug_pc', label: 'PC Steckdose', category: 'plugs' },
  { value: 'plug_tv', label: 'Fernseher Steckdose', category: 'plugs' },
  { value: 'main_pc', label: 'Desktop PC', category: 'computers' },
  { value: 'brain', label: 'NEXUS Brain', category: 'pis' },
  { value: 'server1', label: 'Server 1', category: 'pis' },
  { value: 'server3', label: 'Server 3', category: 'pis' },
]

const COLORS = [
  '#00D4FF', '#3498DB', '#2ECC71', '#E74C3C', '#F39C12',
  '#9B59B6', '#1ABC9C', '#E67E22', '#95A5A6', '#2C3E50',
]

const ICONS = [
  { value: 'code', label: 'Code' },
  { value: 'sunrise', label: 'Sonnenaufgang' },
  { value: 'film', label: 'Film' },
  { value: 'moon', label: 'Mond' },
  { value: 'door-open', label: 'Tür' },
  { value: 'power-off', label: 'Power' },
  { value: 'sun', label: 'Sonne' },
  { value: 'home', label: 'Haus' },
  { value: 'music', label: 'Musik' },
  { value: 'coffee', label: 'Kaffee' },
]

const EMPTY_ACTION = { action: 'light.on', device: 'light_1' }

function actionNeedsDevice(actionType) {
  return actionType !== 'wait' && actionType !== 'jarvis.speak'
}

export default function SceneEditor({ scene, onSave, onClose }) {
  const isEdit = !!scene

  const [name, setName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [icon, setIcon] = useState('code')
  const [color, setColor] = useState('#00D4FF')
  const [actions, setActions] = useState([{ ...EMPTY_ACTION }])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (scene) {
      setName(scene.name)
      setDisplayName(scene.display_name || scene.name)
      setIcon(scene.icon || 'code')
      setColor(scene.color || '#00D4FF')
      setActions(scene.actions?.length ? scene.actions.map(a => ({ ...a })) : [{ ...EMPTY_ACTION }])
    }
  }, [scene])

  const updateAction = (index, field, value) => {
    setActions(prev => prev.map((a, i) => i === index ? { ...a, [field]: value } : a))
  }

  const removeAction = (index) => {
    setActions(prev => prev.filter((_, i) => i !== index))
  }

  const addAction = () => {
    setActions(prev => [...prev, { ...EMPTY_ACTION }])
  }

  const moveAction = (index, direction) => {
    const newActions = [...actions]
    const target = index + direction
    if (target < 0 || target >= newActions.length) return
    ;[newActions[index], newActions[target]] = [newActions[target], newActions[index]]
    setActions(newActions)
  }

  const handleSave = async () => {
    const sceneName = name.trim().replace(/\s+/g, '_').toLowerCase()
    if (!sceneName) {
      setError('Name ist erforderlich')
      return
    }
    if (actions.length === 0) {
      setError('Mindestens eine Aktion ist erforderlich')
      return
    }

    const cleanActions = actions.map(a => {
      const clean = { action: a.action }
      if (actionNeedsDevice(a.action)) clean.device = a.device
      if (a.action === 'light.brightness' || a.action === 'light.color_temp') clean.level = Number(a.level) || 50
      if (a.action === 'wait') clean.seconds = Number(a.seconds) || 1
      if (a.action === 'jarvis.speak') clean.text = a.text || ''
      return clean
    })

    const sceneData = {
      name: sceneName,
      display_name: displayName.trim() || sceneName,
      icon,
      color,
      triggers: scene?.triggers || [],
      actions: cleanActions,
    }

    setSaving(true)
    setError('')
    try {
      await onSave(sceneData, isEdit ? scene.name : null)
      onClose()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const actionMeta = (type) => ACTION_TYPES.find(a => a.value === type) || {}

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-5 border-b border-[#1e1e2e]">
          <h2 className="text-lg font-semibold text-white">
            {isEdit ? 'Szene bearbeiten' : 'Neue Szene'}
          </h2>
          <button onClick={onClose} className="text-gray-500 hover:text-white cursor-pointer">
            <X size={20} />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Name */}
          <div>
            <label className="block text-xs text-gray-400 mb-1.5">Anzeigename</label>
            <input
              type="text"
              value={displayName}
              onChange={e => {
                setDisplayName(e.target.value)
                if (!isEdit) setName(e.target.value.trim().replace(/\s+/g, '_').toLowerCase())
              }}
              placeholder="z.B. Film-Abend"
              className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00D4FF]"
            />
            {name && (
              <p className="text-xs text-gray-600 mt-1">ID: {name}</p>
            )}
          </div>

          {/* Icon + Color */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Icon</label>
              <select
                value={icon}
                onChange={e => setIcon(e.target.value)}
                className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00D4FF]"
              >
                {ICONS.map(i => (
                  <option key={i.value} value={i.value}>{i.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Farbe</label>
              <div className="flex gap-1.5 flex-wrap">
                {COLORS.map(c => (
                  <button
                    key={c}
                    onClick={() => setColor(c)}
                    className={`w-6 h-6 rounded-full cursor-pointer transition-transform ${
                      color === c ? 'ring-2 ring-white scale-110' : ''
                    }`}
                    style={{ background: c }}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Actions */}
          <div>
            <label className="block text-xs text-gray-400 mb-2">Aktionen</label>
            <div className="space-y-2">
              {actions.map((action, i) => {
                const meta = actionMeta(action.action)
                return (
                  <div key={i} className="bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg p-3">
                    <div className="flex items-center gap-2">
                      <div className="flex flex-col gap-0.5">
                        <button
                          onClick={() => moveAction(i, -1)}
                          disabled={i === 0}
                          className="text-gray-600 hover:text-gray-300 disabled:opacity-20 cursor-pointer text-xs"
                        >▲</button>
                        <button
                          onClick={() => moveAction(i, 1)}
                          disabled={i === actions.length - 1}
                          className="text-gray-600 hover:text-gray-300 disabled:opacity-20 cursor-pointer text-xs"
                        >▼</button>
                      </div>

                      <select
                        value={action.action}
                        onChange={e => updateAction(i, 'action', e.target.value)}
                        className="flex-1 bg-[#12121a] border border-[#2a2a3e] rounded px-2 py-1.5 text-xs text-white focus:outline-none"
                      >
                        {ACTION_TYPES.map(a => (
                          <option key={a.value} value={a.value}>{a.label}</option>
                        ))}
                      </select>

                      {actionNeedsDevice(action.action) && (
                        <select
                          value={action.device || ''}
                          onChange={e => updateAction(i, 'device', e.target.value)}
                          className="flex-1 bg-[#12121a] border border-[#2a2a3e] rounded px-2 py-1.5 text-xs text-white focus:outline-none"
                        >
                          {DEVICES.map(d => (
                            <option key={d.value} value={d.value}>{d.label}</option>
                          ))}
                        </select>
                      )}

                      <button
                        onClick={() => removeAction(i)}
                        className="text-gray-600 hover:text-red-400 cursor-pointer"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>

                    {meta.hasLevel && (
                      <div className="mt-2 flex items-center gap-2">
                        <span className="text-xs text-gray-500">Level:</span>
                        <input
                          type="range"
                          min="1"
                          max="100"
                          value={action.level || 50}
                          onChange={e => updateAction(i, 'level', e.target.value)}
                          className="flex-1"
                        />
                        <span className="text-xs text-gray-400 w-8 text-right">{action.level || 50}%</span>
                      </div>
                    )}

                    {meta.hasSeconds && (
                      <div className="mt-2 flex items-center gap-2">
                        <span className="text-xs text-gray-500">Sekunden:</span>
                        <input
                          type="number"
                          min="1"
                          max="300"
                          value={action.seconds || 1}
                          onChange={e => updateAction(i, 'seconds', e.target.value)}
                          className="w-20 bg-[#12121a] border border-[#2a2a3e] rounded px-2 py-1 text-xs text-white focus:outline-none"
                        />
                      </div>
                    )}

                    {meta.hasText && (
                      <div className="mt-2">
                        <input
                          type="text"
                          value={action.text || ''}
                          onChange={e => updateAction(i, 'text', e.target.value)}
                          placeholder="Text zum Sprechen..."
                          className="w-full bg-[#12121a] border border-[#2a2a3e] rounded px-2 py-1.5 text-xs text-white focus:outline-none"
                        />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            <button
              onClick={addAction}
              className="mt-2 flex items-center gap-1.5 text-xs text-[#00D4FF] hover:text-white transition-colors cursor-pointer"
            >
              <Plus size={14} /> Aktion hinzufügen
            </button>
          </div>

          {error && (
            <p className="text-sm text-red-400">{error}</p>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 p-5 border-t border-[#1e1e2e]">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors cursor-pointer"
          >
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
