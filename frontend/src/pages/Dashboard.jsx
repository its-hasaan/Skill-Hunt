import { useOutletContext, useNavigate } from 'react-router-dom'
import {
  Briefcase, Code, Globe, Building2, TrendingUp
} from 'lucide-react'
import { useSummaryStats, useSkillDemand } from '../hooks/useData'
import { Card, StatCard, ChartLoading, EmptyState, ErrorState } from '../components/ui'
import { SkillBarChart, CategoryPieChart } from '../components/charts/Charts'
import { formatNumber } from '../utils/helpers'

export default function Dashboard() {
  const { selectedRole, selectedCountry } = useOutletContext()
  const navigate = useNavigate()

  const { data: stats, isLoading: statsLoading } = useSummaryStats()
  const {
    data: skillDemand,
    isLoading: skillsLoading,
    isError: skillsError,
    refetch: refetchSkills,
  } = useSkillDemand(
    selectedRole,
    selectedCountry || null,
    20
  )

  const openJobs = (skillName) => {
    if (!selectedRole || !skillName) return
    const params = new URLSearchParams({ skill: skillName, role: selectedRole })
    if (selectedCountry) params.set('country', selectedCountry)
    navigate(`/jobs?${params.toString()}`)
  }

  return (
    <div className="space-y-4">
      {/* Hero Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        <StatCard
          title="Total Jobs"
          value={statsLoading ? '...' : formatNumber(stats?.total_jobs || 0)}
          subtitle={statsLoading ? undefined : `${formatNumber(stats?.current_jobs || 0)} current (last 60d)`}
          icon={Briefcase}
          loading={statsLoading}
        />
        <StatCard
          title="Skills Tracked"
          value={statsLoading ? '...' : formatNumber(stats?.total_skills || 0)}
          icon={Code}
          loading={statsLoading}
        />
        <StatCard
          title="Countries"
          value={statsLoading ? '...' : formatNumber(stats?.total_countries || 0)}
          icon={Globe}
          loading={statsLoading}
        />
        <StatCard
          title="Job Roles"
          value={statsLoading ? '...' : formatNumber(stats?.total_roles || 0)}
          icon={TrendingUp}
          loading={statsLoading}
        />
        <StatCard
          title="Companies"
          value={statsLoading ? '...' : formatNumber(stats?.total_companies || 0)}
          subtitle={statsLoading ? undefined : `${formatNumber(stats?.current_companies || 0)} current (last 60d)`}
          icon={Building2}
          loading={statsLoading}
        />
      </div>

      {/* Main Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Top Skills */}
        <Card
          title={`Top Skills for ${selectedRole || 'All Roles'}`}
          className="lg:col-span-2"
        >
          {skillsLoading ? (
            <ChartLoading height={340} />
          ) : skillsError ? (
            <ErrorState
              message="Could not reach the API — this is a connection problem, not missing data."
              onRetry={refetchSkills}
            />
          ) : skillDemand?.data?.length > 0 ? (
            <SkillBarChart data={skillDemand.data} height={340} />
          ) : (
            <EmptyState description="No skill data available for this selection" />
          )}
        </Card>

        {/* Category Distribution */}
        <Card title="Skills by Category">
          {skillsLoading ? (
            <ChartLoading height={260} />
          ) : skillDemand?.data?.length > 0 ? (
            <CategoryPieChart data={skillDemand.data} height={260} />
          ) : (
            <EmptyState description="No category data available" />
          )}
        </Card>
      </div>

      {/* Skills Table */}
      <Card
        title="Skill Demand Breakdown"
        headerAction={<span className="text-xs text-gray-500 dark:text-gray-400">Click a skill to see the jobs →</span>}
      >
        {skillsLoading ? (
          <div className="space-y-1.5">
            {[...Array(10)].map((_, i) => (
              <div key={i} className="h-8 bg-gray-100 dark:bg-gray-700 rounded animate-pulse" />
            ))}
          </div>
        ) : skillDemand?.data?.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-white/[0.08]">
                  <th className="text-left py-2 px-3 text-[11px] font-medium uppercase tracking-wider text-gray-400 dark:text-gray-500">Skill</th>
                  <th className="text-left py-2 px-3 text-[11px] font-medium uppercase tracking-wider text-gray-400 dark:text-gray-500">Category</th>
                  <th className="text-right py-2 px-3 text-[11px] font-medium uppercase tracking-wider text-gray-400 dark:text-gray-500">Jobs</th>
                  <th className="text-right py-2 px-3 text-[11px] font-medium uppercase tracking-wider text-gray-400 dark:text-gray-500">Demand %</th>
                  <th
                    className="text-right py-2 px-3 text-[11px] font-medium uppercase tracking-wider text-gray-400 dark:text-gray-500 cursor-help"
                    title="Converted to USD using live exchange rates, so figures are comparable across countries"
                  >
                    Avg Salary
                  </th>
                </tr>
              </thead>
              <tbody>
                {skillDemand.data.slice(0, 20).map((skill, index) => (
                  <tr
                    key={index}
                    onClick={() => openJobs(skill.skill_name)}
                    title={`View jobs mentioning ${skill.skill_name}`}
                    className="border-b border-gray-100 dark:border-white/[0.05] hover:bg-gray-50 dark:hover:bg-white/[0.03] cursor-pointer transition-colors"
                  >
                    <td className="py-2 px-3 font-medium text-primary-600 dark:text-primary-400 hover:underline">{skill.skill_name}</td>
                    <td className="py-2 px-3 text-gray-600 dark:text-gray-400">{skill.skill_category || '-'}</td>
                    <td className="py-2 px-3 text-right font-medium text-gray-900 dark:text-white tabular-nums">{formatNumber(skill.job_count)}</td>
                    <td className="py-2 px-3 text-right text-gray-600 dark:text-gray-400 tabular-nums">
                      {skill.demand_percentage ? `${skill.demand_percentage.toFixed(1)}%` : '-'}
                    </td>
                    <td className="py-2 px-3 text-right text-gray-600 dark:text-gray-400 tabular-nums">
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
    </div>
  )
}
