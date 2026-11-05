import { BrowserRouter, Navigate, Route, Routes } from 'react-router'
import { AppProvider, useAppState } from './hooks/useAppState'
import { AppLayout } from './layouts/AppLayout'
import { AccessPage } from './pages/AccessPage'
import { ConnectionPage } from './pages/ConnectionPage'
import { DashboardPage } from './pages/DashboardPage'
import { ExecutionPage } from './pages/ExecutionPage'
import { FindingDetailPage } from './pages/FindingDetailPage'
import { ModalitiesPage } from './pages/ModalitiesPage'
import { NewExecutionPage } from './pages/NewExecutionPage'
import { NewProjectPage } from './pages/NewProjectPage'
import { ProjectDetailPage } from './pages/ProjectDetailPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { ResultsPage } from './pages/ResultsPage'

function AppRoutes() {
  const { connected } = useAppState()
  if (!connected) return <ConnectionPage />
  return <Routes><Route element={<AppLayout />}><Route index element={<DashboardPage />} /><Route path="projects" element={<ProjectsPage />} /><Route path="projects/new" element={<NewProjectPage />} /><Route path="projects/:id" element={<ProjectDetailPage />} /><Route path="projects/:id/access" element={<AccessPage />} /><Route path="modalities" element={<ModalitiesPage />} /><Route path="executions/new" element={<NewExecutionPage />} /><Route path="executions/:id" element={<ExecutionPage />} /><Route path="executions/:id/findings/:findingId" element={<FindingDetailPage />} /><Route path="results" element={<ResultsPage />} /><Route path="*" element={<Navigate to="/" replace />} /></Route></Routes>
}

export default function App() { return <BrowserRouter><AppProvider><AppRoutes /></AppProvider></BrowserRouter> }
