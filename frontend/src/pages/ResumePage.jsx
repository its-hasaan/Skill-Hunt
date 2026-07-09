import { useState, useCallback } from 'react'
import { useOutletContext } from 'react-router-dom'
import {
  Upload, FileText, Target, CheckCircle2, XCircle,
  AlertCircle, TrendingUp
} from 'lucide-react'
import { Card, ChartLoading, EmptyState, Spinner } from '../components/ui'
import { resumeApi } from '../api'

// File upload component
function FileUpload({ onFileSelect, file, loading }) {
  const [dragActive, setDragActive] = useState(false)

  const handleDrag = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onFileSelect(e.dataTransfer.files[0])
    }
  }, [onFileSelect])

  const handleChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      onFileSelect(e.target.files[0])
    }
  }

  return (
    <div
      className={`
        relative border-2 border-dashed rounded-xl p-8 text-center transition-all
        ${dragActive ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20' : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500'}
        ${loading ? 'opacity-50 pointer-events-none' : ''}
      `}
      onDragEnter={handleDrag}
      onDragLeave={handleDrag}
      onDragOver={handleDrag}
      onDrop={handleDrop}
    >
      <input
        type="file"
        accept=".pdf,.docx,.doc,.txt,.md,.png,.jpg,.jpeg"
        onChange={handleChange}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        disabled={loading}
      />
      
      {file ? (
        <div className="flex items-center justify-center gap-3">
          <FileText className="h-10 w-10 text-primary-600" />
          <div className="text-left">
            <p className="font-medium text-gray-900 dark:text-gray-100">{file.name}</p>
            <p className="text-sm text-gray-500 dark:text-gray-400">{(file.size / 1024).toFixed(1)} KB</p>
          </div>
          <CheckCircle2 className="h-6 w-6 text-green-500" />
        </div>
      ) : (
        <>
          <Upload className="h-12 w-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
          <p className="text-lg font-medium text-gray-700 dark:text-gray-300 mb-2">
            Drop your resume here
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
            or click to browse files
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-500">
            Supports PDF, DOCX, DOC, TXT, and images (PNG, JPG)
          </p>
        </>
      )}
    </div>
  )
}

// Skill Badge component
function SkillBadge({ skill, type = 'neutral' }) {
  const colors = {
    have: 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 border-green-200 dark:border-green-800',
    need: 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300 border-red-200 dark:border-red-800',
    neutral: 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300 border-gray-200 dark:border-gray-600',
  }

  return (
    <span className={`
      inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border
      ${colors[type]}
    `}>
      {type === 'have' && <CheckCircle2 className="h-3.5 w-3.5 mr-1" />}
      {type === 'need' && <XCircle className="h-3.5 w-3.5 mr-1" />}
      {skill}
    </span>
  )
}

// Match Score Gauge
function MatchGauge({ score }) {
  const getColor = (score) => {
    if (score >= 70) return 'text-green-600'
    if (score >= 40) return 'text-yellow-600'
    return 'text-red-600'
  }

  const getLabel = (score) => {
    if (score >= 70) return 'Strong Match'
    if (score >= 40) return 'Moderate Match'
    return 'Needs Improvement'
  }

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-32 h-32">
        <svg className="w-32 h-32 transform -rotate-90">
          <circle
            cx="64"
            cy="64"
            r="56"
            stroke="#e5e7eb"
            strokeWidth="12"
            fill="none"
          />
          <circle
            cx="64"
            cy="64"
            r="56"
            stroke="currentColor"
            strokeWidth="12"
            fill="none"
            strokeDasharray={`${score * 3.52} 352`}
            className={getColor(score)}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={`text-3xl font-bold ${getColor(score)}`}>{score}%</span>
        </div>
      </div>
      <p className={`mt-2 font-medium ${getColor(score)}`}>{getLabel(score)}</p>
    </div>
  )
}

// Role Match Card
function RoleMatchCard({ match, rank }) {
  const getScoreColor = (score) => {
    if (score >= 70) return 'bg-green-500'
    if (score >= 40) return 'bg-yellow-500'
    return 'bg-red-500'
  }

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`
            w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-sm
            ${rank === 1 ? 'bg-yellow-500' : rank === 2 ? 'bg-gray-400' : rank === 3 ? 'bg-amber-600' : 'bg-gray-300 dark:bg-gray-600'}
          `}>
            {rank}
          </div>
          <div>
            <h4 className="font-semibold text-gray-900 dark:text-gray-100">{match.role}</h4>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {match.matched_skills_count} of {match.total_skills_evaluated} skills matched
            </p>
          </div>
        </div>
        <div className="text-right">
          <div className={`
            inline-flex items-center px-3 py-1 rounded-full text-white font-bold
            ${getScoreColor(match.match_score)}
          `}>
            {match.match_score}%
          </div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2 mb-3">
        <div 
          className={`h-2 rounded-full transition-all ${getScoreColor(match.match_score)}`}
          style={{ width: `${match.match_score}%` }}
        />
      </div>

      {/* Top matched skills */}
      {match.top_matched_skills?.length > 0 && (
        <div className="mb-2">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Your matching skills:</p>
          <div className="flex flex-wrap gap-1">
            {match.top_matched_skills.slice(0, 4).map((skill, i) => (
              <span key={i} className="text-xs bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 px-2 py-0.5 rounded">
                {skill.skill_name}
              </span>
            ))}
            {match.top_matched_skills.length > 4 && (
              <span className="text-xs text-gray-500 dark:text-gray-400">+{match.top_matched_skills.length - 4} more</span>
            )}
          </div>
        </div>
      )}

      {/* Top missing skills */}
      {match.top_missing_skills?.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Skills to learn:</p>
          <div className="flex flex-wrap gap-1">
            {match.top_missing_skills.slice(0, 3).map((skill, i) => (
              <span key={i} className="text-xs bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 px-2 py-0.5 rounded">
                {skill.skill_name}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function ResumePage() {
  const { selectedRole, selectedCountry, roles } = useOutletContext()
  
  const [file, setFile] = useState(null)
  const [targetRole, setTargetRole] = useState(selectedRole || '')
  const [activeTab, setActiveTab] = useState('gap-analysis')
  
  // Analysis states
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [gapAnalysis, setGapAnalysis] = useState(null)
  const [roleMatches, setRoleMatches] = useState(null)

  const handleFileSelect = (selectedFile) => {
    setFile(selectedFile)
    setError(null)
    // Reset results when new file is selected
    setGapAnalysis(null)
    setRoleMatches(null)
  }

  const handleAnalyze = async () => {
    if (!file) {
      setError('Please upload a resume first')
      return
    }

    if (activeTab === 'gap-analysis' && !targetRole) {
      setError('Please select a target role')
      return
    }

    setLoading(true)
    setError(null)

    try {
      if (activeTab === 'gap-analysis') {
        const result = await resumeApi.analyze(file, targetRole, selectedCountry)
        setGapAnalysis(result)
      } else {
        const result = await resumeApi.matchRoles(file, selectedCountry, 15)
        setRoleMatches(result)
      }
    } catch (err) {
      console.error('Analysis error:', err)
      setError(err.response?.data?.detail || 'Failed to analyze resume. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-primary-600 to-accent-600 rounded-2xl p-8 text-white">
        <div className="flex items-center gap-3 mb-2">
          <Target className="h-8 w-8" />
          <h1 className="text-3xl font-bold">Resume Analyzer</h1>
        </div>
        <p className="text-white/80 text-lg">
          Upload your resume to discover your skill match with market demand and find your best-fit roles
        </p>
      </div>

      {/* Upload and Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* File Upload */}
        <Card title="1. Upload Resume" className="lg:col-span-2">
          <FileUpload file={file} onFileSelect={handleFileSelect} loading={loading} />
        </Card>

        {/* Analysis Options */}
        <Card title="2. Choose Analysis">
          <div className="space-y-4">
            {/* Tab Selection */}
            <div className="flex gap-2 p-1 bg-gray-100 dark:bg-gray-700 rounded-lg">
              <button
                onClick={() => setActiveTab('gap-analysis')}
                className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-all ${
                  activeTab === 'gap-analysis'
                    ? 'bg-white dark:bg-gray-600 text-primary-700 dark:text-primary-400 shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                }`}
              >
                Gap Analysis
              </button>
              <button
                onClick={() => setActiveTab('role-match')}
                className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-all ${
                  activeTab === 'role-match'
                    ? 'bg-white dark:bg-gray-600 text-primary-700 dark:text-primary-400 shadow-sm'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                }`}
              >
                Role Match
              </button>
            </div>

            {/* Target Role (only for gap analysis) */}
            {activeTab === 'gap-analysis' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Target Role
                </label>
                <select
                  value={targetRole}
                  onChange={(e) => setTargetRole(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                >
                  <option value="">Select a role...</option>
                  {roles?.map((role) => (
                    <option key={role} value={role}>{role}</option>
                  ))}
                </select>
              </div>
            )}

            {/* Analyze Button */}
            <button
              onClick={handleAnalyze}
              disabled={loading || !file || (activeTab === 'gap-analysis' && !targetRole)}
              className={`
                w-full py-3 px-4 rounded-lg font-medium flex items-center justify-center gap-2
                transition-all
                ${loading || !file || (activeTab === 'gap-analysis' && !targetRole)
                  ? 'bg-gray-300 dark:bg-gray-600 text-gray-500 dark:text-gray-400 cursor-not-allowed'
                  : 'bg-primary-600 text-white hover:bg-primary-700 shadow-lg hover:shadow-xl'
                }
              `}
            >
              {loading ? (
                <>
                  <Spinner size="sm" />
                  Analyzing...
                </>
              ) : (
                <>
                  <TrendingUp className="h-5 w-5" />
                  {activeTab === 'gap-analysis' ? 'Analyze Skills Gap' : 'Find Matching Roles'}
                </>
              )}
            </button>

            {/* Error Message */}
            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400 text-sm">
                <AlertCircle className="h-5 w-5 flex-shrink-0" />
                {error}
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Results */}
      {loading && (
        <Card>
          <ChartLoading height={300} />
        </Card>
      )}

      {/* Gap Analysis Results */}
      {!loading && gapAnalysis && activeTab === 'gap-analysis' && (
        <div className="space-y-6">
          {/* Summary */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card className="flex items-center justify-center py-8">
              <MatchGauge score={gapAnalysis.match_percentage} />
            </Card>
            
            <Card title="Your Matching Skills" className="md:col-span-2">
              <div className="flex flex-wrap gap-2">
                {gapAnalysis.skills_you_have?.length > 0 ? (
                  gapAnalysis.skills_you_have.map((skill, i) => (
                    <SkillBadge key={i} skill={skill.skill_name} type="have" />
                  ))
                ) : (
                  <p className="text-gray-500">No matching skills found</p>
                )}
              </div>
            </Card>
          </div>

          {/* Skills to Learn */}
          <Card 
            title="Skills to Learn"
            headerAction={
              <span className="text-sm text-gray-500">
                Sorted by market demand
              </span>
            }
          >
            {gapAnalysis.skills_you_need?.length > 0 ? (
              <div className="space-y-3">
                {gapAnalysis.skills_you_need.slice(0, 15).map((skill, i) => (
                  <div 
                    key={i}
                    className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <span className={`
                        w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold
                        ${i < 5 ? 'bg-red-500 text-white' : 'bg-gray-300 dark:bg-gray-600 text-gray-600 dark:text-gray-300'}
                      `}>
                        {i + 1}
                      </span>
                      <div>
                        <span className="font-medium text-gray-900 dark:text-gray-100">{skill.skill_name}</span>
                        <span className="text-sm text-gray-500 dark:text-gray-400 ml-2">({skill.skill_category})</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {skill.job_count?.toLocaleString()} jobs
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {skill.demand_percentage?.toFixed(1)}% of postings
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState 
                title="Great job!" 
                description="You have all the top skills for this role!"
              />
            )}
          </Card>

          {/* All Resume Skills */}
          <Card title={`All Skills Found (${gapAnalysis.total_resume_skills})`}>
            <div className="flex flex-wrap gap-2">
              {gapAnalysis.resume_skills?.map((skill, i) => (
                <span 
                  key={i}
                  className="px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-full text-sm"
                >
                  {skill.skill_name}
                  {skill.mention_count > 1 && (
                    <span className="ml-1 text-gray-400 dark:text-gray-500">×{skill.mention_count}</span>
                  )}
                </span>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* Role Match Results */}
      {!loading && roleMatches && activeTab === 'role-match' && (
        <Card 
          title="Your Best Role Matches"
          headerAction={
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Based on skill overlap with market demand
            </span>
          }
        >
          {roleMatches.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {roleMatches.map((match, i) => (
                <RoleMatchCard key={i} match={match} rank={i + 1} />
              ))}
            </div>
          ) : (
            <EmptyState 
              title="No matches found" 
              description="We couldn't match your skills to any roles. Try uploading a different resume."
            />
          )}
        </Card>
      )}

      {/* Instructions */}
      {!loading && !gapAnalysis && !roleMatches && (
        <Card title="How It Works">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div>
              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Gap Analysis
              </h4>
              <p className="text-gray-600 dark:text-gray-400 mb-3">
                Compare your skills against market demand for a specific role.
              </p>
              <ul className="space-y-2 text-sm text-gray-500 dark:text-gray-400 list-disc list-inside">
                <li>See which of your skills are in high demand</li>
                <li>Discover skill gaps to fill for your target role</li>
                <li>Get a match score based on real job market data</li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">
                Role Match
              </h4>
              <p className="text-gray-600 dark:text-gray-400 mb-3">
                Find which job roles best match your current skillset.
              </p>
              <ul className="space-y-2 text-sm text-gray-500 dark:text-gray-400 list-disc list-inside">
                <li>Automatically match against all tracked roles</li>
                <li>Weighted scoring based on skill importance</li>
                <li>Discover career paths you hadn't considered</li>
              </ul>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
