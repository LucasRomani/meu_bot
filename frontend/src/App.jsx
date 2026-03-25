import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import Dashboard from './pages/Dashboard'
import HistoryPage from './pages/HistoryPage'

function App() {
  const [token, setToken] = useState(localStorage.getItem('token'))
  const [username, setUsername] = useState(localStorage.getItem('username'))

  const handleLogin = (newToken, newUsername) => {
    localStorage.setItem('token', newToken)
    localStorage.setItem('username', newUsername)
    setToken(newToken)
    setUsername(newUsername)
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    setToken(null)
    setUsername(null)
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route 
          path="/login" 
          element={token ? <Navigate to="/" /> : <LoginPage onLogin={handleLogin} />} 
        />
        <Route 
          path="/" 
          element={token ? <Dashboard token={token} username={username} onLogout={handleLogout} /> : <Navigate to="/login" />} 
        />
        <Route 
          path="/history" 
          element={token ? <HistoryPage token={token} username={username} onLogout={handleLogout} /> : <Navigate to="/login" />} 
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App
