import { NavLink } from 'react-router-dom'

export function AppHeader() {
  return (
    <header className="app-header">
      <h1>Crypto trading bot</h1>
      <nav className="app-nav" aria-label="Principal">
        <NavLink to="/" end className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
          Panel
        </NavLink>
        <NavLink to="/lab" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
          Laboratorio
        </NavLink>
        <NavLink to="/config" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
          Configuración
        </NavLink>
        <NavLink to="/agent-debug" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
          Debug IA
        </NavLink>
      </nav>
      <span className="meta">
        Paper / testnet ·{' '}
        <a href="/docs" target="_blank" rel="noreferrer">
          API docs
        </a>
      </span>
    </header>
  )
}
