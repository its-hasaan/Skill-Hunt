/**
 * Reusable chart components using Recharts.
 *
 * Visual rules applied throughout (see dataviz conventions):
 * - Solid hairline gridlines (never dashed), recessive axes.
 * - Thin bars with a rounded data-end, generous padding.
 * - Colors from the CVD-validated series palette in utils/helpers; category
 *   colors are FIXED per category (never reassigned when data is filtered).
 * - One shared tooltip with a color chip per row and formatted values.
 * - Legends whenever more than one hue carries meaning.
 */
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  PieChart, Pie, Cell, ResponsiveContainer, LineChart, Line, ReferenceLine,
} from 'recharts'
import {
  formatNumber, formatCurrency, formatPercent,
  getSeriesColor, getCategoryColor, SERIES_NEUTRAL,
} from '../../utils/helpers'
import { useTheme } from '../../context/ThemeContext'

/**
 * Theme-aware chart tokens: series palette, hairline grid, muted ticks.
 */
export function useChartColors() {
  const { isDark } = useTheme()
  return {
    isDark,
    series: (i) => getSeriesColor(i, isDark),
    gridColor: isDark ? '#30363d' : '#e5e7eb',        // hairline, one shade off surface
    axisColor: isDark ? '#4b5563' : '#d1d5db',
    tickStyle: { fill: isDark ? '#9ca3af' : '#6b7280', fontSize: 12 },
    positive: isDark ? '#3987e5' : '#2a78d6',          // diverging pair: blue…
    negative: isDark ? '#e66767' : '#e34948',          // …red
  }
}

/** Truncate long category-axis labels; the tooltip carries the full name. */
const truncate = (max) => (value) =>
  value && value.length > max ? `${value.slice(0, max - 1)}…` : value

/**
 * Shared tooltip: title + one row per series with a color chip and a
 * formatted value. `rows` receives the Recharts payload and returns
 * [{ label, value, color }] — charts customize via formatter props.
 */
function ChartTooltip({ active, payload, label, isDark, title, rows }) {
  if (!active || !payload?.length) return null
  const items = rows
    ? rows(payload, label)
    : payload.map((p) => ({ label: p.name, value: formatNumber(p.value), color: p.color || p.fill }))
  return (
    <div
      className="rounded-lg border shadow-lg px-3 py-2 text-xs"
      style={{
        backgroundColor: isDark ? '#161b22' : '#ffffff',
        borderColor: isDark ? '#30363d' : '#e5e7eb',
        color: isDark ? '#f3f4f6' : '#111827',
      }}
    >
      <div className="font-semibold mb-1">{title ? title(payload, label) : label}</div>
      {items.map((item, i) => (
        <div key={i} className="flex items-center gap-2 py-0.5">
          {item.color && (
            <span className="inline-block h-2.5 w-2.5 rounded-sm flex-shrink-0" style={{ backgroundColor: item.color }} />
          )}
          <span className="text-gray-500 dark:text-gray-400">{item.label}</span>
          <span className="ml-auto font-medium tabular-nums pl-3">{item.value}</span>
        </div>
      ))}
    </div>
  )
}

/**
 * Horizontal bar chart for skill rankings — single measure, one hue.
 */
export function SkillBarChart({ data, dataKey = 'job_count', nameKey = 'skill_name', height = 400 }) {
  const c = useChartColors()
  const sortedData = [...data]
    .sort((a, b) => b[dataKey] - a[dataKey])
    .slice(0, 15)
    .reverse()

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={sortedData} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
        <CartesianGrid horizontal={false} stroke={c.gridColor} />
        <XAxis type="number" tickFormatter={formatNumber} tick={c.tickStyle} axisLine={{ stroke: c.axisColor }} tickLine={false} />
        <YAxis
          dataKey={nameKey}
          type="category"
          tick={c.tickStyle}
          tickFormatter={truncate(16)}
          width={112}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          cursor={{ fill: c.gridColor, opacity: 0.35 }}
          content={<ChartTooltip isDark={c.isDark} rows={(payload) => [{
            label: 'Jobs', value: formatNumber(payload[0].value), color: c.series(0),
          }]} />}
        />
        <Bar dataKey={dataKey} fill={c.series(0)} radius={[0, 4, 4, 0]} barSize={16} />
      </BarChart>
    </ResponsiveContainer>
  )
}

/**
 * Skill ranking bar chart colored by category — categories keep a FIXED
 * color everywhere in the app, with a legend for the categories present.
 */
export function CategoryBarChart({
  data,
  dataKey = 'job_count',
  nameKey = 'skill_name',
  categoryKey = 'skill_category',
  height = 400,
}) {
  const c = useChartColors()
  const sortedData = [...data]
    .sort((a, b) => b[dataKey] - a[dataKey])
    .slice(0, 15)
    .reverse()

  // Legend: categories present in the visible bars, in display order.
  const presentCategories = [...new Set(sortedData.map(d => d[categoryKey] || 'Other'))].reverse()

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={sortedData} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
          <CartesianGrid horizontal={false} stroke={c.gridColor} />
          <XAxis type="number" tickFormatter={formatNumber} tick={c.tickStyle} axisLine={{ stroke: c.axisColor }} tickLine={false} />
          <YAxis
            dataKey={nameKey}
            type="category"
            tick={c.tickStyle}
            tickFormatter={truncate(16)}
            width={112}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: c.gridColor, opacity: 0.35 }}
            content={<ChartTooltip isDark={c.isDark} rows={(payload) => {
              const row = payload[0]?.payload || {}
              return [
                { label: row[categoryKey] || 'Other', value: '', color: getCategoryColor(row[categoryKey], c.isDark) },
                { label: 'Jobs', value: formatNumber(payload[0].value) },
                ...(row.demand_percentage != null
                  ? [{ label: 'Demand', value: `${Number(row.demand_percentage).toFixed(1)}%` }]
                  : []),
              ]
            }} />}
          />
          <Bar dataKey={dataKey} radius={[0, 4, 4, 0]} barSize={16}>
            {sortedData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={getCategoryColor(entry[categoryKey], c.isDark)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      {/* Category legend — fixed colors, so it doubles as a key across pages */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 justify-center mt-2">
        {presentCategories.map((cat) => (
          <span key={cat} className="inline-flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: getCategoryColor(cat, c.isDark) }} />
            {cat}
          </span>
        ))}
      </div>
    </div>
  )
}

/**
 * Category share donut — folds the tail into "Other" (max 6 slices + Other),
 * center shows the total, identity lives in the legend (no per-slice labels).
 */
export function CategoryPieChart({ data, height = 300 }) {
  const c = useChartColors()
  const categoryData = data.reduce((acc, item) => {
    const cat = item.skill_category || 'Other'
    acc[cat] = (acc[cat] || 0) + (item.job_count || 1)
    return acc
  }, {})

  const sorted = Object.entries(categoryData).sort((a, b) => b[1] - a[1])
  const top = sorted.slice(0, 6)
  const otherTotal = sorted.slice(6).reduce((sum, [, v]) => sum + v, 0)
  const pieData = [
    ...top.map(([name, value]) => ({ name, value })),
    ...(otherTotal > 0 ? [{ name: 'Other', value: otherTotal }] : []),
  ]
  const total = pieData.reduce((sum, d) => sum + d.value, 0)

  return (
    <div>
      <div className="relative">
        <ResponsiveContainer width="100%" height={height}>
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              innerRadius={62}
              outerRadius={95}
              paddingAngle={2}
              dataKey="value"
            >
              {pieData.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={entry.name === 'Other' ? SERIES_NEUTRAL : getCategoryColor(entry.name, c.isDark)}
                  stroke="none"
                />
              ))}
            </Pie>
            <Tooltip
              content={<ChartTooltip isDark={c.isDark}
                title={(payload) => payload[0]?.name}
                rows={(payload) => [
                  { label: 'Jobs', value: formatNumber(payload[0]?.value) },
                  { label: 'Share', value: `${((payload[0]?.value / total) * 100).toFixed(1)}%` },
                ]} />}
            />
          </PieChart>
        </ResponsiveContainer>
        {/* Center total */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-xl font-bold text-gray-900 dark:text-gray-100">{formatNumber(total)}</span>
          <span className="text-xs text-gray-500 dark:text-gray-400">skill mentions</span>
        </div>
      </div>
      {/* Legend with shares */}
      <div className="mt-2 space-y-1">
        {pieData.map((entry) => (
          <div key={entry.name} className="flex items-center gap-2 text-xs">
            <span
              className="h-2.5 w-2.5 rounded-sm flex-shrink-0"
              style={{ backgroundColor: entry.name === 'Other' ? SERIES_NEUTRAL : getCategoryColor(entry.name, c.isDark) }}
            />
            <span className="text-gray-600 dark:text-gray-300 truncate">{entry.name}</span>
            <span className="ml-auto text-gray-400 dark:text-gray-500 tabular-nums">
              {((entry.value / total) * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * Salary premium — a diverging measure (above/below market), so it uses the
 * diverging pair (blue = above, red = below) with a zero reference line.
 */
export function SalaryPremiumChart({ data, height = 400 }) {
  const c = useChartColors()
  const sortedData = [...data]
    .filter(d => d.salary_premium_percentage != null)
    .sort((a, b) => b.salary_premium_percentage - a.salary_premium_percentage)
    .slice(0, 15)
    .reverse()

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={sortedData} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
        <CartesianGrid horizontal={false} stroke={c.gridColor} />
        <XAxis
          type="number"
          tickFormatter={(v) => `${v > 0 ? '+' : ''}${v.toFixed(0)}%`}
          tick={c.tickStyle}
          axisLine={{ stroke: c.axisColor }}
          tickLine={false}
        />
        <YAxis
          dataKey="skill_name"
          type="category"
          tick={c.tickStyle}
          tickFormatter={truncate(16)}
          width={112}
          axisLine={false}
          tickLine={false}
        />
        <ReferenceLine x={0} stroke={c.axisColor} />
        <Tooltip
          cursor={{ fill: c.gridColor, opacity: 0.35 }}
          content={<ChartTooltip isDark={c.isDark} rows={(payload) => {
            const v = payload[0].value
            return [{
              label: v >= 0 ? 'Above market' : 'Below market',
              value: formatPercent(v),
              color: v >= 0 ? c.positive : c.negative,
            }]
          }} />}
        />
        <Bar dataKey="salary_premium_percentage" radius={[0, 4, 4, 0]} barSize={16}>
          {sortedData.map((entry, index) => (
            <Cell
              key={`cell-${index}`}
              fill={entry.salary_premium_percentage >= 0 ? c.positive : c.negative}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

/**
 * Salary by skill — one measure, one hue, with a "market average" reference
 * line when the data carries it (turns raw bars into an instant comparison).
 */
export function SalaryComparisonChart({ data, height = 400 }) {
  const c = useChartColors()
  const sortedData = [...data]
    .filter(d => d.avg_salary_with_skill != null)
    .sort((a, b) => b.avg_salary_with_skill - a.avg_salary_with_skill)
    .slice(0, 15)
    .reverse()

  const marketAvg = sortedData.find(d => d.market_avg_salary != null)?.market_avg_salary

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={sortedData} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
        <CartesianGrid horizontal={false} stroke={c.gridColor} />
        <XAxis
          type="number"
          tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
          tick={c.tickStyle}
          axisLine={{ stroke: c.axisColor }}
          tickLine={false}
        />
        <YAxis
          dataKey="skill_name"
          type="category"
          tick={c.tickStyle}
          tickFormatter={truncate(16)}
          width={112}
          axisLine={false}
          tickLine={false}
        />
        {marketAvg != null && (
          <ReferenceLine
            x={marketAvg}
            stroke={c.tickStyle.fill}
            strokeWidth={1}
            label={{ value: 'Market avg', position: 'insideTopRight', fill: c.tickStyle.fill, fontSize: 11 }}
          />
        )}
        <Tooltip
          cursor={{ fill: c.gridColor, opacity: 0.35 }}
          content={<ChartTooltip isDark={c.isDark} rows={(payload) => {
            const row = payload[0]?.payload || {}
            return [
              { label: 'Avg salary', value: formatCurrency(payload[0].value), color: c.series(0) },
              ...(row.market_avg_salary != null
                ? [{ label: 'Market avg', value: formatCurrency(row.market_avg_salary) }]
                : []),
              ...(row.jobs_with_skill != null
                ? [{ label: 'Based on', value: `${formatNumber(row.jobs_with_skill)} jobs` }]
                : []),
            ]
          }} />}
        />
        <Bar dataKey="avg_salary_with_skill" fill={c.series(0)} radius={[0, 4, 4, 0]} barSize={16} />
      </BarChart>
    </ResponsiveContainer>
  )
}

/**
 * Company job count chart — one measure, one hue.
 */
export function CompanyBarChart({ data, height = 500 }) {
  const c = useChartColors()
  const sortedData = [...data]
    .sort((a, b) => b.job_count - a.job_count)
    .slice(0, 20)
    .reverse()

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={sortedData} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
        <CartesianGrid horizontal={false} stroke={c.gridColor} />
        <XAxis type="number" tickFormatter={formatNumber} tick={c.tickStyle} axisLine={{ stroke: c.axisColor }} tickLine={false} />
        <YAxis
          dataKey="company_name"
          type="category"
          tick={{ ...c.tickStyle, fontSize: 11 }}
          tickFormatter={truncate(18)}
          width={124}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          cursor={{ fill: c.gridColor, opacity: 0.35 }}
          content={<ChartTooltip isDark={c.isDark} rows={(payload) => [{
            label: 'Open positions', value: formatNumber(payload[0].value), color: c.series(0),
          }]} />}
        />
        <Bar dataKey="job_count" fill={c.series(0)} radius={[0, 4, 4, 0]} barSize={14} />
      </BarChart>
    </ResponsiveContainer>
  )
}

/**
 * Contract type donut — three fixed identities on stable series slots.
 */
export function ContractTypePieChart({ data, height = 250 }) {
  const c = useChartColors()
  const pieData = [
    { name: 'Full Time', value: data.full_time || 0, slot: 0 },
    { name: 'Part Time', value: data.part_time || 0, slot: 1 },
    { name: 'Contract', value: data.contract || 0, slot: 2 },
  ].filter(d => d.value > 0)
  const total = pieData.reduce((sum, d) => sum + d.value, 0)

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={pieData}
            cx="50%"
            cy="50%"
            innerRadius={45}
            outerRadius={80}
            paddingAngle={2}
            dataKey="value"
          >
            {pieData.map((entry) => (
              <Cell key={entry.name} fill={c.series(entry.slot)} stroke="none" />
            ))}
          </Pie>
          <Tooltip
            content={<ChartTooltip isDark={c.isDark}
              title={(payload) => payload[0]?.name}
              rows={(payload) => [
                { label: 'Jobs', value: formatNumber(payload[0]?.value) },
                { label: 'Share', value: `${((payload[0]?.value / total) * 100).toFixed(1)}%` },
              ]} />}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap gap-x-4 gap-y-1 justify-center mt-1">
        {pieData.map((entry) => (
          <span key={entry.name} className="inline-flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: c.series(entry.slot) }} />
            {entry.name} · {((entry.value / total) * 100).toFixed(0)}%
          </span>
        ))}
      </div>
    </div>
  )
}

/**
 * Country comparison bar chart — one measure, one hue.
 */
export function CountryComparisonChart({ data, valueKey = 'demand_percentage', height = 400 }) {
  const c = useChartColors()
  const isPercent = valueKey.includes('percentage')
  const sortedData = [...data]
    .sort((a, b) => b[valueKey] - a[valueKey])
    .map(d => ({
      ...d,
      display_name: d.country_name || d.country_code?.toUpperCase()
    }))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={sortedData} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
        <CartesianGrid horizontal={false} stroke={c.gridColor} />
        <XAxis
          type="number"
          tickFormatter={(v) => isPercent ? `${v.toFixed(1)}%` : formatNumber(v)}
          tick={c.tickStyle}
          axisLine={{ stroke: c.axisColor }}
          tickLine={false}
        />
        <YAxis
          dataKey="display_name"
          type="category"
          tick={c.tickStyle}
          tickFormatter={truncate(16)}
          width={112}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          cursor={{ fill: c.gridColor, opacity: 0.35 }}
          content={<ChartTooltip isDark={c.isDark} rows={(payload) => {
            const row = payload[0]?.payload || {}
            return [
              { label: isPercent ? 'Demand' : 'Jobs', value: isPercent ? `${payload[0].value.toFixed(2)}%` : formatNumber(payload[0].value), color: c.series(0) },
              ...(isPercent && row.job_count != null
                ? [{ label: 'Jobs', value: formatNumber(row.job_count) }]
                : []),
            ]
          }} />}
        />
        <Bar dataKey={valueKey} fill={c.series(0)} radius={[0, 4, 4, 0]} barSize={16} />
      </BarChart>
    </ResponsiveContainer>
  )
}

/**
 * Skill demand over time — multi-series line chart.
 *
 * Props:
 *   periods: [{ period: 'YYYY-MM-DD', total_jobs }]     (the % denominator)
 *   series:  [{ skill_name, points: [{ period, job_count, demand_percentage }] }]
 *   colorMap: { [skill_name]: slotIndex }               (stable per skill —
 *             assigned when a skill is added and kept until removed, so
 *             removing one series never repaints the others)
 *
 * The y-value is the share of that month's postings mentioning the skill —
 * comparable across months even when extraction volume varies. Months with a
 * small sample (n < 200) are flagged in the tooltip.
 */
export function SkillTrendChart({ periods, series, colorMap = {}, height = 360 }) {
  const c = useChartColors()

  const monthLabel = (iso) => {
    const d = new Date(iso)
    return d.toLocaleDateString(undefined, { month: 'short', year: '2-digit' })
  }

  // Pivot to Recharts rows: one row per period, one column per skill.
  const totals = Object.fromEntries(periods.map(p => [p.period, p.total_jobs]))
  const rows = periods.map(p => {
    const row = { period: p.period, total_jobs: p.total_jobs }
    for (const s of series) {
      const point = s.points.find(pt => pt.period === p.period)
      row[s.skill_name] = point ? point.demand_percentage : 0
      row[`${s.skill_name}__count`] = point ? point.job_count : 0
    }
    return row
  })

  const colorFor = (skill) => c.series(colorMap[skill] ?? 0)
  const LOW_SAMPLE = 200

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rows} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid vertical={false} stroke={c.gridColor} />
        <XAxis
          dataKey="period"
          tickFormatter={monthLabel}
          tick={c.tickStyle}
          axisLine={{ stroke: c.axisColor }}
          tickLine={false}
          padding={{ left: 10, right: 10 }}
        />
        <YAxis
          tickFormatter={(v) => `${v}%`}
          tick={c.tickStyle}
          axisLine={false}
          tickLine={false}
          width={45}
          domain={[0, 'auto']}
        />
        <Tooltip
          content={<ChartTooltip isDark={c.isDark}
            title={(payload, label) => {
              const n = totals[label]
              const flag = n != null && n < LOW_SAMPLE ? ' · ⚠ small sample' : ''
              return `${monthLabel(label)} — ${formatNumber(n)} postings${flag}`
            }}
            rows={(payload) => payload
              .filter(p => !p.dataKey.endsWith('__count'))
              .sort((a, b) => b.value - a.value)
              .map(p => ({
                label: p.dataKey,
                value: `${p.value.toFixed(1)}%  (${formatNumber(p.payload[`${p.dataKey}__count`])})`,
                color: colorFor(p.dataKey),
              }))} />}
        />
        <Legend
          verticalAlign="top"
          height={32}
          iconType="plainline"
          formatter={(value) => (
            <span className="text-xs" style={{ color: c.tickStyle.fill }}>{value}</span>
          )}
        />
        {series.map((s) => (
          <Line
            key={s.skill_name}
            type="monotone"
            dataKey={s.skill_name}
            stroke={colorFor(s.skill_name)}
            strokeWidth={2}
            dot={{ r: 3, fill: colorFor(s.skill_name), strokeWidth: 0 }}
            activeDot={{ r: 5, strokeWidth: 2, stroke: c.isDark ? '#161b22' : '#ffffff' }}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
