import { useOutletContext } from 'react-router-dom'
import { 
  Briefcase, Code, Globe, Building2, TrendingUp 
} from 'lucide-react'
import { useSummaryStats, useSkillDemand } from '../hooks/useData'
import { Card, StatCard, ChartLoading, EmptyState } from '../components/ui'
import { SkillBarChart, CategoryPieChart } from '../components/charts/Charts'
import { formatNumber } from '../utils/helpers'

export default function Dashboard() {
  const { selectedRole, selectedCountry } = useOutletContext()
  
  const { data: stats, isLoading: statsLoading } = useSummaryStats()
  const { data: skillDemand, isLoading: skillsLoading } = useSkillDemand(
    selectedRole, 
    selectedCountry || null, 
    20
  )

  return (
    <div className="space-y-6">
      {/* Hero Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <StatCard
          title="Total Jobs"
          value={statsLoading ? '...' : formatNumber(stats?.total_jobs || 0)}
          icon={Briefcase}
          color="primary"
          loading={statsLoading}
        />
        <StatCard
          title="Skills Tracked"
          value={statsLoading ? '...' : formatNumber(stats?.total_skills || 0)}
          icon={Code}
          color="accent"
          loading={statsLoading}
        />
        <StatCard
          title="Countries"
          value={statsLoading ? '...' : formatNumber(stats?.total_countries || 0)}
          icon={Globe}
          color="green"
          loading={statsLoading}
        />
        <StatCard
          title="Job Roles"
          value={statsLoading ? '...' : formatNumber(stats?.total_roles || 0)}
          icon={TrendingUp}
          color="yellow"
          loading={statsLoading}
        />
        <StatCard
          title="Companies"
          value={statsLoading ? '...' : formatNumber(stats?.total_companies || 0)}
          icon={Building2}
          color="red"
          loading={statsLoading}
        />
      </div>

      {/* Main Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top Skills */}
        <Card 
          title={`Top Skills for ${selectedRole || 'All Roles'}`}
          className="lg:col-span-2"
        >
          {skillsLoading ? (
            <ChartLoading height={400} />
          ) : skillDemand?.data?.length > 0 ? (
            <SkillBarChart data={skillDemand.data} height={400} />
          ) : (
            <EmptyState description="No skill data available for this selection" />
          )}
        </Card>

        {/* Category Distribution */}
        <Card title="Skills by Category">
          {skillsLoading ? (
            <ChartLoading height={300} />
          ) : skillDemand?.data?.length > 0 ? (
            <CategoryPieChart data={skillDemand.data} height={300} />
          ) : (
            <EmptyState description="No category data available" />
          )}
        </Card>
      </div>

      {/* Skills Table */}
      <Card title="Skill Demand Breakdown">
        {skillsLoading ? (
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
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Skill</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Category</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600">Jobs</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600">Demand %</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600">Avg Salary</th>
                </tr>
              </thead>
              <tbody>
                {skillDemand.data.slice(0, 20).map((skill, index) => (
                  <tr key={index} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4 font-medium text-gray-900">{skill.skill_name}</td>
                    <td className="py-3 px-4 text-gray-600">{skill.skill_category || '-'}</td>
                    <td className="py-3 px-4 text-right text-gray-900">{formatNumber(skill.job_count)}</td>
                    <td className="py-3 px-4 text-right text-gray-600">
                      {skill.demand_percentage ? `${skill.demand_percentage.toFixed(1)}%` : '-'}
                    </td>
                    <td className="py-3 px-4 text-right text-gray-600">
                      {skill.avg_salary_midpoint ? `$${formatNumber(Math.round(skill.avg_salary_midpoint))}` : '-'}
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

      {/* Footer */}
      <div className="text-center text-sm text-gray-500 py-4">
        <p>🎯 Skill Hunt | Data refreshed weekly from job postings</p>
        <p className="mt-1">Built with React + FastAPI • Data Engineering Portfolio Project</p>
      </div>
    </div>
  )
}
