import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import SkillsPage from './pages/SkillsPage'
import SalaryPage from './pages/SalaryPage'
import CompaniesPage from './pages/CompaniesPage'
import CareerPage from './pages/CareerPage'
import GlobalPage from './pages/GlobalPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="skills" element={<SkillsPage />} />
          <Route path="salary" element={<SalaryPage />} />
          <Route path="companies" element={<CompaniesPage />} />
          <Route path="career" element={<CareerPage />} />
          <Route path="global" element={<GlobalPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
