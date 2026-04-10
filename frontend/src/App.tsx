import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AgentDebugPage } from './pages/AgentDebugPage'
import { ConfigPage } from './pages/ConfigPage'
import { DashboardPage } from './pages/DashboardPage'
import { LabPage } from './pages/LabPage'

export default function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/lab" element={<LabPage />} />
        <Route path="/config" element={<ConfigPage />} />
        <Route path="/agent-debug" element={<AgentDebugPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
