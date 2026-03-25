import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apiGetHistory, apiGetExecutionLogs } from '../services/api'

export default function HistoryPage({ token, username, onLogout }) {
  const [history, setHistory] = useState([])
  const [selectedExecution, setSelectedExecution] = useState(null)
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingLogs, setLoadingLogs] = useState(false)

  useEffect(() => {
    fetchHistory()
  }, [])

  const fetchHistory = async () => {
    setLoading(true)
    const data = await apiGetHistory(token)
    if (data.history) {
      setHistory(data.history)
    }
    setLoading(false)
  }

  const handleSelectExecution = async (execution) => {
    setSelectedExecution(execution)
    setLoadingLogs(true)
    const data = await apiGetExecutionLogs(execution.id, token)
    if (data.logs) {
      setLogs(data.logs)
    }
    setLoadingLogs(false)
  }

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="header-left">
          <Link to="/" className="btn btn-dark btn-sm">⬅️ Voltar ao Dashboard</Link>
          <h1>📜 Histórico de Execuções</h1>
        </div>
        <div className="header-right">
          <div className="header-user">
            <div className="avatar">{username?.charAt(0).toUpperCase()}</div>
            <span>{username}</span>
          </div>
          <button className="btn btn-dark btn-sm" onClick={onLogout}>Sair</button>
        </div>
      </header>

      <div className="dashboard-content history-layout">
        <div className="panel history-list-panel">
          <div className="panel-header">
            <h2>Últimas Execuções</h2>
            <button className="btn btn-dark btn-sm" onClick={fetchHistory}>🔄 Atualizar</button>
          </div>
          <div className="panel-body">
            {loading ? (
              <div className="loading">Carregando histórico...</div>
            ) : history.length === 0 ? (
              <div className="empty">Nenhuma execução encontrada.</div>
            ) : (
              <div className="execution-items">
                {history.map((item) => (
                  <div 
                    key={item.id} 
                    className={`execution-item ${selectedExecution?.id === item.id ? 'active' : ''}`}
                    onClick={() => handleSelectExecution(item)}
                  >
                    <div className="exec-info">
                      <span className="exec-task">{item.task_name}</span>
                      <span className="exec-date">{new Date(item.started_at).toLocaleString()}</span>
                    </div>
                    <div className={`exec-status status-${item.status}`}>
                      {item.status.toUpperCase()}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="panel history-details-panel">
          <div className="panel-header">
            <h2>Logs da Execução</h2>
          </div>
          <div className="panel-body">
            {!selectedExecution ? (
              <div className="empty">Selecione uma execução para ver os logs.</div>
            ) : loadingLogs ? (
              <div className="loading">Carregando logs...</div>
            ) : (
              <div className="log-console history-logs">
                <div className="log-entries">
                  {logs.length === 0 ? (
                    <div className="log-entry">Nenhum log para esta execução.</div>
                  ) : (
                    logs.map((log, idx) => (
                      <div key={idx} className="log-entry">
                        <span className="log-time">[{new Date(log.timestamp).toLocaleTimeString()}]</span>
                        <span className="log-msg">{log.message}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
