import { useOutletContext } from 'react-router-dom'
import { useCompanyLeaderboard, useContractTypes } from '../hooks/useData'
import { Card, ChartLoading, EmptyState, ErrorState } from '../components/ui'
import { CompanyBarChart, ContractTypePieChart } from '../components/charts/Charts'
import { formatNumber, formatCurrency } from '../utils/helpers'

export default function CompaniesPage() {
  const { selectedRole, selectedCountry } = useOutletContext()

  const { data: companies, isLoading: companiesLoading, isError: companiesError, refetch: refetchCompanies } = useCompanyLeaderboard(
    selectedRole,
    selectedCountry || null,
    50
  )

  const { data: contractTypes, isLoading: contractLoading } = useContractTypes(
    selectedRole,
    selectedCountry || null
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Top Hiring Companies</h1>
        <p className="text-gray-600 dark:text-gray-400">
          {selectedRole ? `Companies hiring for ${selectedRole}` : 'Select a role to see companies'}
        </p>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Companies Chart */}
        <Card title="Top 20 Hiring Companies" className="lg:col-span-2">
          {companiesLoading ? (
            <ChartLoading height={550} />
          ) : companiesError ? (
            <ErrorState message="Could not reach the API — this is a connection problem, not missing data." onRetry={refetchCompanies} />
          ) : companies?.data?.length > 0 ? (
            <CompanyBarChart data={companies.data} height={550} />
          ) : (
            <EmptyState description="No company data available" />
          )}
        </Card>

        {/* Contract Types */}
        <div className="space-y-6">
          <Card title="Contract Types">
            {contractLoading ? (
              <ChartLoading height={220} />
            ) : contractTypes ? (
              <ContractTypePieChart data={contractTypes} height={220} />
            ) : (
              <EmptyState description="No contract data" />
            )}

            {/* Contract Stats */}
            {contractTypes && (
              <div className="mt-4 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">Full-time:</span>
                  <span className="font-medium text-green-600 dark:text-green-400">
                    {formatNumber(contractTypes.full_time || 0)}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">Part-time:</span>
                  <span className="font-medium text-yellow-600 dark:text-yellow-400">
                    {formatNumber(contractTypes.part_time || 0)}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">Contract:</span>
                  <span className="font-medium text-purple-600 dark:text-purple-400">
                    {formatNumber(contractTypes.contract || 0)}
                  </span>
                </div>
              </div>
            )}
          </Card>

          {/* Quick Stats */}
          {companies?.data?.length > 0 && (
            <Card title="Quick Stats">
              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">Total Companies:</span>
                  <span className="font-medium dark:text-gray-200">{companies.total_count}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">Top Employer:</span>
                  <span className="font-medium dark:text-gray-200">{companies.data[0]?.company_name}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">Top Jobs:</span>
                  <span className="font-medium dark:text-gray-200">{formatNumber(companies.data[0]?.job_count)}</span>
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* Companies Table */}
      <Card title="📋 Company Details">
        {companiesLoading ? (
          <div className="space-y-2">
            {[...Array(10)].map((_, i) => (
              <div key={i} className="h-12 bg-gray-100 dark:bg-gray-700 rounded animate-pulse" />
            ))}
          </div>
        ) : companies?.data?.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-gray-400">Rank</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600 dark:text-gray-400">Company</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-gray-400">Total Jobs</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600 dark:text-gray-400">Full-Time</th>
                  <th
                    className="text-right py-3 px-4 font-medium text-gray-600 dark:text-gray-400 cursor-help"
                    title="Converted to USD using live exchange rates, so figures are comparable across countries"
                  >
                    Avg Salary
                  </th>
                </tr>
              </thead>
              <tbody>
                {companies.data.slice(0, 30).map((company, index) => (
                  <tr key={index} className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <td className="py-3 px-4 text-gray-500 dark:text-gray-500">{index + 1}</td>
                    <td className="py-3 px-4 font-medium text-gray-900 dark:text-gray-100">{company.company_name}</td>
                    <td className="py-3 px-4 text-right text-gray-900 dark:text-gray-100">
                      {formatNumber(company.job_count)}
                    </td>
                    <td className="py-3 px-4 text-right text-gray-600 dark:text-gray-400">
                      {formatNumber(company.full_time_count || 0)}
                    </td>
                    <td className="py-3 px-4 text-right text-gray-600 dark:text-gray-400">
                      {company.avg_salary_midpoint 
                        ? formatCurrency(company.avg_salary_midpoint) 
                        : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState description="No company data available" />
        )}
      </Card>
    </div>
  )
}
