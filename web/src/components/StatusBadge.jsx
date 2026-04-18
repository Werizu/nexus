export default function StatusBadge({ online, label }) {
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${
      online
        ? 'bg-emerald-500/15 text-emerald-400'
        : 'bg-red-500/15 text-red-400'
    }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${online ? 'bg-emerald-400' : 'bg-red-400'}`} />
      {label || (online ? 'Online' : 'Offline')}
    </span>
  )
}
