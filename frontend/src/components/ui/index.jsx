import clsx from 'clsx'

/**
 * Loading skeleton component
 */
export function Skeleton({ className }) {
  return (
    <div className={clsx('animate-pulse bg-gray-200 rounded', className)} />
  )
}

/**
 * Loading spinner
 */
export function Spinner({ size = 'md', className }) {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
  }

  return (
    <div className={clsx('flex justify-center items-center', className)}>
      <div className={clsx(
        'animate-spin rounded-full border-2 border-gray-300 border-t-primary-600',
        sizeClasses[size]
      )} />
    </div>
  )
}

/**
 * Loading state for charts
 */
export function ChartLoading({ height = 300 }) {
  return (
    <div 
      className="flex items-center justify-center bg-gray-50 rounded-lg"
      style={{ height }}
    >
      <div className="text-center">
        <Spinner />
        <p className="mt-2 text-sm text-gray-500">Loading chart...</p>
      </div>
    </div>
  )
}

/**
 * Error state component
 */
export function ErrorState({ message = 'Something went wrong', onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center">
      <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-4">
        <svg className="w-8 h-8 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      </div>
      <h3 className="text-lg font-medium text-gray-900 mb-1">Error</h3>
      <p className="text-sm text-gray-500 mb-4">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn-primary">
          Try Again
        </button>
      )}
    </div>
  )
}

/**
 * Empty state component
 */
export function EmptyState({ 
  title = 'No data', 
  description = 'No data available for the selected filters.',
  icon = null 
}) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center">
      {icon || (
        <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
          <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
          </svg>
        </div>
      )}
      <h3 className="text-lg font-medium text-gray-900 mb-1">{title}</h3>
      <p className="text-sm text-gray-500">{description}</p>
    </div>
  )
}

/**
 * Stat card component
 */
export function StatCard({ title, value, icon: Icon, color = 'primary', loading = false }) {
  const colorClasses = {
    primary: 'from-primary-500 to-primary-600',
    accent: 'from-accent-500 to-accent-600',
    green: 'from-green-500 to-green-600',
    yellow: 'from-yellow-500 to-yellow-600',
    red: 'from-red-500 to-red-600',
  }

  if (loading) {
    return (
      <div className={`bg-gradient-to-br ${colorClasses[color]} rounded-xl p-4`}>
        <Skeleton className="h-4 w-20 bg-white/30 mb-2" />
        <Skeleton className="h-8 w-24 bg-white/30" />
      </div>
    )
  }

  return (
    <div className={`bg-gradient-to-br ${colorClasses[color]} rounded-xl p-4 text-white`}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-white/80">{title}</span>
        {Icon && <Icon className="h-5 w-5 text-white/60" />}
      </div>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  )
}

/**
 * Card component
 */
export function Card({ title, children, className, headerAction }) {
  return (
    <div className={clsx('bg-white rounded-xl shadow-sm border border-gray-100', className)}>
      {title && (
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          {headerAction}
        </div>
      )}
      <div className="p-6">{children}</div>
    </div>
  )
}

/**
 * Tab component
 */
export function Tabs({ tabs, activeTab, onChange }) {
  return (
    <div className="flex gap-2 p-1 bg-gray-100 rounded-lg">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={clsx(
            'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors',
            activeTab === tab.id
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
          )}
        >
          {tab.icon && <tab.icon className="h-4 w-4" />}
          {tab.label}
        </button>
      ))}
    </div>
  )
}

/**
 * Badge component
 */
export function Badge({ children, variant = 'default', className }) {
  const variants = {
    default: 'bg-gray-100 text-gray-700',
    primary: 'bg-primary-100 text-primary-700',
    success: 'bg-green-100 text-green-700',
    warning: 'bg-yellow-100 text-yellow-700',
    danger: 'bg-red-100 text-red-700',
  }

  return (
    <span className={clsx(
      'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
      variants[variant],
      className
    )}>
      {children}
    </span>
  )
}
