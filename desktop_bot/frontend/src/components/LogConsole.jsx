import { useEffect, useRef } from 'react'

export default function LogConsole({ logs, onClear }) {
  const containerRef = useRef()

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [logs])

  const getLogType = (msg) => {
    if (msg.includes('❌') || msg.includes('ERRO') || msg.includes('FALHA')) return 'error'
    if (msg.includes('✅') || msg.includes('concluí')) return 'success'
    if (msg.includes('⚠️') || msg.includes('⛔') || msg.includes('DUPLICADO')) return 'warn'
    return ''
  }

  return (
    <div className="log-console">
      <div className="panel-header">
        <h2>📋 Log de Atividades</h2>
        <span style={{ marginLeft: 'auto', fontSize: '12px', color: 'var(--text-muted)' }}>
          {logs.length} entradas
        </span>
        <button
          className="btn btn-dark btn-sm"
          style={{ marginLeft: '8px', width: 'auto', padding: '4px 12px', fontSize: '12px' }}
          onClick={onClear}
        >
          🗑️ Limpar
        </button>
      </div>
      <div className="log-entries" ref={containerRef}>
        {logs.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', padding: '20px', textAlign: 'center' }}>
            Aguardando atividade...
          </div>
        ) : (
          logs.map((log, i) => (
            <div className="log-entry" key={i}>
              <span className="log-time">{log.time}</span>
              <span className={`log-msg ${log.type || getLogType(log.message)}`}>
                {log.message}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
