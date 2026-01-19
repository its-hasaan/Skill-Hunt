/**
 * Reusable chart components using Recharts
 */
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  PieChart, Pie, Cell, ResponsiveContainer, LineChart, Line,
  ScatterChart, Scatter, ZAxis
} from 'recharts'
import { CHART_COLORS, formatNumber, formatCurrency, formatPercent } from '../../utils/helpers'

/**
 * Horizontal bar chart for skill rankings
 */
export function SkillBarChart({ data, dataKey = 'job_count', nameKey = 'skill_name', height = 400 }) {
  // Sort by value and take top items
  const sortedData = [...data]
    .sort((a, b) => b[dataKey] - a[dataKey])
    .slice(0, 15)
    .reverse() // Reverse for horizontal bar chart (highest on top)

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={sortedData} layout="vertical" margin={{ top: 5, right: 30, left: 100, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis type="number" tickFormatter={formatNumber} />
        <YAxis 
          dataKey={nameKey} 
          type="category" 
          tick={{ fontSize: 12 }}
          width={90}
        />
        <Tooltip 
          formatter={(value) => formatNumber(value)}
          contentStyle={{ 
            backgroundColor: 'white', 
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'
          }}
        />
        <Bar 
          dataKey={dataKey} 
          fill="#3b82f6" 
          radius={[0, 4, 4, 0]}
        />
      </BarChart>
    </ResponsiveContainer>
  )
}

/**
 * Colorful bar chart with category colors
 */
export function CategoryBarChart({ 
  data, 
  dataKey = 'job_count', 
  nameKey = 'skill_name',
  categoryKey = 'skill_category',
  height = 400 
}) {
  const sortedData = [...data]
    .sort((a, b) => b[dataKey] - a[dataKey])
    .slice(0, 15)
    .reverse()

  // Get unique categories for coloring
  const categories = [...new Set(data.map(d => d[categoryKey]))]
  const categoryColorMap = {}
  categories.forEach((cat, i) => {
    categoryColorMap[cat] = CHART_COLORS[i % CHART_COLORS.length]
  })

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={sortedData} layout="vertical" margin={{ top: 5, right: 30, left: 100, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis type="number" tickFormatter={formatNumber} />
        <YAxis 
          dataKey={nameKey} 
          type="category" 
          tick={{ fontSize: 12 }}
          width={90}
        />
        <Tooltip 
          formatter={(value, name, props) => [formatNumber(value), props.payload[categoryKey]]}
          contentStyle={{ 
            backgroundColor: 'white', 
            border: '1px solid #e5e7eb',
            borderRadius: '8px'
          }}
        />
        <Bar dataKey={dataKey} radius={[0, 4, 4, 0]}>
          {sortedData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={categoryColorMap[entry[categoryKey]] || '#6b7280'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/**
 * Pie chart for category distribution
 */
export function CategoryPieChart({ data, height = 300 }) {
  // Aggregate by category
  const categoryData = data.reduce((acc, item) => {
    const cat = item.skill_category || 'Other'
    acc[cat] = (acc[cat] || 0) + (item.job_count || 1)
    return acc
  }, {})

  const pieData = Object.entries(categoryData).map(([name, value]) => ({ name, value }))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={pieData}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={100}
          paddingAngle={2}
          dataKey="value"
          label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
          labelLine={{ stroke: '#94a3b8', strokeWidth: 1 }}
        >
          {pieData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip 
          formatter={(value) => formatNumber(value)}
          contentStyle={{ 
            backgroundColor: 'white', 
            border: '1px solid #e5e7eb',
            borderRadius: '8px'
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}

/**
 * Salary premium bar chart
 */
export function SalaryPremiumChart({ data, height = 400 }) {
  const sortedData = [...data]
    .filter(d => d.salary_premium_percentage != null)
    .sort((a, b) => b.salary_premium_percentage - a.salary_premium_percentage)
    .slice(0, 15)
    .reverse()

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={sortedData} layout="vertical" margin={{ top: 5, right: 30, left: 100, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis 
          type="number" 
          tickFormatter={(v) => `${v > 0 ? '+' : ''}${v.toFixed(0)}%`}
        />
        <YAxis 
          dataKey="skill_name" 
          type="category" 
          tick={{ fontSize: 12 }}
          width={90}
        />
        <Tooltip 
          formatter={(value) => formatPercent(value)}
          contentStyle={{ 
            backgroundColor: 'white', 
            border: '1px solid #e5e7eb',
            borderRadius: '8px'
          }}
        />
        <Bar dataKey="salary_premium_percentage" radius={[0, 4, 4, 0]}>
          {sortedData.map((entry, index) => (
            <Cell 
              key={`cell-${index}`} 
              fill={entry.salary_premium_percentage >= 0 ? '#10b981' : '#ef4444'} 
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/**
 * Salary comparison bar chart
 */
export function SalaryComparisonChart({ data, height = 400 }) {
  const sortedData = [...data]
    .filter(d => d.avg_salary_with_skill != null)
    .sort((a, b) => b.avg_salary_with_skill - a.avg_salary_with_skill)
    .slice(0, 15)
    .reverse()

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={sortedData} layout="vertical" margin={{ top: 5, right: 30, left: 100, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis 
          type="number" 
          tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
        />
        <YAxis 
          dataKey="skill_name" 
          type="category" 
          tick={{ fontSize: 12 }}
          width={90}
        />
        <Tooltip 
          formatter={(value) => formatCurrency(value)}
          contentStyle={{ 
            backgroundColor: 'white', 
            border: '1px solid #e5e7eb',
            borderRadius: '8px'
          }}
        />
        <Bar 
          dataKey="avg_salary_with_skill" 
          fill="#6366f1" 
          radius={[0, 4, 4, 0]}
        />
      </BarChart>
    </ResponsiveContainer>
  )
}

/**
 * Company job count chart
 */
export function CompanyBarChart({ data, height = 500 }) {
  const sortedData = [...data]
    .sort((a, b) => b.job_count - a.job_count)
    .slice(0, 20)
    .reverse()

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={sortedData} layout="vertical" margin={{ top: 5, right: 30, left: 120, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis type="number" tickFormatter={formatNumber} />
        <YAxis 
          dataKey="company_name" 
          type="category" 
          tick={{ fontSize: 11 }}
          width={110}
        />
        <Tooltip 
          formatter={(value) => formatNumber(value)}
          contentStyle={{ 
            backgroundColor: 'white', 
            border: '1px solid #e5e7eb',
            borderRadius: '8px'
          }}
        />
        <Bar 
          dataKey="job_count" 
          fill="#0ea5e9" 
          radius={[0, 4, 4, 0]}
        />
      </BarChart>
    </ResponsiveContainer>
  )
}

/**
 * Contract type pie chart
 */
export function ContractTypePieChart({ data, height = 250 }) {
  const pieData = [
    { name: 'Full Time', value: data.full_time || 0, color: '#10b981' },
    { name: 'Part Time', value: data.part_time || 0, color: '#f59e0b' },
    { name: 'Contract', value: data.contract || 0, color: '#6366f1' },
  ].filter(d => d.value > 0)

  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={pieData}
          cx="50%"
          cy="50%"
          innerRadius={40}
          outerRadius={80}
          paddingAngle={3}
          dataKey="value"
          label={({ name, percent }) => `${name} (${(percent * 100).toFixed(0)}%)`}
        >
          {pieData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip formatter={(value) => formatNumber(value)} />
      </PieChart>
    </ResponsiveContainer>
  )
}

/**
 * Country comparison bar chart
 */
export function CountryComparisonChart({ data, valueKey = 'demand_percentage', height = 400 }) {
  const sortedData = [...data]
    .sort((a, b) => b[valueKey] - a[valueKey])
    .map(d => ({
      ...d,
      display_name: d.country_name || d.country_code?.toUpperCase()
    }))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={sortedData} layout="vertical" margin={{ top: 5, right: 30, left: 100, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis 
          type="number" 
          tickFormatter={(v) => valueKey.includes('percentage') ? `${v.toFixed(1)}%` : formatNumber(v)}
        />
        <YAxis 
          dataKey="display_name" 
          type="category" 
          tick={{ fontSize: 12 }}
          width={90}
        />
        <Tooltip 
          formatter={(value) => valueKey.includes('percentage') ? `${value.toFixed(2)}%` : formatNumber(value)}
          contentStyle={{ 
            backgroundColor: 'white', 
            border: '1px solid #e5e7eb',
            borderRadius: '8px'
          }}
        />
        <Bar 
          dataKey={valueKey} 
          fill="#8b5cf6" 
          radius={[0, 4, 4, 0]}
        />
      </BarChart>
    </ResponsiveContainer>
  )
}
