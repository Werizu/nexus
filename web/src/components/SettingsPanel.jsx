import { useState, useEffect, useCallback } from 'react'
import { KeyRound, UserCog, Trash2, Shield, User } from 'lucide-react'

const API_BASE = '/api/v1'

function getToken() {
  return localStorage.getItem('nexus_token')
}

async function api(path, options = {}) {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${API_BASE}${path}`, { headers, ...options })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || `Fehler: ${res.status}`)
  }
  return res.json()
}

function PasswordSection() {
  const [current, setCurrent] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirm, setConfirm] = useState('')
  const [msg, setMsg] = useState(null)

  const handleChange = async (e) => {
    e.preventDefault()
    setMsg(null)
    if (newPw.length < 4) return setMsg({ type: 'error', text: 'Mindestens 4 Zeichen' })
    if (newPw !== confirm) return setMsg({ type: 'error', text: 'Passwörter stimmen nicht überein' })
    try {
      await api('/auth/password', { method: 'PUT', body: JSON.stringify({ password: newPw }) })
      setMsg({ type: 'ok', text: 'Passwort geändert' })
      setCurrent('')
      setNewPw('')
      setConfirm('')
    } catch (e) {
      setMsg({ type: 'error', text: e.message })
    }
  }

  return (
    <div className="bg-[#12121a] border border-[#1e1e2e] rounded-2xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <KeyRound size={16} className="text-[#00D4FF]" />
        <h3 className="text-sm font-semibold text-white">Passwort ändern</h3>
      </div>
      <form onSubmit={handleChange} className="space-y-3 max-w-sm">
        <input
          type="password"
          placeholder="Neues Passwort"
          value={newPw}
          onChange={e => setNewPw(e.target.value)}
          className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00D4FF]"
        />
        <input
          type="password"
          placeholder="Passwort bestätigen"
          value={confirm}
          onChange={e => setConfirm(e.target.value)}
          className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00D4FF]"
        />
        {msg && (
          <p className={`text-sm ${msg.type === 'ok' ? 'text-emerald-400' : 'text-red-400'}`}>{msg.text}</p>
        )}
        <button
          type="submit"
          disabled={!newPw || !confirm}
          className="px-4 py-2 text-sm bg-[#00D4FF] text-black font-medium rounded-lg hover:bg-[#00b8d4] transition-colors disabled:opacity-50 cursor-pointer"
        >
          Ändern
        </button>
      </form>
    </div>
  )
}

function ProfileSection({ user, onUpdate }) {
  const [displayName, setDisplayName] = useState(user.display_name || '')
  const [msg, setMsg] = useState(null)

  const handleSave = async (e) => {
    e.preventDefault()
    setMsg(null)
    if (!displayName.trim()) return
    try {
      await api(`/auth/users/${user.username}`, {
        method: 'PUT',
        body: JSON.stringify({ display_name: displayName.trim() }),
      })
      const updated = { ...user, display_name: displayName.trim() }
      localStorage.setItem('nexus_user', JSON.stringify(updated))
      onUpdate(updated)
      setMsg({ type: 'ok', text: 'Gespeichert' })
    } catch (e) {
      setMsg({ type: 'error', text: e.message })
    }
  }

  return (
    <div className="bg-[#12121a] border border-[#1e1e2e] rounded-2xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <User size={16} className="text-[#00D4FF]" />
        <h3 className="text-sm font-semibold text-white">Profil</h3>
      </div>
      <form onSubmit={handleSave} className="space-y-3 max-w-sm">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Benutzername</label>
          <p className="text-sm text-gray-400">{user.username}</p>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Anzeigename</label>
          <input
            type="text"
            value={displayName}
            onChange={e => setDisplayName(e.target.value)}
            className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00D4FF]"
          />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Rolle</label>
          <p className="text-sm text-gray-400 capitalize">{user.role}</p>
        </div>
        {msg && (
          <p className={`text-sm ${msg.type === 'ok' ? 'text-emerald-400' : 'text-red-400'}`}>{msg.text}</p>
        )}
        <button
          type="submit"
          className="px-4 py-2 text-sm bg-[#00D4FF] text-black font-medium rounded-lg hover:bg-[#00b8d4] transition-colors cursor-pointer"
        >
          Speichern
        </button>
      </form>
    </div>
  )
}

function UserManagement({ currentUser }) {
  const [users, setUsers] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [newUser, setNewUser] = useState({ username: '', password: '', display_name: '', role: 'user' })
  const [msg, setMsg] = useState(null)

  const loadUsers = useCallback(async () => {
    try {
      setUsers(await api('/auth/users'))
    } catch {}
  }, [])

  useEffect(() => { loadUsers() }, [loadUsers])

  const handleAdd = async (e) => {
    e.preventDefault()
    setMsg(null)
    if (!newUser.username || !newUser.password) return
    try {
      await api('/auth/register', { method: 'POST', body: JSON.stringify(newUser) })
      setNewUser({ username: '', password: '', display_name: '', role: 'user' })
      setShowAdd(false)
      await loadUsers()
    } catch (e) {
      setMsg({ type: 'error', text: e.message })
    }
  }

  const handleDelete = async (username) => {
    if (username === currentUser.username) return
    if (!window.confirm(`Benutzer "${username}" wirklich löschen?`)) return
    try {
      await api(`/auth/users/${username}`, { method: 'DELETE' })
      await loadUsers()
    } catch (e) {
      setMsg({ type: 'error', text: e.message })
    }
  }

  const handleRoleToggle = async (username, currentRole) => {
    if (username === currentUser.username) return
    const newRole = currentRole === 'admin' ? 'user' : 'admin'
    try {
      await api(`/auth/users/${username}`, { method: 'PUT', body: JSON.stringify({ role: newRole }) })
      await loadUsers()
    } catch (e) {
      setMsg({ type: 'error', text: e.message })
    }
  }

  return (
    <div className="bg-[#12121a] border border-[#1e1e2e] rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <UserCog size={16} className="text-[#00D4FF]" />
          <h3 className="text-sm font-semibold text-white">Benutzerverwaltung</h3>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="px-3 py-1 text-xs bg-[#00D4FF] text-black font-medium rounded-lg hover:bg-[#00b8d4] transition-colors cursor-pointer"
        >
          + Neuer Benutzer
        </button>
      </div>

      {showAdd && (
        <form onSubmit={handleAdd} className="mb-4 p-4 bg-[#0a0a0f] rounded-xl border border-[#1e1e2e] space-y-3 max-w-sm">
          <input
            type="text"
            placeholder="Benutzername"
            value={newUser.username}
            onChange={e => setNewUser({ ...newUser, username: e.target.value })}
            className="w-full bg-[#12121a] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00D4FF]"
          />
          <input
            type="text"
            placeholder="Anzeigename"
            value={newUser.display_name}
            onChange={e => setNewUser({ ...newUser, display_name: e.target.value })}
            className="w-full bg-[#12121a] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00D4FF]"
          />
          <input
            type="password"
            placeholder="Passwort"
            value={newUser.password}
            onChange={e => setNewUser({ ...newUser, password: e.target.value })}
            className="w-full bg-[#12121a] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00D4FF]"
          />
          <select
            value={newUser.role}
            onChange={e => setNewUser({ ...newUser, role: e.target.value })}
            className="w-full bg-[#12121a] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#00D4FF]"
          >
            <option value="user">Benutzer</option>
            <option value="admin">Admin</option>
          </select>
          <div className="flex gap-2">
            <button type="submit" className="px-3 py-1.5 text-sm bg-[#00D4FF] text-black font-medium rounded-lg hover:bg-[#00b8d4] cursor-pointer">Erstellen</button>
            <button type="button" onClick={() => setShowAdd(false)} className="px-3 py-1.5 text-sm text-gray-400 hover:text-white cursor-pointer">Abbrechen</button>
          </div>
        </form>
      )}

      {msg && <p className={`text-sm mb-3 ${msg.type === 'ok' ? 'text-emerald-400' : 'text-red-400'}`}>{msg.text}</p>}

      <div className="space-y-2">
        {users.map((u) => (
          <div key={u.username} className="flex items-center justify-between p-3 bg-[#0a0a0f] rounded-xl border border-[#1e1e2e]">
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${u.role === 'admin' ? 'bg-amber-500/20' : 'bg-[#1e1e2e]'}`}>
                {u.role === 'admin' ? <Shield size={14} className="text-amber-400" /> : <User size={14} className="text-gray-400" />}
              </div>
              <div>
                <p className="text-sm text-white font-medium">{u.display_name || u.username}</p>
                <p className="text-xs text-gray-500">@{u.username} · {u.role}</p>
              </div>
            </div>
            {u.username !== currentUser.username && (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleRoleToggle(u.username, u.role)}
                  className="text-xs text-gray-500 hover:text-[#00D4FF] cursor-pointer"
                  title={u.role === 'admin' ? 'Zu Benutzer machen' : 'Zum Admin machen'}
                >
                  {u.role === 'admin' ? 'Herabstufen' : 'Befördern'}
                </button>
                <button
                  onClick={() => handleDelete(u.username)}
                  className="text-gray-500 hover:text-red-400 cursor-pointer"
                  title="Löschen"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function SettingsPanel({ user, onUserUpdate }) {
  const isAdmin = user.role === 'admin'

  return (
    <div className="space-y-6 max-w-2xl">
      <ProfileSection user={user} onUpdate={onUserUpdate} />
      <PasswordSection />
      {isAdmin && <UserManagement currentUser={user} />}
    </div>
  )
}
