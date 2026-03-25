import { useState } from 'react'
import { apiLogin, apiRegister } from '../services/api'

export default function LoginPage({ onLogin }) {
  const [isRegister, setIsRegister] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)

    try {
      if (isRegister) {
        const data = await apiRegister(username, password)
        if (data.success) {
          setSuccess('Conta criada! Fazendo login...')
          // Auto-login after register
          const loginData = await apiLogin(username, password)
          if (loginData.success) {
            onLogin(loginData.token, loginData.username)
          }
        } else {
          setError(data.message)
        }
      } else {
        const data = await apiLogin(username, password)
        if (data.success) {
          onLogin(data.token, data.username)
        } else {
          setError(data.message)
        }
      }
    } catch (err) {
      setError('Erro de conexão com o servidor.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>🤖 Bot Sischef</h1>
        <p className="subtitle">Automação Inteligente para Sischef & QRPedir</p>

        <div className="form-group">
          <label>Usuário</label>
          <input
            type="text"
            placeholder="Seu usuário"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoFocus
          />
        </div>

        <div className="form-group">
          <label>Senha</label>
          <input
            type="password"
            placeholder="Sua senha"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        <button className="btn btn-primary" type="submit" disabled={loading}>
          {loading ? '⏳ Aguarde...' : isRegister ? 'Criar Conta' : 'Entrar'}
        </button>

        {error && <p className="error-msg">{error}</p>}
        {success && <p className="success-msg">{success}</p>}

        <p className="toggle-link" onClick={() => { setIsRegister(!isRegister); setError(''); setSuccess(''); }}>
          {isRegister
            ? 'Já tem conta? '
            : 'Não tem conta? '}
          <span>{isRegister ? 'Entrar' : 'Criar conta'}</span>
        </p>
      </form>
    </div>
  )
}
