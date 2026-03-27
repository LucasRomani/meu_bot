import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { getSocket, apiUploadCSV, apiGetCredentials, apiSaveCredential, apiChangePassword } from '../services/api'
import LogConsole from '../components/LogConsole'
import ProgressBar from '../components/ProgressBar'

const SISCHEF_TASKS = [
  { id: 'cadastro_produtos', label: '📦 Cadastro de Produtos', color: 'btn-orange' },
  { id: 'edicao_ncm', label: '🏷️ Edição de NCM', color: 'btn-orange' },
  { id: 'tributacao', label: '💰 Ajuste de Tributação', color: 'btn-orange' },
  { id: 'codbarras', label: '📊 Ajuste Cód. Barras', color: 'btn-orange' },
  { id: 'precovenda', label: '💲 Ajuste Preço de Venda', color: 'btn-orange' },
]

const SISCHEF_RECEITA_TASKS = [
  { id: 'receitas', label: '🍳 Cadastrar Receitas (Produção)', color: 'btn-purple' },
  { id: 'ficha_tecnica', label: '📋 Cadastrar Ficha Técnica (PDV)', color: 'btn-purple' },
]

export default function Dashboard({ token, username, onLogout }) {
  const [socket, setSocket] = useState(null)
  const [logs, setLogs] = useState([])
  const [progress, setProgress] = useState({ atual: 0, total: 0 })
  const [timer, setTimer] = useState('00:00')
  const [running, setRunning] = useState(false)
  const [paused, setPaused] = useState(false)
  const [view, setView] = useState('main') // 'main' or 'settings'

  // Change Password State
  const [oldPass, setOldPass] = useState('')
  const [newPass, setNewPass] = useState('')
  const [confirmPass, setConfirmPass] = useState('')
  const [passMsg, setPassMsg] = useState({ text: '', type: '' })

  // Bot status
  const [sischefActive, setSischefActive] = useState(false)
  const [qrpedirActive, setQrpedirActive] = useState(false)
  const [sischefScreenshot, setSischefScreenshot] = useState(null)
  const [qrpedirScreenshot, setQrpedirScreenshot] = useState(null)

  // Credentials
  const [sischefUser, setSischefUser] = useState('')
  const [sischefPass, setSischefPass] = useState('')
  const [qrpedirUser, setQrpedirUser] = useState('')
  const [qrpedirPass, setQrpedirPass] = useState('')

  // Files
  const [csvSischef, setCsvSischef] = useState(null)
  const [csvReceitas, setCsvReceitas] = useState(null)
  const [csvQrpedir, setCsvQrpedir] = useState(null)

  const fileRefSischef = useRef()
  const fileRefReceitas = useRef()
  const fileRefQrpedir = useRef()

  // Socket connection
  useEffect(() => {
    const s = getSocket(token)

    s.on('connected', (data) => {
      addLog('✅ Conectado ao servidor.', 'success')
    })

    s.on('log', (data) => {
      addLog(data.message)
    })

    s.on('progress', (data) => {
      setProgress({ atual: data.atual, total: data.total })
    })

    s.on('timer', (data) => {
      setTimer(data.time)
    })

    s.on('bot_status', (data) => {
      if (data.bot_type === 'sischef') setSischefActive(data.active)
      if (data.bot_type === 'qrpedir') setQrpedirActive(data.active)
    })

    s.on('screenshot', (data) => {
      if (data.bot_type === 'sischef') setSischefScreenshot(data.image)
      if (data.bot_type === 'qrpedir') setQrpedirScreenshot(data.image)
    })

    s.on('task_started', () => {
      setRunning(true)
    })

    s.on('task_stopped', () => {
      setRunning(false)
      setPaused(false)
    })

    s.on('pause_status', (data) => {
      setPaused(data.pausado)
    })

    s.on('error', (data) => {
      addLog(`❌ ${data.message}`, 'error')
    })

    s.on('disconnect', () => {
      addLog('⚠️ Desconectado do servidor.', 'warn')
    })

    setSocket(s)
    return () => s.disconnect()
  }, [token])

  // Load saved credentials
  useEffect(() => {
    const loadCreds = async () => {
      const data = await apiGetCredentials(token)
      if (data.credentials) {
        data.credentials.forEach(c => {
          if (c.system === 'sischef') {
            setSischefUser(c.username)
            setSischefPass(c.password)
          } else if (c.system === 'qrpedir') {
            setQrpedirUser(c.username)
            setQrpedirPass(c.password)
          }
        })
      }
    }
    loadCreds()
  }, [token])

  const saveCreds = async (system) => {
    const user = system === 'sischef' ? sischefUser : qrpedirUser
    const pass = system === 'sischef' ? sischefPass : qrpedirPass
    const result = await apiSaveCredential({ system, username: user, password: pass }, token)
    if (result.success) {
      addLog(`✅ Credenciais de ${system} salvas com sucesso.`, 'success')
    } else {
      addLog(`❌ Erro ao salvar credenciais: ${result.message}`, 'error')
    }
  }

  const addLog = (message, type = '') => {
    const time = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    setLogs((prev) => [...prev.slice(-500), { time, message, type }])
  }

  // Actions
  const startBot = (botType) => {
    const user = botType === 'sischef' ? sischefUser : qrpedirUser
    const pass = botType === 'sischef' ? sischefPass : qrpedirPass
    socket?.emit('start_bot', { bot_type: botType, usuario: user, senha: pass })
  }

  const startTask = (taskId) => {
    socket?.emit('start_task', { task: taskId })
  }

  const stopTask = () => {
    socket?.emit('stop_task')
  }

  const pauseResume = () => {
    socket?.emit('pause_resume')
  }

  const closeBots = () => {
    socket?.emit('close_bots')
  }

  const handleFileUpload = async (file, type, setFn) => {
    if (!file) return
    const result = await apiUploadCSV(file, type, token)
    if (result.success) {
      setFn(file.name)
      addLog(`📄 ${result.message}`, 'success')
    } else {
      addLog(`❌ ${result.message}`, 'error')
    }
  }

  const clearLogs = () => setLogs([])

  const handleChangePassword = async (e) => {
    e.preventDefault()
    setPassMsg({ text: '', type: '' })

    if (newPass !== confirmPass) {
      return setPassMsg({ text: 'As senhas não coincidem.', type: 'error' })
    }

    const res = await apiChangePassword(oldPass, newPass, token)
    if (res.success) {
      setPassMsg({ text: 'Senha alterada com sucesso!', type: 'success' })
      setOldPass('')
      setNewPass('')
      setConfirmPass('')
    } else {
      setPassMsg({ text: res.message || 'Erro ao alterar senha.', type: 'error' })
    }
  }

  return (
    <div className="dashboard">
      {/* Header */}
      <header className="dashboard-header">
        <h1>🤖 Bot Sischef & QRPedir</h1>
        <div className="header-right">
          <button 
            className="btn btn-dark btn-sm" 
            onClick={() => setView(view === 'main' ? 'settings' : 'main')}
          >
            {view === 'main' ? '⚙️ Configurações' : '🏠 Dashboard'}
          </button>
          <Link to="/history" className="btn btn-dark btn-sm">📜 Histórico</Link>
          <div className="header-user">
            <div className="avatar">{username?.charAt(0).toUpperCase()}</div>
            <span>{username}</span>
          </div>
          <button className="btn btn-dark btn-sm" onClick={onLogout}>Sair</button>
        </div>
      </header>

      {view === 'settings' ? (
        <div className="dashboard-content settings-view">
          <div className="panel" style={{ maxWidth: '600px', margin: '40px auto' }}>
            <div className="panel-header">
              <h2>🔒 Alterar Senha</h2>
            </div>
            <div className="panel-body">
              <form onSubmit={handleChangePassword}>
                <div className="form-group">
                  <label>Senha Atual</label>
                  <input 
                    type="password" 
                    value={oldPass} 
                    onChange={(e) => setOldPass(e.target.value)} 
                    required 
                  />
                </div>
                <div className="form-group">
                  <label>Nova Senha</label>
                  <input 
                    type="password" 
                    value={newPass} 
                    onChange={(e) => setNewPass(e.target.value)} 
                    required 
                  />
                </div>
                <div className="form-group">
                  <label>Confirmar Nova Senha</label>
                  <input 
                    type="password" 
                    value={confirmPass} 
                    onChange={(e) => setConfirmPass(e.target.value)} 
                    required 
                  />
                </div>
                {passMsg.text && (
                  <p className={`msg ${passMsg.type}`} style={{ 
                    padding: '10px', 
                    borderRadius: '4px', 
                    marginBottom: '10px',
                    backgroundColor: passMsg.type === 'success' ? '#d4edda' : '#f8d7da',
                    color: passMsg.type === 'success' ? '#155724' : '#721c24'
                  }}>
                    {passMsg.text}
                  </p>
                )}
                <button type="submit" className="btn btn-primary">Atualizar Senha</button>
              </form>
            </div>
          </div>

          <div className="panel" style={{ maxWidth: '600px', margin: '0 auto' }}>
            <div className="panel-header">
              <h2>👥 Gestão de Usuários</h2>
            </div>
            <div className="panel-body">
              <p>Para adicionar novos usuários ao sistema, utilize a opção <strong>"Criar Conta"</strong> na tela de login.</p>
              <p style={{ color: 'var(--text-muted)', fontSize: '14px' }}>
                Cada usuário terá seu próprio banco de credenciais e histórico de execuções de forma isolada.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="dashboard-content">
        {/* Status Bar */}
        <div className="status-bar">
          <div className="status-item">
            <span className="icon">⏱️</span> {timer}
          </div>
          <div className="status-item">
            <span className="icon">📦</span> {progress.atual}/{progress.total}
          </div>
          <ProgressBar atual={progress.atual} total={progress.total} />
          <div className="status-actions">
            <button
              className={`btn btn-sm ${paused ? 'btn-green' : 'btn-yellow'}`}
              onClick={pauseResume}
              disabled={!running}
            >
              {paused ? '▶️ Retomar' : '⏸️ Pausar'}
            </button>
            <button className="btn btn-red btn-sm" onClick={stopTask} disabled={!running}>
              ⏹️ Parar
            </button>
            <button className="btn btn-dark btn-sm" onClick={closeBots}>
              🔌 Fechar Navegadores
            </button>
          </div>
        </div>

        {/* Sischef Panel */}
        <div className="panel">
          <div className="panel-header">
            <h2>🍽️ Sischef</h2>
            <span className={`badge ${sischefActive ? 'badge-green' : 'badge-red'}`}>
              {sischefActive ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
          <div className="panel-body">
            <div className="credentials-form">
              <div className="form-group">
                <label>Usuário Sischef</label>
                <input
                  type="text"
                  placeholder="Usuário"
                  value={sischefUser}
                  onChange={(e) => setSischefUser(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Senha Sischef</label>
                <input
                  type="password"
                  placeholder="Senha"
                  value={sischefPass}
                  onChange={(e) => setSischefPass(e.target.value)}
                />
              </div>
            </div>

            <div className="panel-actions">
              <button
                className="btn btn-green btn-sm"
                onClick={() => startBot('sischef')}
                disabled={running}
              >
                🚀 Iniciar Bot Sischef
              </button>
              <button
                className="btn btn-dark btn-sm"
                onClick={() => saveCreds('sischef')}
              >
                💾 Salvar Credenciais
              </button>
            </div>

            {/* Sischef Live Feed */}
            {sischefScreenshot && sischefActive && (
              <div className="livestream" style={{ margin: '15px 0', border: '1px solid #444', borderRadius: '8px', overflow: 'hidden', backgroundColor: '#000' }}>
                <div style={{ backgroundColor: '#222', color: '#ff4444', fontSize: '12px', padding: '4px 8px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <span style={{ width: '8px', height: '8px', backgroundColor: '#ff4444', borderRadius: '50%', display: 'inline-block' }}></span>
                  MONITORAMENTO AO VIVO
                </div>
                <img src={`data:image/png;base64,${sischefScreenshot}`} alt="Sischef Live Feed" style={{ width: '100%', display: 'block' }} />
              </div>
            )}

            {/* CSV Sischef */}
            <div className="section-label">CSV Geral</div>
            <input
              ref={fileRefSischef}
              type="file"
              accept=".csv"
              style={{ display: 'none' }}
              onChange={(e) => handleFileUpload(e.target.files[0], 'sischef', setCsvSischef)}
            />
            <div
              className={`file-upload ${csvSischef ? 'has-file' : ''}`}
              onClick={() => fileRefSischef.current?.click()}
            >
              <span className="file-icon">📄</span>
              <span className="file-name">{csvSischef || 'Selecionar CSV Geral...'}</span>
            </div>

            {/* Task Buttons */}
            <div className="task-buttons">
              {SISCHEF_TASKS.map((task) => (
                <button
                  key={task.id}
                  className={`btn ${task.color} btn-sm`}
                  onClick={() => startTask(task.id)}
                  disabled={running || !sischefActive}
                >
                  {task.label}
                </button>
              ))}
            </div>

            {/* CSV Receitas */}
            <div className="section-label">CSV Receitas / Fichas</div>
            <input
              ref={fileRefReceitas}
              type="file"
              accept=".csv"
              style={{ display: 'none' }}
              onChange={(e) => handleFileUpload(e.target.files[0], 'receitas', setCsvReceitas)}
            />
            <div
              className={`file-upload ${csvReceitas ? 'has-file' : ''}`}
              onClick={() => fileRefReceitas.current?.click()}
            >
              <span className="file-icon">📁</span>
              <span className="file-name">{csvReceitas || 'Selecionar CSV Receitas...'}</span>
            </div>

            <div className="task-buttons">
              {SISCHEF_RECEITA_TASKS.map((task) => (
                <button
                  key={task.id}
                  className={`btn ${task.color} btn-sm`}
                  onClick={() => startTask(task.id)}
                  disabled={running || !sischefActive}
                >
                  {task.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* QRPedir Panel */}
        <div className="panel">
          <div className="panel-header">
            <h2>📱 QRPedir</h2>
            <span className={`badge ${qrpedirActive ? 'badge-green' : 'badge-red'}`}>
              {qrpedirActive ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>
          <div className="panel-body">
            <div className="credentials-form">
              <div className="form-group">
                <label>Usuário QRPedir</label>
                <input
                  type="text"
                  placeholder="Usuário"
                  value={qrpedirUser}
                  onChange={(e) => setQrpedirUser(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Senha QRPedir</label>
                <input
                  type="password"
                  placeholder="Senha"
                  value={qrpedirPass}
                  onChange={(e) => setQrpedirPass(e.target.value)}
                />
              </div>
            </div>

            <div className="panel-actions">
              <button
                className="btn btn-cyan btn-sm"
                onClick={() => startBot('qrpedir')}
                disabled={running}
              >
                🚀 Iniciar Bot QRPedir
              </button>
              <button
                className="btn btn-dark btn-sm"
                onClick={() => saveCreds('qrpedir')}
              >
                💾 Salvar Credenciais
              </button>
            </div>

            {/* QRPedir Live Feed */}
            {qrpedirScreenshot && qrpedirActive && (
              <div className="livestream" style={{ margin: '15px 0', border: '1px solid #444', borderRadius: '8px', overflow: 'hidden', backgroundColor: '#000' }}>
                <div style={{ backgroundColor: '#222', color: '#ff4444', fontSize: '12px', padding: '4px 8px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <span style={{ width: '8px', height: '8px', backgroundColor: '#ff4444', borderRadius: '50%', display: 'inline-block' }}></span>
                  MONITORAMENTO AO VIVO
                </div>
                <img src={`data:image/png;base64,${qrpedirScreenshot}`} alt="QRPedir Live Feed" style={{ width: '100%', display: 'block' }} />
              </div>
            )}

            {/* CSV QRPedir */}
            <div className="section-label">CSV Cadastro QRPedir</div>
            <input
              ref={fileRefQrpedir}
              type="file"
              accept=".csv"
              style={{ display: 'none' }}
              onChange={(e) => handleFileUpload(e.target.files[0], 'qrpedir', setCsvQrpedir)}
            />
            <div
              className={`file-upload ${csvQrpedir ? 'has-file' : ''}`}
              onClick={() => fileRefQrpedir.current?.click()}
            >
              <span className="file-icon">📄</span>
              <span className="file-name">{csvQrpedir || 'Selecionar CSV QRPedir...'}</span>
            </div>

            <div className="task-buttons">
              <button
                className="btn btn-cyan btn-sm"
                onClick={() => startTask('cadastro_qrpedir')}
                disabled={running || !qrpedirActive}
              >
                📱 Iniciar Cadastro QRPedir
              </button>
            </div>
          </div>
        </div>

        <LogConsole logs={logs} onClear={clearLogs} />
      </div>
      )}
    </div>
  )
}
