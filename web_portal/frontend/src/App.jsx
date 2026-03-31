import { useEffect } from 'react'
import './index.css'

function App() {
  const downloads = [
    {
      title: 'Bot Desktop',
      description: 'Baixe o MeuBot para Windows e automatize seus Cadastros.',
      icon: '🚀',
      link: '/downloads/MeuBot-Desktop.zip',
      color: 'blue'
    },
    {
      title: 'Planilha QRPedir',
      description: 'Modelo de planilha formato CSV para o sistema QRPedir.',
      icon: '📊',
      link: '/downloads/Planilha-Modelo-QRPedir.csv',
      color: 'purple'
    },
    {
      title: 'Planilha Sischef',
      description: 'Modelo de planilha formato CSV para o sistema Sischef.',
      icon: '📈',
      link: '/downloads/Planilha-Modelo-Sischef.csv',
      color: 'green'
    }
  ];

  return (
    <div className="landing-page">
      <div className="background-orbs">
        <div className="orb orb-1"></div>
        <div className="orb orb-2"></div>
      </div>

      <nav className="navbar">
        <div className="logo">
          <span className="logo-icon">🤖</span>
          <span className="logo-text">MeuBot</span>
        </div>
      </nav>

      <main className="main-content">
        <header className="hero">
          <div className="badge">Automação Inteligente</div>
          <h1>Simplifique seus <br /><span className="text-gradient">Cadastros de Produtos e Receitas</span></h1>
          <p className="hero-subtitle">
            Baixe o aplicativo desktop do MeuBot, baixe nossas planilhas modelo e
            comece a automatizar o cadastro de produtos e receitas no nosso sistema Sischef de forma rápida e segura.
          </p>
        </header>

        <section className="downloads-section">
          {downloads.map((item, index) => (
            <div className="download-card" key={index}>
              <div className={`card-icon-container bg-${item.color}`}>
                <span className="card-icon">{item.icon}</span>
              </div>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
              <a href={item.link} className={`btn btn-${item.color}`} download>
                Fazer Download
              </a>
            </div>
          ))}
        </section>
      </main>

      <footer className="footer">
        <p>&copy; {new Date().getFullYear()} MeuBot. Todos os direitos reservados.</p>
      </footer>
    </div>
  )
}

export default App
