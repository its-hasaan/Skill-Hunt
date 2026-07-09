import { useState, useEffect, useRef } from 'react'
import { Outlet, NavLink, Link, useNavigate } from 'react-router-dom'
import {
  Target, BarChart3, DollarSign, Building2,
  GitBranch, Globe, Menu, X, FileText, Sun, Moon,
  Bookmark, BookmarkCheck, LogIn, UserCircle, LogOut
} from 'lucide-react'
import clsx from 'clsx'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useFilterOptions } from '../hooks/useData'
import { useTheme } from '../context/ThemeContext'
import { useAuth } from '../context/AuthContext'
import { userApi } from '../api'
import { getCountryFlag } from '../utils/helpers'

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
  const [justSaved, setJustSaved] = useState(false)
  const { isDark, toggleTheme } = useTheme()
  const { user, isAuthEnabled, signOut } = useAuth()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const { data: filters, isLoading: filtersLoading } = useFilterOptions()

  // Signed-in users get their saved dashboard defaults applied once per visit.
  const { data: profile } = useQuery({
    queryKey: ['user', 'profile'],
    queryFn: userApi.getProfile,
    enabled: Boolean(user),
    retry: 1,
  })
  const defaultsApplied = useRef(false)
  useEffect(() => {
    if (defaultsApplied.current || !profile || !filters?.roles?.length) return
    if (profile.default_role && filters.roles.includes(profile.default_role)) {
      setSelectedRole(profile.default_role)
    }
    if (profile.default_country) {
      setSelectedCountry(profile.default_country)
    }
    defaultsApplied.current = true
  }, [profile, filters])

  // Set default role once filters load
  if (filters?.roles?.length && !selectedRole) {
    setSelectedRole(filters.roles[0])
  }

  const handleSaveSearch = async () => {
    if (!user || !selectedRole) return
    const countryName = filters?.countries?.find(c => c.country_code === selectedCountry)?.country_name
    const name = selectedCountry ? `${selectedRole} — ${countryName || selectedCountry}` : selectedRole
    try {
      await userApi.saveSearch(name, selectedRole, selectedCountry || null)
      queryClient.invalidateQueries({ queryKey: ['user', 'saved-searches'] })
      setJustSaved(true)
      setTimeout(() => setJustSaved(false), 2000)
    } catch (e) {
      console.error('Failed to save search', e)
    }
  }

  const handleSignOut = async () => {
    await signOut()
    navigate('/')
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
        <div className="flex items-center gap-3 h-14 px-6 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <img src="/logo.png" alt="Job Script" className="h-8 w-8 flex-shrink-0" />
          <span className="text-lg font-bold text-gray-900 dark:text-gray-100">Job Script</span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-3 space-y-1 overflow-y-auto">
          {navigation.map((item) => (
            <NavLink
              key={item.name}
              to={item.href}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) => clsx(
                'flex items-center gap-3 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
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

          {/* Country selector — fully dynamic: every country we have data for */}
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1 px-3">
              Country
              {filters?.countries?.length ? (
                <span className="text-gray-400 dark:text-gray-500 font-normal"> ({filters.countries.length})</span>
              ) : null}
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
                  {getCountryFlag(country.country_code)} {country.country_name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-30 h-14 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center px-4 lg:px-6 transition-colors duration-200">
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
              Skill demand insights from job postings
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

          {/* Save current search (signed-in only) */}
          {user && (
            <button
              onClick={handleSaveSearch}
              disabled={!selectedRole}
              className="ml-2 p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors disabled:opacity-40"
              title={justSaved ? 'Saved!' : 'Save current search to your account'}
            >
              {justSaved
                ? <BookmarkCheck className="h-5 w-5 text-green-500" />
                : <Bookmark className="h-5 w-5" />}
            </button>
          )}

          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            className="ml-2 p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>

          {/* Auth: avatar with hover menu, or sign-in link */}
          {isAuthEnabled && (
            user ? (
              <div className="relative ml-2 group">
                <button className="flex items-center" title={user.email}>
                  {user.user_metadata?.avatar_url ? (
                    <img
                      src={user.user_metadata.avatar_url}
                      alt="Account"
                      referrerPolicy="no-referrer"
                      className="h-8 w-8 rounded-full border border-gray-200 dark:border-gray-600 group-hover:ring-2 group-hover:ring-primary-400 transition-shadow"
                    />
                  ) : (
                    <span className="h-8 w-8 rounded-full bg-primary-100 dark:bg-primary-900/40 flex items-center justify-center text-sm font-semibold text-primary-700 dark:text-primary-300 group-hover:ring-2 group-hover:ring-primary-400 transition-shadow">
                      {(user.email || '?')[0].toUpperCase()}
                    </span>
                  )}
                </button>

                {/* Hover dropdown — pt-2 bridges the gap so hover doesn't drop */}
                <div className="absolute right-0 top-full pt-2 w-52 invisible opacity-0 group-hover:visible group-hover:opacity-100 transition-opacity z-50">
                  <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg py-1">
                    <div className="px-4 py-2 border-b border-gray-100 dark:border-gray-700">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                        {user.email}
                      </p>
                    </div>
                    <Link
                      to="/account"
                      className="flex items-center gap-2 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                    >
                      <UserCircle className="h-4 w-4" /> My Account
                    </Link>
                    <button
                      onClick={handleSignOut}
                      className="w-full flex items-center gap-2 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                    >
                      <LogOut className="h-4 w-4" /> Sign out
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <Link
                to="/login"
                className="ml-2 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-primary-600 dark:text-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/30 transition-colors"
              >
                <LogIn className="h-4 w-4" />
                <span className="hidden sm:inline">Sign in</span>
              </Link>
            )
          )}
        </header>

        {/* Page content */}
        <main className="p-3 lg:p-5">
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
