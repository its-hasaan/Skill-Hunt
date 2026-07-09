import { useState, useEffect, useRef } from 'react'
import { useOutletContext, useNavigate } from 'react-router-dom'
import { X, Plus, TrendingUp } from 'lucide-react'
import { useSkillDemand, useSkillCooccurrence, useSkillTrend } from '../hooks/useData'
import { Card, ChartLoading, EmptyState, ErrorState, Tabs } from '../components/ui'
import { CategoryBarChart, CategoryPieChart, SkillTrendChart, useChartColors } from '../components/charts/Charts'
import { formatNumber } from '../utils/helpers'

const MAX_TREND_SKILLS = 5

export default function SkillsPage() {
  const { selectedRole, selectedCountry } = useOutletContext()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('demand')
  const [selectedSkill, setSelectedSkill] = useState(null)

  // --- Trend state -------------------------------------------------------
  // Each tracked skill keeps its color slot until removed, so removing one
  // line never repaints the others.
  const [trendSkills, setTrendSkills] = useState([])
  const [trendMonths, setTrendMonths] = useState(6)
  const slotMap = useRef({})
  const seededForRole = useRef(null)
  const chartColors = useChartColors()

  const assignSlot = (skill) => {
    if (slotMap.current[skill] !== undefined) return
    const used = new Set(Object.values(slotMap.current))
    for (let i = 0; i < MAX_TREND_SKILLS; i++) {
      if (!used.has(i)) { slotMap.current[skill] = i; return }
    }
  }

  const addTrendSkill = (skill) => {
    if (!skill || trendSkills.includes(skill) || trendSkills.length >= MAX_TREND_SKILLS) return
    assignSlot(skill)
    setTrendSkills((prev) => [...prev, skill])
  }

  const removeTrendSkill = (skill) => {
    delete slotMap.current[skill]
    setTrendSkills((prev) => prev.filter((s) => s !== skill))
  }

  const openJobs = (skillName) => {
    if (!selectedRole || !skillName) return
    const params = new URLSearchParams({ skill: skillName, role: selectedRole })
    if (selectedCountry) params.set('country', selectedCountry)
    navigate(`/jobs?${params.toString()}`)
  }

  const { data: skillDemand, isLoading: demandLoading, isError: demandError, refetch: refetchDemand } = useSkillDemand(
    selectedRole, 
    selectedCountry || null, 
    30
  )

  const { data: cooccurrence, isLoading: coocLoading } = useSkillCooccurrence(
    selectedRole,
    selectedSkill,
    5
  )

  const { data: trend, isLoading: trendLoading } = useSkillTrend(
    trendSkills,
    selectedRole || null,
    selectedCountry || null,
    trendMonths
  )

  // Seed the trend with the role's top 3 skills whenever the role changes.
  useEffect(() => {
    if (!selectedRole || !skillDemand?.data?.length) return
    if (seededForRole.current === selectedRole) return
    seededForRole.current = selectedRole
    slotMap.current = {}
    const top3 = skillDemand.data.slice(0, 3).map((s) => s.skill_name)
    top3.forEach(assignSlot)
    setTrendSkills(top3)
  }, [selectedRole, skillDemand])

  const tabs = [
    { id: 'demand', label: 'Top Skills' },
    { id: 'connections', label: 'Skill Connections' },
  ]

  // Get unique skills for dropdown
  const skillOptions = skillDemand?.data?.map(s => s.skill_name) || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Skills Analysis</h1>
          <p className="text-gray-600 dark:text-gray-400">
            {selectedRole ? `Skills for ${selectedRole}` : 'Select a role to see skills'}
          </p>
        </div>
        <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />
      </div>

      {activeTab === 'demand' && (
        <>
        {/* Demand trend over time */}
        <Card
          title="Skill Demand Over Time"
          headerAction={
            <div className="flex items-center gap-1">
              {[6, 12, 24].map((m) => (
                <button
                  key={m}
                  onClick={() => setTrendMonths(m)}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                    trendMonths === m
                      ? 'bg-primary-100 dark:bg-primary-900/40 text-primary-700 dark:text-primary-300'
                      : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
                  }`}
                >
                  {m === 24 ? 'All' : `${m}m`}
                </button>
              ))}
            </div>
          }
        >
          <p className="text-sm text-gray-500 dark:text-gray-400 -mt-2 mb-4">
            Share of {selectedRole} postings mentioning each skill, by month posted
            {selectedCountry ? '' : ' (all countries)'}. Percentages are comparable
            across months even when posting volume varies.
          </p>

          {/* Tracked-skill chips + add control */}
          <div className="flex flex-wrap items-center gap-2 mb-4">
            {trendSkills.map((skill) => (
              <span
                key={skill}
                className="inline-flex items-center gap-1.5 pl-2.5 pr-1.5 py-1 rounded-full text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200"
              >
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: chartColors.series(slotMap.current[skill] ?? 0) }}
                />
                {skill}
                <button
                  onClick={() => removeTrendSkill(skill)}
                  className="p-0.5 rounded-full hover:bg-gray-200 dark:hover:bg-gray-600"
                  aria-label={`Remove ${skill} from trend`}
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
            {trendSkills.length < MAX_TREND_SKILLS && skillOptions.length > 0 && (
              <div className="relative inline-flex items-center">
                <Plus className="absolute left-2 h-3.5 w-3.5 text-gray-400 pointer-events-none" />
                <select
                  value=""
                  onChange={(e) => addTrendSkill(e.target.value)}
                  className="pl-7 pr-6 py-1 rounded-full text-xs font-medium bg-transparent border border-dashed border-gray-300 dark:border-gray-600 text-gray-500 dark:text-gray-400 cursor-pointer focus:outline-none"
                  aria-label="Add skill to trend"
                >
                  <option value="">Add skill</option>
                  {skillOptions.filter((s) => !trendSkills.includes(s)).map((skill) => (
                    <option key={skill} value={skill}>{skill}</option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {trendLoading && !trend ? (
            <ChartLoading height={360} />
          ) : trend?.periods?.length > 1 && trend?.series?.length > 0 ? (
            <SkillTrendChart
              periods={trend.periods}
              series={trend.series}
              colorMap={slotMap.current}
              height={360}
            />
          ) : trendSkills.length === 0 ? (
            <EmptyState
              icon={<TrendingUp className="h-12 w-12 text-gray-300 dark:text-gray-600 mb-3" />}
              title="Pick skills to track"
              description="Add up to 5 skills above to compare their demand over time."
            />
          ) : (
            <EmptyState
              icon={<TrendingUp className="h-12 w-12 text-gray-300 dark:text-gray-600 mb-3" />}
              title="Not enough history yet"
              description="Trend needs at least two months of postings for this selection. Try a longer range or remove the country filter."
            />
          )}
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Chart */}
          <Card title="Top 15 Skills by Job Count" className="lg:col-span-2">
            {demandLoading ? (
              <ChartLoading height={500} />
            ) : demandError ? (
              <ErrorState message="Could not reach the API — this is a connection problem, not missing data." onRetry={refetchDemand} />
            ) : skillDemand?.data?.length > 0 ? (
              <CategoryBarChart 
                data={skillDemand.data} 
                dataKey="job_count"
                nameKey="skill_name"
                categoryKey="skill_category"
                height={500} 
              />
            ) : (
              <EmptyState description="No skill data available" />
            )}
          </Card>

          {/* Category Breakdown */}
          <Card title="Skills by Category">
            {demandLoading ? (
              <ChartLoading height={300} />
            ) : skillDemand?.data?.length > 0 ? (
              <CategoryPieChart data={skillDemand.data} height={300} />
            ) : (
              <EmptyState />
            )}

            {/* Quick Stats */}
            {skillDemand?.data && (
              <div className="mt-6 space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">Total Skills:</span>
                  <span className="font-medium dark:text-gray-200">{skillDemand.total_count}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">Top Skill:</span>
                  <span className="font-medium dark:text-gray-200">{skillDemand.data[0]?.skill_name}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">Top Category:</span>
                  <span className="font-medium dark:text-gray-200">{skillDemand.data[0]?.skill_category || '-'}</span>
                </div>
              </div>
            )}
          </Card>
        </div>
        </>
      )}

      {activeTab === 'connections' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Skill Selector */}
          <Card title="Find Skill Connections">
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Select a skill to see what it pairs with:
              </label>
              <select
                value={selectedSkill || ''}
                onChange={(e) => setSelectedSkill(e.target.value || null)}
                className="select-input"
              >
                <option value="">Choose a skill...</option>
                {skillOptions.map(skill => (
                  <option key={skill} value={skill}>{skill}</option>
                ))}
              </select>
            </div>

            {selectedSkill && (
              coocLoading ? (
                <div className="space-y-2">
                  {[...Array(8)].map((_, i) => (
                    <div key={i} className="h-12 bg-gray-100 rounded animate-pulse" />
                  ))}
                </div>
              ) : cooccurrence?.length > 0 ? (
                <div className="space-y-2">
                  <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-3">
                    Skills that pair with {selectedSkill}:
                  </h4>
                  {cooccurrence.slice(0, 15).map((pair, index) => {
                    const otherSkill = pair.skill_name_1 === selectedSkill 
                      ? pair.skill_name_2 
                      : pair.skill_name_1
                    return (
                      <div 
                        key={index}
                        className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg"
                      >
                        <span className="font-medium text-gray-900 dark:text-gray-100">{otherSkill}</span>
                        <div className="text-right text-sm">
                          <div className="text-gray-600 dark:text-gray-400">
                            {formatNumber(pair.cooccurrence_count)} jobs
                          </div>
                          <div className="text-gray-400 dark:text-gray-500">
                            {(pair.jaccard_similarity * 100).toFixed(1)}% similarity
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <EmptyState description="No connection data for this skill" />
              )
            )}
          </Card>

          {/* Top Pairs */}
          <Card title="Top Skill Pairs">
            {coocLoading && !selectedSkill ? (
              <ChartLoading height={400} />
            ) : (
              <div className="text-center text-gray-500 dark:text-gray-400 py-8">
                <p>Select a skill to see its connections</p>
                <p className="text-sm mt-2">
                  The network graph visualization will show how skills relate to each other
                </p>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Full Skills Table */}
      <Card title="Complete Skills Breakdown">
        {demandLoading ? (
          <div className="space-y-2">
            {[...Array(10)].map((_, i) => (
              <div key={i} className="h-10 bg-gray-100 dark:bg-gray-700 rounded animate-pulse" />
            ))}
          </div>
        ) : skillDemand?.data?.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-gray-400">Rank</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-gray-400">Skill</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-gray-400">Category</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-gray-400">Jobs</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-gray-400">Demand %</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-gray-400"></th>
                </tr>
              </thead>
              <tbody>
                {skillDemand.data.map((skill, index) => (
                  <tr
                    key={index}
                    className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer"
                    onClick={() => { setSelectedSkill(skill.skill_name); setActiveTab('connections') }}
                    title={`Show ${skill.skill_name} connections`}
                  >
                    <td className="py-3 px-4 text-gray-500 dark:text-gray-500">{index + 1}</td>
                    <td className="py-3 px-4 font-medium text-gray-900 dark:text-gray-100">{skill.skill_name}</td>
                    <td className="py-3 px-4 text-gray-600 dark:text-gray-400">{skill.skill_category || '-'}</td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => { e.stopPropagation(); openJobs(skill.skill_name) }}
                        title={`View jobs mentioning ${skill.skill_name}`}
                        className="font-medium text-primary-600 dark:text-primary-400 hover:underline"
                      >
                        {formatNumber(skill.job_count)}
                      </button>
                    </td>
                    <td className="py-3 px-4 text-right text-gray-600 dark:text-gray-400">
                      {skill.demand_percentage ? `${skill.demand_percentage.toFixed(1)}%` : '-'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => { e.stopPropagation(); openJobs(skill.skill_name) }}
                        className="text-xs text-primary-600 dark:text-primary-400 hover:underline whitespace-nowrap"
                      >
                        View jobs →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState description="No data available" />
        )}
      </Card>
    </div>
  )
}
