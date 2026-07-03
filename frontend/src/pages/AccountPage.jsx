/**
 * Account page — the personalized dashboard for signed-in users.
 *  - Profile & default dashboard filters (role/country)
 *  - Saved searches (apply / delete)
 *  - Resume analysis history
 */
import { useState } from 'react'
import { Navigate, useNavigate, useOutletContext, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  User, Bookmark, FileText, Trash2, Play, Save, LogOut, Clock,
} from 'lucide-react'
import { userApi } from '../api'
import { useAuth } from '../context/AuthContext'
import { Card, Spinner, Badge, EmptyState } from '../components/ui'
import { getCountryDisplay } from '../utils/helpers'

function formatDate(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
    })
  } catch {
    return iso
  }
}

export default function AccountPage() {
  const { user, loading, signOut } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { setSelectedRole, setSelectedCountry, roles, countries } = useOutletContext()

  const [displayName, setDisplayName] = useState(null) // null = untouched
  const [defaultRole, setDefaultRole] = useState(null)
  const [defaultCountry, setDefaultCountry] = useState(null)
  const [saveMsg, setSaveMsg] = useState('')

  const enabled = Boolean(user)

  const { data: profile, isLoading: profileLoading } = useQuery({
    queryKey: ['user', 'profile'],
    queryFn: userApi.getProfile,
    enabled,
  })
  const { data: savedSearches, isLoading: searchesLoading } = useQuery({
    queryKey: ['user', 'saved-searches'],
    queryFn: userApi.getSavedSearches,
    enabled,
  })
  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ['user', 'resume-history'],
    queryFn: userApi.getResumeHistory,
    enabled,
  })

  const updateProfile = useMutation({
    mutationFn: (updates) => userApi.updateProfile(updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user', 'profile'] })
      setSaveMsg('Saved!')
      setTimeout(() => setSaveMsg(''), 2500)
    },
  })
  const deleteSearch = useMutation({
    mutationFn: (id) => userApi.deleteSavedSearch(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['user', 'saved-searches'] }),
  })
  const deleteAnalysis = useMutation({
    mutationFn: (id) => userApi.deleteResumeAnalysis(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['user', 'resume-history'] }),
  })

  if (loading) {
    return <div className="flex justify-center py-20"><Spinner size="lg" /></div>
  }
  if (!user) return <Navigate to="/login" replace />

  const applySearch = (search) => {
    setSelectedRole(search.role)
    setSelectedCountry(search.country || '')
    navigate('/')
  }

  const handleSaveProfile = () => {
    updateProfile.mutate({
      display_name: displayName ?? undefined,
      default_role: defaultRole ?? undefined,
      default_country: defaultCountry ?? undefined,
    })
  }

  const avatarUrl = user.user_metadata?.avatar_url || profile?.avatar_url

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {avatarUrl ? (
            <img src={avatarUrl} alt="" className="h-14 w-14 rounded-full border border-gray-200 dark:border-gray-700" referrerPolicy="no-referrer" />
          ) : (
            <div className="h-14 w-14 rounded-full bg-primary-100 dark:bg-primary-900/40 flex items-center justify-center">
              <User className="h-7 w-7 text-primary-600 dark:text-primary-400" />
            </div>
          )}
          <div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
              {profile?.display_name || user.email}
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">{user.email}</p>
          </div>
        </div>
        <button
          onClick={async () => { await signOut(); navigate('/') }}
          className="btn-secondary flex items-center gap-2 text-sm"
        >
          <LogOut className="h-4 w-4" /> Sign out
        </button>
      </div>

      {/* Profile & preferences */}
      <Card title="Profile & Dashboard Defaults">
        {profileLoading ? <Spinner /> : (
          <div className="space-y-4">
            <div className="grid sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Display name</label>
                <input
                  className="select-input"
                  value={displayName ?? profile?.display_name ?? ''}
                  onChange={(e) => setDisplayName(e.target.value)}
                  maxLength={100}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Default role</label>
                <select
                  className="select-input"
                  value={defaultRole ?? profile?.default_role ?? ''}
                  onChange={(e) => setDefaultRole(e.target.value)}
                >
                  <option value="">— none —</option>
                  {roles.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">Default country</label>
                <select
                  className="select-input"
                  value={defaultCountry ?? profile?.default_country ?? ''}
                  onChange={(e) => setDefaultCountry(e.target.value)}
                >
                  <option value="">All countries</option>
                  {countries.map((c) => (
                    <option key={c.country_code} value={c.country_code}>{c.country_name}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleSaveProfile}
                disabled={updateProfile.isPending}
                className="btn-primary flex items-center gap-2 text-sm"
              >
                {updateProfile.isPending ? <Spinner size="sm" /> : <Save className="h-4 w-4" />}
                Save preferences
              </button>
              {saveMsg && <span className="text-sm text-green-600 dark:text-green-400">{saveMsg}</span>}
            </div>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              Your default role and country are applied to the dashboard filters each time you visit.
            </p>
          </div>
        )}
      </Card>

      {/* Saved searches */}
      <Card title="Saved Searches">
        {searchesLoading ? <Spinner /> : !savedSearches?.length ? (
          <EmptyState
            icon={<Bookmark className="h-12 w-12 text-gray-300 dark:text-gray-600 mb-3" />}
            title="No saved searches yet"
            description="Set a role and country in the sidebar, then click the bookmark icon in the top bar to save the search."
          />
        ) : (
          <ul className="divide-y divide-gray-100 dark:divide-gray-700">
            {savedSearches.map((s) => (
              <li key={s.id} className="py-3 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium text-gray-900 dark:text-gray-100 truncate">{s.name}</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {s.role} · {s.country ? getCountryDisplay(s.country) : 'All countries'}
                  </p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    onClick={() => applySearch(s)}
                    className="btn-secondary flex items-center gap-1.5 text-sm"
                    title="Apply this search to the dashboard"
                  >
                    <Play className="h-3.5 w-3.5" /> Apply
                  </button>
                  <button
                    onClick={() => deleteSearch.mutate(s.id)}
                    className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Resume history */}
      <Card title="Resume Analysis History">
        {historyLoading ? <Spinner /> : !history?.length ? (
          <EmptyState
            icon={<FileText className="h-12 w-12 text-gray-300 dark:text-gray-600 mb-3" />}
            title="No analyses yet"
            description="Analyses you run while signed in appear here."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 dark:text-gray-400 uppercase">
                  <th className="pb-2 pr-4">File</th>
                  <th className="pb-2 pr-4">Type</th>
                  <th className="pb-2 pr-4">Role</th>
                  <th className="pb-2 pr-4">Score</th>
                  <th className="pb-2 pr-4"><Clock className="h-3.5 w-3.5 inline" /> Date</th>
                  <th className="pb-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {history.map((h) => (
                  <tr key={h.id}>
                    <td className="py-2.5 pr-4 font-medium text-gray-900 dark:text-gray-100 max-w-[200px] truncate">
                      {h.filename}
                    </td>
                    <td className="py-2.5 pr-4">
                      <Badge variant={h.analysis_type === 'gap_analysis' ? 'primary' : 'default'}>
                        {h.analysis_type === 'gap_analysis' ? 'Gap Analysis' : 'Role Match'}
                      </Badge>
                    </td>
                    <td className="py-2.5 pr-4 text-gray-600 dark:text-gray-300">{h.target_role || '—'}</td>
                    <td className="py-2.5 pr-4 text-gray-600 dark:text-gray-300">
                      {h.match_score != null ? `${h.match_score}%` : '—'}
                    </td>
                    <td className="py-2.5 pr-4 text-gray-500 dark:text-gray-400">{formatDate(h.uploaded_at)}</td>
                    <td className="py-2.5 text-right">
                      <button
                        onClick={() => deleteAnalysis.mutate(h.id)}
                        className="p-1.5 text-gray-400 hover:text-red-500 transition-colors"
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-3">
          Run a new analysis on the <Link to="/resume" className="text-primary-600 dark:text-primary-400 hover:underline">Resume Analyzer</Link> page — signed-in analyses are saved here automatically.
        </p>
      </Card>
    </div>
  )
}
