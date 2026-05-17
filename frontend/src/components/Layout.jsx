import { useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import { 
  Target, BarChart3, DollarSign, Building2, 
  GitBranch, Globe, Menu, X, FileText, Sun, Moon
} from 'lucide-react'
import clsx from 'clsx'
import { useFilterOptions } from '../hooks/useData'
import { useTheme } from '../context/ThemeContext'

const navigation = [
  { name: 'Dashboard', href: '/', icon: BarChart3 },
  { name: 'Skills', href: '/skills', icon: Target },
  { name: 'Salary', href: '/salary', icon: DollarSign },
  { name: 'Companies', href: '/companies', icon: Building2 },
  { name: 'Career Paths', href: '/career', icon: GitBranch },
  { name: 'Global', href: '/global', icon: Globe },
  { name: 'Resume Analyzer', href: '/resume', icon: FileText },
]

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [selectedRole, setSelectedRole] = useState('')
  const [selectedCountry, setSelectedCountry] = useState('')
  const { isDark, toggleTheme } = useTheme()
  
  const { data: filters, isLoading: filtersLoading } = useFilterOptions()

  // Set default role once filters load
  if (filters?.roles?.length && !selectedRole) {
    setSelectedRole(filters.roles[0])
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 transition-colors duration-200">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-gray-900/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={clsx(
        'fixed inset-y-0 left-0 z-50 w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 transform transition-transform duration-200 lg:translate-x-0 flex flex-col',
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      )}>
        {/* Logo */}
        <div className="flex items-center gap-3 h-16 px-6 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <div className="h-9 w-9 rounded-full overflow-hidden flex-shrink-0">
            <img src="/logo.png" alt="Skill Hunt" className="w-full h-full object-cover scale-[1.35] object-center" />
          </div>
          <span className="text-xl font-bold text-gray-900 dark:text-gray-100">Skill Hunt</span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-4 space-y-1 overflow-y-auto">
          {navigation.map((item) => (
            <NavLink
              key={item.name}
              to={item.href}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) => clsx(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                isActive 
                  ? 'bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400' 
                  : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-gray-100'
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.name}
            </NavLink>
          ))}
        </nav>

        {/* Filters */}
        <div className="px-4 py-4 border-t border-gray-200 dark:border-gray-700 flex-shrink-0">
          <h3 className="px-3 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
            Filters
          </h3>
          
          {/* Role selector */}
          <div className="mb-3">
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1 px-3">
              Job Role
            </label>
            <select
              value={selectedRole}
              onChange={(e) => setSelectedRole(e.target.value)}
              className="select-input text-sm"
              disabled={filtersLoading}
            >
              {filtersLoading ? (
                <option>Loading...</option>
              ) : (
                filters?.roles?.map((role) => (
                  <option key={role} value={role}>{role}</option>
                ))
              )}
            </select>
          </div>

          {/* Country selector */}
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1 px-3">
              Country
            </label>
            <select
              value={selectedCountry}
              onChange={(e) => setSelectedCountry(e.target.value)}
              className="select-input text-sm"
              disabled={filtersLoading}
            >
              <option value="">All Countries</option>
              {filters?.countries?.map((country) => (
                <option key={country.country_code} value={country.country_code}>
                  {country.country_name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-30 h-16 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center px-4 lg:px-6 transition-colors duration-200">
          {/* Mobile menu button */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="lg:hidden p-2 -ml-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
          >
            {sidebarOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>

          {/* Breadcrumb / Title */}
          <div className="flex-1 ml-2 lg:ml-0">
            <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Tech Job Market Analysis
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 hidden sm:block">
              Real-time skill demand insights from job postings
            </p>
          </div>

          {/* Quick filters (desktop) */}
          <div className="hidden md:flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500 dark:text-gray-400">Role:</span>
              <span className="text-sm font-medium text-gray-900 dark:text-gray-200">
                {selectedRole || 'All'}
              </span>
            </div>
            {selectedCountry && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500 dark:text-gray-400">Country:</span>
                <span className="text-sm font-medium text-gray-900 dark:text-gray-200">
                  {filters?.countries?.find(c => c.country_code === selectedCountry)?.country_name || selectedCountry}
                </span>
              </div>
            )}
          </div>

          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            className="ml-4 p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>
        </header>

        {/* Page content */}
        <main className="p-4 lg:p-6">
          <Outlet context={{ 
            selectedRole, 
            selectedCountry, 
            setSelectedRole, 
            setSelectedCountry,
            roles: filters?.roles || [],
            countries: filters?.countries || []
          }} />
        </main>
      </div>
    </div>
  )
}
