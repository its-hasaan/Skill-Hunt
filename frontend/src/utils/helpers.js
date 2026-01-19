/**
 * Country names and flags mapping
 */
export const COUNTRY_INFO = {
  gb: { name: 'United Kingdom', flag: '🇬🇧' },
  us: { name: 'United States', flag: '🇺🇸' },
  au: { name: 'Australia', flag: '🇦🇺' },
  at: { name: 'Austria', flag: '🇦🇹' },
  be: { name: 'Belgium', flag: '🇧🇪' },
  br: { name: 'Brazil', flag: '🇧🇷' },
  ca: { name: 'Canada', flag: '🇨🇦' },
  de: { name: 'Germany', flag: '🇩🇪' },
  fr: { name: 'France', flag: '🇫🇷' },
  in: { name: 'India', flag: '🇮🇳' },
  it: { name: 'Italy', flag: '🇮🇹' },
  mx: { name: 'Mexico', flag: '🇲🇽' },
  nl: { name: 'Netherlands', flag: '🇳🇱' },
  nz: { name: 'New Zealand', flag: '🇳🇿' },
  pl: { name: 'Poland', flag: '🇵🇱' },
  sg: { name: 'Singapore', flag: '🇸🇬' },
  za: { name: 'South Africa', flag: '🇿🇦' },
}

export function getCountryName(code) {
  return COUNTRY_INFO[code]?.name || code?.toUpperCase() || 'Unknown'
}

export function getCountryFlag(code) {
  return COUNTRY_INFO[code]?.flag || '🌍'
}

export function getCountryDisplay(code) {
  const info = COUNTRY_INFO[code]
  if (info) {
    return `${info.flag} ${info.name}`
  }
  return code?.toUpperCase() || 'Unknown'
}

/**
 * Format number with commas
 */
export function formatNumber(num) {
  if (num === null || num === undefined) return 'N/A'
  return num.toLocaleString()
}

/**
 * Format currency
 */
export function formatCurrency(amount, currency = 'USD') {
  if (amount === null || amount === undefined) return 'N/A'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount)
}

/**
 * Format percentage
 */
export function formatPercent(value, decimals = 1) {
  if (value === null || value === undefined) return 'N/A'
  return `${value >= 0 ? '+' : ''}${value.toFixed(decimals)}%`
}

/**
 * Get color for skill category
 */
export const CATEGORY_COLORS = {
  'Programming Language': '#3b82f6',
  'Framework': '#10b981',
  'Database': '#f59e0b',
  'Cloud': '#6366f1',
  'DevOps': '#ec4899',
  'Data': '#8b5cf6',
  'AI/ML': '#14b8a6',
  'Security': '#ef4444',
  'Other': '#6b7280',
}

export function getCategoryColor(category) {
  return CATEGORY_COLORS[category] || CATEGORY_COLORS['Other']
}

/**
 * Chart color palette
 */
export const CHART_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#6366f1', '#ec4899',
  '#8b5cf6', '#14b8a6', '#ef4444', '#06b6d4', '#84cc16',
  '#f97316', '#a855f7', '#22c55e', '#eab308', '#0ea5e9',
]

/**
 * Get difficulty color
 */
export function getDifficultyColor(difficulty) {
  switch (difficulty) {
    case 'easy':
      return 'text-green-600 bg-green-100'
    case 'moderate':
      return 'text-yellow-600 bg-yellow-100'
    case 'significant':
      return 'text-red-600 bg-red-100'
    default:
      return 'text-gray-600 bg-gray-100'
  }
}

/**
 * Get difficulty emoji
 */
export function getDifficultyEmoji(difficulty) {
  switch (difficulty) {
    case 'easy':
      return '🟢'
    case 'moderate':
      return '🟡'
    case 'significant':
      return '🔴'
    default:
      return '⚪'
  }
}
