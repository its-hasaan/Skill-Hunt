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
  pk: { name: 'Pakistan', flag: '🇵🇰' },
  remote: { name: 'Remote / Worldwide', flag: '🌐' },
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
 * Chart series palette — 8 categorical slots, CVD-validated for both themes
 * (adjacent-pair colorblind separation + lightness band + chroma floor,
 * checked against the app's light/dark card surfaces). The slot ORDER is the
 * colorblind-safety mechanism — never reorder or generate extra hues; a 9th
 * series folds into "Other" gray.
 */
export const SERIES_COLORS = {
  light: ['#2a78d6', '#1baf7a', '#eda100', '#008300', '#4a3aa7', '#e34948', '#e87ba4', '#eb6834'],
  dark:  ['#3987e5', '#199e70', '#c98500', '#008300', '#9085e9', '#e66767', '#d55181', '#d95926'],
}

/** Neutral for "Other" / unknown — identical in both themes. */
export const SERIES_NEUTRAL = '#898781'

export function getSeriesColor(index, isDark = false) {
  const palette = isDark ? SERIES_COLORS.dark : SERIES_COLORS.light
  return index >= 0 && index < palette.length ? palette[index] : SERIES_NEUTRAL
}

/**
 * Skill-category colors — FIXED category→slot assignment so a category keeps
 * its color across every chart, filter, and page (color follows the entity,
 * never its current rank). Categories map onto 8 semantic families to stay
 * inside the CVD-validated palette; anything not listed renders neutral gray
 * rather than silently reusing a slot. Keep in sync with the categories in
 * `etl/config/skills_taxonomy.json` (checked against the live taxonomy).
 */
const CATEGORY_SLOTS = {
  // slot 0 — blue: languages & frameworks
  'Programming Language': 0,
  'Web Framework': 0,
  // slot 1 — aqua: data & analytics tooling
  'Data Science': 1,
  'Data Visualization': 1,
  'BI/Visualization': 1,
  'Data Engineering': 1,
  'Big Data': 1,
  // slot 2 — yellow: storage
  'Database': 2,
  'Data Warehouse': 2,
  'Data Platform': 2,
  // slot 3 — green: AI/ML
  'Machine Learning': 3,
  // slot 4 — violet: cloud & infra
  'Cloud': 4,
  'Cloud Platform': 4,
  'Architecture': 4,
  // slot 5 — red: security & ops
  'Security': 5,
  'DevOps': 5,
  'Operating System': 5,
  // slot 6 — magenta: app layers
  'Frontend': 6,
  'Backend': 6,
  'Mobile': 6,
  'API & Integration': 6,
  // slot 7 — orange: practices & tooling
  'Methodology': 7,
  'Testing': 7,
  'Version Control': 7,
  'Soft Skills': 7,
  'Productivity': 7,
}

export function getCategoryColor(category, isDark = false) {
  const slot = CATEGORY_SLOTS[category]
  return slot === undefined ? SERIES_NEUTRAL : getSeriesColor(slot, isDark)
}

/** @deprecated kept for compatibility — prefer getCategoryColor(category, isDark) */
export const CATEGORY_COLORS = Object.fromEntries(
  Object.entries(CATEGORY_SLOTS).map(([cat, slot]) => [cat, SERIES_COLORS.light[slot]])
)
CATEGORY_COLORS['Other'] = SERIES_NEUTRAL

/**
 * Chart color palette (light-mode slots; theme-aware code should use
 * SERIES_COLORS / getSeriesColor instead)
 */
export const CHART_COLORS = SERIES_COLORS.light

/**
 * Get difficulty color
 */
export function getDifficultyColor(difficulty) {
  switch (difficulty) {
    case 'easy':
      return 'text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/30'
    case 'moderate':
      return 'text-yellow-600 dark:text-yellow-400 bg-yellow-100 dark:bg-yellow-900/30'
    case 'significant':
      return 'text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-900/30'
    default:
      return 'text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-700'
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
