export default function ProgressBar({ atual, total }) {
  const pct = total > 0 ? Math.round((atual / total) * 100) : 0

  return (
    <div className="progress-container" style={{ flex: 1 }}>
      <div className="progress-bar-wrapper">
        <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="progress-label">
        <span>{pct}%</span>
        <span>{atual} de {total}</span>
      </div>
    </div>
  )
}
