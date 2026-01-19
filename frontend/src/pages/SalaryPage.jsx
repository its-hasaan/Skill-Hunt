import { useOutletContext } from 'react-router-dom'
import { useSalaryBySkill, useTopPayingSkills, usePremiumSkills } from '../hooks/useData'
import { Card, ChartLoading, EmptyState } from '../components/ui'
import { SalaryPremiumChart, SalaryComparisonChart } from '../components/charts/Charts'
import { formatNumber, formatCurrency, formatPercent } from '../utils/helpers'

export default function SalaryPage() {
  const { selectedRole, selectedCountry } = useOutletContext()

  const { data: salaryData, isLoading: salaryLoading } = useSalaryBySkill(
    selectedRole,
    selectedCountry || null,
    5
  )

  const { data: premiumSkills, isLoading: premiumLoading } = usePremiumSkills(
    selectedRole,
    selectedCountry || null,
    15
  )

  const { data: topPaying, isLoading: topPayingLoading } = useTopPayingSkills(
    selectedRole,
    selectedCountry || null,
    15
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Salary Analysis</h1>
        <p className="text-gray-600">
          {selectedRole ? `Salary insights for ${selectedRole}` : 'Select a role to see salary data'}
        </p>
      </div>

      {/* Main Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Salary Premium */}
        <Card title="💎 Skills with Highest Salary Premium">
          <p className="text-sm text-gray-500 mb-4">
            Skills that pay above the market average
          </p>
          {premiumLoading ? (
            <ChartLoading height={450} />
          ) : premiumSkills?.length > 0 ? (
            <SalaryPremiumChart data={premiumSkills} height={450} />
          ) : (
            <EmptyState description="No salary premium data available" />
          )}
        </Card>

        {/* Average Salary */}
        <Card title="📈 Highest Paying Skills">
          <p className="text-sm text-gray-500 mb-4">
            Skills with the highest average salaries
          </p>
          {topPayingLoading ? (
            <ChartLoading height={450} />
          ) : topPaying?.length > 0 ? (
            <SalaryComparisonChart data={topPaying} height={450} />
          ) : (
            <EmptyState description="No salary data available" />
          )}
        </Card>
      </div>

      {/* Salary Table */}
      <Card title="📊 Complete Salary Comparison">
        {salaryLoading ? (
          <div className="space-y-2">
            {[...Array(10)].map((_, i) => (
              <div key={i} className="h-12 bg-gray-100 rounded animate-pulse" />
            ))}
          </div>
        ) : salaryData?.data?.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Skill</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Category</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600">Jobs</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600">Avg Salary</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600">Market Avg</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600">Premium</th>
                </tr>
              </thead>
              <tbody>
                {salaryData.data.slice(0, 30).map((skill, index) => (
                  <tr key={index} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4 font-medium text-gray-900">{skill.skill_name}</td>
                    <td className="py-3 px-4 text-gray-600">{skill.skill_category || '-'}</td>
                    <td className="py-3 px-4 text-right text-gray-900">
                      {formatNumber(skill.jobs_with_skill)}
                    </td>
                    <td className="py-3 px-4 text-right text-gray-900">
                      {skill.avg_salary_with_skill 
                        ? formatCurrency(skill.avg_salary_with_skill) 
                        : '-'}
                    </td>
                    <td className="py-3 px-4 text-right text-gray-600">
                      {skill.market_avg_salary 
                        ? formatCurrency(skill.market_avg_salary) 
                        : '-'}
                    </td>
                    <td className={`py-3 px-4 text-right font-medium ${
                      skill.salary_premium_percentage >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {skill.salary_premium_percentage != null 
                        ? formatPercent(skill.salary_premium_percentage) 
                        : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState description="No salary data available for this selection" />
        )}
      </Card>

      {/* Insights */}
      {salaryData?.data?.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-green-50 rounded-xl p-4">
            <h4 className="font-medium text-green-800 mb-1">💰 Top Earner</h4>
            <p className="text-2xl font-bold text-green-900">
              {topPaying?.[0]?.skill_name || '-'}
            </p>
            <p className="text-sm text-green-600">
              {topPaying?.[0]?.avg_salary_with_skill 
                ? formatCurrency(topPaying[0].avg_salary_with_skill) + ' avg'
                : '-'}
            </p>
          </div>
          <div className="bg-purple-50 rounded-xl p-4">
            <h4 className="font-medium text-purple-800 mb-1">📈 Best Premium</h4>
            <p className="text-2xl font-bold text-purple-900">
              {premiumSkills?.[0]?.skill_name || '-'}
            </p>
            <p className="text-sm text-purple-600">
              {premiumSkills?.[0]?.salary_premium_percentage 
                ? formatPercent(premiumSkills[0].salary_premium_percentage) + ' above market'
                : '-'}
            </p>
          </div>
          <div className="bg-blue-50 rounded-xl p-4">
            <h4 className="font-medium text-blue-800 mb-1">📊 Skills Analyzed</h4>
            <p className="text-2xl font-bold text-blue-900">
              {salaryData.total_count}
            </p>
            <p className="text-sm text-blue-600">
              skills with salary data
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
