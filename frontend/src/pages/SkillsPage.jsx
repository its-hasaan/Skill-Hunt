import { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { useSkillDemand, useSkillCooccurrence } from '../hooks/useData'
import { Card, ChartLoading, EmptyState, Tabs } from '../components/ui'
import { CategoryBarChart, CategoryPieChart } from '../components/charts/Charts'
import { formatNumber } from '../utils/helpers'

export default function SkillsPage() {
  const { selectedRole, selectedCountry } = useOutletContext()
  const [activeTab, setActiveTab] = useState('demand')
  const [selectedSkill, setSelectedSkill] = useState(null)

  const { data: skillDemand, isLoading: demandLoading } = useSkillDemand(
    selectedRole, 
    selectedCountry || null, 
    30
  )

  const { data: cooccurrence, isLoading: coocLoading } = useSkillCooccurrence(
    selectedRole,
    selectedSkill,
    5
  )

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
          <h1 className="text-2xl font-bold text-gray-900">Skills Analysis</h1>
          <p className="text-gray-600">
            {selectedRole ? `Skills for ${selectedRole}` : 'Select a role to see skills'}
          </p>
        </div>
        <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />
      </div>

      {activeTab === 'demand' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Chart */}
          <Card title="Top 15 Skills by Job Count" className="lg:col-span-2">
            {demandLoading ? (
              <ChartLoading height={500} />
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
                  <span className="text-gray-600">Total Skills:</span>
                  <span className="font-medium">{skillDemand.total_count}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Top Skill:</span>
                  <span className="font-medium">{skillDemand.data[0]?.skill_name}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Top Category:</span>
                  <span className="font-medium">{skillDemand.data[0]?.skill_category || '-'}</span>
                </div>
              </div>
            )}
          </Card>
        </div>
      )}

      {activeTab === 'connections' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Skill Selector */}
          <Card title="Find Skill Connections">
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
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
                  <h4 className="font-medium text-gray-900 mb-3">
                    Skills that pair with {selectedSkill}:
                  </h4>
                  {cooccurrence.slice(0, 15).map((pair, index) => {
                    const otherSkill = pair.skill_name_1 === selectedSkill 
                      ? pair.skill_name_2 
                      : pair.skill_name_1
                    return (
                      <div 
                        key={index}
                        className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                      >
                        <span className="font-medium text-gray-900">{otherSkill}</span>
                        <div className="text-right text-sm">
                          <div className="text-gray-600">
                            {formatNumber(pair.cooccurrence_count)} jobs
                          </div>
                          <div className="text-gray-400">
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
              <div className="text-center text-gray-500 py-8">
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
              <div key={i} className="h-10 bg-gray-100 rounded animate-pulse" />
            ))}
          </div>
        ) : skillDemand?.data?.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Rank</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Skill</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Category</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600">Jobs</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600">Demand %</th>
                </tr>
              </thead>
              <tbody>
                {skillDemand.data.map((skill, index) => (
                  <tr 
                    key={index} 
                    className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                    onClick={() => setSelectedSkill(skill.skill_name)}
                  >
                    <td className="py-3 px-4 text-gray-500">{index + 1}</td>
                    <td className="py-3 px-4 font-medium text-gray-900">{skill.skill_name}</td>
                    <td className="py-3 px-4 text-gray-600">{skill.skill_category || '-'}</td>
                    <td className="py-3 px-4 text-right text-gray-900">{formatNumber(skill.job_count)}</td>
                    <td className="py-3 px-4 text-right text-gray-600">
                      {skill.demand_percentage ? `${skill.demand_percentage.toFixed(1)}%` : '-'}
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
