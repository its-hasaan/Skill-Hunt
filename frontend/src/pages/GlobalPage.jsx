import { useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import { useSkillByCountry, useFilterOptions, useSkillDemand } from '../hooks/useData'
import { Card, ChartLoading, EmptyState, ErrorState } from '../components/ui'
import { CountryComparisonChart } from '../components/charts/Charts'
import { getCountryDisplay, formatNumber } from '../utils/helpers'

// Fallback while the demand query loads (or no role is selected yet).
const FALLBACK_SKILLS = [
  'Python', 'SQL', 'JavaScript', 'AWS', 'Docker', 'Kubernetes',
  'React', 'TypeScript', 'Java', 'Git', 'Linux', 'PostgreSQL',
  'Machine Learning', 'TensorFlow', 'Spark', 'Tableau'
]

export default function GlobalPage() {
  const { selectedRole } = useOutletContext()
  const [selectedSkill, setSelectedSkill] = useState('')

  const { data: filters } = useFilterOptions()
  const { data: countryData, isLoading: countryLoading, isError: countryError } = useSkillByCountry(
    selectedSkill,
    selectedRole
  )

  // Skill options come from the LIVE top-demand list for the selected role,
  // so the dropdown always matches what actually exists in the data —
  // the old hardcoded list silently broke whenever taxonomy naming changed.
  const { data: demandData } = useSkillDemand(selectedRole, null, 30)
  const commonSkills = demandData?.data?.length
    ? demandData.data.map((s) => s.skill_name)
    : FALLBACK_SKILLS

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">🌍 Global Skill Comparison</h1>
        <p className="text-gray-600 dark:text-gray-400">
          Compare skill demand across different countries
        </p>
      </div>

      {/* Skill Selector */}
      <Card>
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
          <label className="font-medium text-gray-700 dark:text-gray-300">
            Select a skill to compare:
          </label>
          <select
            value={selectedSkill}
            onChange={(e) => setSelectedSkill(e.target.value)}
            className="select-input max-w-xs"
          >
            <option value="">Choose a skill...</option>
            {commonSkills.map(skill => (
              <option key={skill} value={skill}>{skill}</option>
            ))}
          </select>
          {selectedSkill && (
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Comparing for: <strong>{selectedRole || 'All Roles'}</strong>
            </span>
          )}
        </div>
      </Card>

      {!selectedSkill ? (
        <Card>
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-gray-100 dark:bg-gray-700 rounded-full flex items-center justify-center mx-auto mb-4">
              <span className="text-3xl">🌍</span>
            </div>
            <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
              Select a Skill to Compare
            </h3>
            <p className="text-gray-500 dark:text-gray-400 max-w-md mx-auto">
              Choose a skill from the dropdown above to see how its demand varies across different countries.
            </p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Demand Percentage Chart */}
          <Card title={`${selectedSkill} Demand by Country (%)`}>
            {countryLoading ? (
              <ChartLoading height={400} />
            ) : countryError ? (
              <ErrorState message="Could not load country data — the API may be unavailable." />
            ) : countryData?.data?.length > 0 ? (
              <CountryComparisonChart 
                data={countryData.data} 
                valueKey="demand_percentage"
                height={400} 
              />
            ) : (
              <EmptyState description="No data available for this skill/role combination" />
            )}
          </Card>

          {/* Job Count Chart */}
          <Card title={`${selectedSkill} Job Count by Country`}>
            {countryLoading ? (
              <ChartLoading height={400} />
            ) : countryData?.data?.length > 0 ? (
              <CountryComparisonChart 
                data={countryData.data} 
                valueKey="job_count"
                height={400} 
              />
            ) : (
              <EmptyState description="No data available" />
            )}
          </Card>
        </div>
      )}

      {/* Country Table */}
      {selectedSkill && countryData?.data?.length > 0 && (
        <Card title="📊 Country Comparison Table">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-gray-400">Country</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-gray-400">Jobs with Skill</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-gray-400">Demand %</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-gray-400">Rank</th>
                </tr>
              </thead>
              <tbody>
                {/* Copy before sorting — .sort() in place mutates React Query's cached array */}
                {[...countryData.data]
                  .sort((a, b) => b.demand_percentage - a.demand_percentage)
                  .map((row, index) => (
                    <tr key={index} className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                      <td className="py-3 px-4 font-medium text-gray-900 dark:text-gray-100">
                        {getCountryDisplay(row.country_code)}
                      </td>
                      <td className="py-3 px-4 text-right text-gray-900 dark:text-gray-100">
                        {formatNumber(row.job_count)}
                      </td>
                      <td className="py-3 px-4 text-right text-gray-600 dark:text-gray-400">
                        {row.demand_percentage?.toFixed(2)}%
                      </td>
                      <td className="py-3 px-4 text-right text-gray-500 dark:text-gray-500">
                        {row.rank_by_country || index + 1}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Available Countries */}
      {filters?.countries && (
        <Card title="🗺️ Countries in Our Dataset">
          <div className="flex flex-wrap gap-2">
            {filters.countries.map((country) => (
              <span 
                key={country.country_code}
                className="px-3 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-full text-sm"
              >
                {getCountryDisplay(country.country_code)}
              </span>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
