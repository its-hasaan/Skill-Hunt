import { useMemo, useState, useEffect } from 'react'
import { useSearchParams, useNavigate, useOutletContext } from 'react-router-dom'
import {
  ArrowLeft, MapPin, Building2, ExternalLink, CalendarDays, ChevronLeft, ChevronRight,
} from 'lucide-react'
import { useSkillJobs } from '../hooks/useData'
import { Card, ChartLoading, EmptyState, ErrorState, Badge } from '../components/ui'
import { formatNumber, formatCurrency, getCountryDisplay } from '../utils/helpers'

const PAGE_SIZE = 20

/**
 * Build a case-insensitive matcher from the highlight skills (name + aliases).
 * Returns { regex, selectedTerms } or null when there is nothing to highlight.
 */
function buildHighlighter(highlightSkills = []) {
  const termMap = new Map() // lowercased term -> { term, isSelected }
  for (const hs of highlightSkills) {
    const terms = [hs.skill_name, ...(hs.aliases || [])]
    for (const t of terms) {
      if (!t) continue
      const key = t.toLowerCase()
      // A selected match always wins over a non-selected one.
      if (!termMap.has(key) || hs.is_selected) {
        termMap.set(key, { term: t, isSelected: !!hs.is_selected })
      }
    }
  }

  // Skip single-character alias noise (e.g. stray "R"/"C") unless it's the selected skill.
  const entries = [...termMap.values()].filter((e) => e.term.length >= 2 || e.isSelected)
  if (entries.length === 0) return null

  // Longest terms first so "Machine Learning" wins over "Learning".
  entries.sort((a, b) => b.term.length - a.term.length)
  const escaped = entries.map((e) => e.term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const selectedTerms = new Set(entries.filter((e) => e.isSelected).map((e) => e.term.toLowerCase()))

  // Alnum boundaries (not \b) so tokens like "C++", ".NET", "Node.js" still match.
  const regex = new RegExp(`(?<![A-Za-z0-9])(${escaped.join('|')})(?![A-Za-z0-9])`, 'gi')
  return { regex, selectedTerms }
}

function HighlightedText({ text, highlighter }) {
  if (!text) return <span className="text-gray-400 dark:text-gray-500 italic">No description available.</span>
  if (!highlighter) return <>{text}</>

  const { regex, selectedTerms } = highlighter
  const parts = []
  let lastIndex = 0
  let match
  regex.lastIndex = 0

  while ((match = regex.exec(text)) !== null) {
    const start = match.index
    const end = start + match[0].length
    if (start > lastIndex) parts.push(text.slice(lastIndex, start))

    const isSelected = selectedTerms.has(match[0].toLowerCase())
    parts.push(
      <mark
        key={`${start}-${match[0]}`}
        className={
          isSelected
            ? 'rounded px-0.5 font-semibold bg-amber-300 text-amber-950 dark:bg-amber-400 dark:text-amber-950'
            : 'rounded px-0.5 bg-primary-100 text-primary-800 dark:bg-primary-500/30 dark:text-primary-200'
        }
      >
        {match[0]}
      </mark>
    )
    lastIndex = end
    if (regex.lastIndex === start) regex.lastIndex++ // guard against zero-length loops
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex))
  return <>{parts}</>
}

function formatDate(value) {
  if (!value) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

function salaryText(job) {
  const cur = job.salary_currency || 'USD'
  const { salary_min: min, salary_max: max } = job
  if (min == null && max == null) return null
  let text
  if (min != null && max != null) text = `${formatCurrency(min, cur)} – ${formatCurrency(max, cur)}`
  else text = formatCurrency(min ?? max, cur)
  return job.salary_is_predicted ? `${text} (est.)` : text
}

export default function JobsPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const outlet = useOutletContext() || {}

  const skill = searchParams.get('skill') || ''
  const role = searchParams.get('role') || outlet.selectedRole || ''
  const country = searchParams.get('country') || outlet.selectedCountry || null

  const [page, setPage] = useState(0)
  // Reset to the first page whenever the drill-down target changes.
  useEffect(() => { setPage(0) }, [skill, role, country])

  const { data, isLoading, isError, refetch, isFetching } = useSkillJobs(
    skill, role, country, PAGE_SIZE, page * PAGE_SIZE
  )

  const highlighter = useMemo(
    () => buildHighlighter(data?.highlight_skills),
    [data?.highlight_skills]
  )

  const totalCount = data?.total_count || 0
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE))

  if (!skill || !role) {
    return (
      <div className="space-y-6">
        <button onClick={() => navigate(-1)} className="inline-flex items-center gap-1 text-sm text-primary-600 dark:text-primary-400 hover:underline">
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <EmptyState
          title="Nothing to show"
          description="Open this page by clicking a skill from the Dashboard or Skills page."
        />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-1 text-sm text-primary-600 dark:text-primary-400 hover:underline w-fit"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </button>

        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
              Jobs mentioning <span className="text-primary-600 dark:text-primary-400">{skill}</span>
            </h1>
            <p className="text-gray-600 dark:text-gray-400">
              {role}
              {country ? ` · ${getCountryDisplay(country)}` : ' · All countries'}
              {' · '}
              {isLoading ? 'Loading…' : `${formatNumber(totalCount)} job${totalCount === 1 ? '' : 's'}`}
            </p>
          </div>

          {/* Legend */}
          <div className="flex items-center gap-4 text-xs text-gray-600 dark:text-gray-400">
            <span className="inline-flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 rounded bg-amber-300 dark:bg-amber-400" /> Selected skill
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="inline-block h-3 w-3 rounded bg-primary-100 dark:bg-primary-500/30" /> Other top skills
            </span>
          </div>
        </div>
      </div>

      {/* Body */}
      {isLoading ? (
        <ChartLoading height={400} />
      ) : isError ? (
        <ErrorState message="Could not load job postings." onRetry={refetch} />
      ) : !data?.jobs?.length ? (
        <EmptyState
          title="No job postings found"
          description={`No stored postings mention "${skill}" for ${role}${country ? ` in ${getCountryDisplay(country)}` : ''}.`}
        />
      ) : (
        <div className="space-y-4">
          {data.jobs.map((job) => {
            const postedOn = formatDate(job.job_posted_at)
            const salary = salaryText(job)
            return (
              <Card key={job.job_id} className="overflow-hidden">
                <div className="flex flex-col gap-3">
                  {/* Title + apply */}
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                        {job.title || 'Untitled role'}
                      </h3>
                      <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-600 dark:text-gray-400">
                        {job.company_name && (
                          <span className="inline-flex items-center gap-1">
                            <Building2 className="h-4 w-4" /> {job.company_name}
                          </span>
                        )}
                        {job.location_display && (
                          <span className="inline-flex items-center gap-1">
                            <MapPin className="h-4 w-4" /> {job.location_display}
                          </span>
                        )}
                        {postedOn && (
                          <span className="inline-flex items-center gap-1">
                            <CalendarDays className="h-4 w-4" /> {postedOn}
                          </span>
                        )}
                      </div>
                    </div>
                    {job.redirect_url && (
                      <a
                        href={job.redirect_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="shrink-0 inline-flex items-center gap-1 rounded-lg bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium px-3 py-2"
                      >
                        View <ExternalLink className="h-4 w-4" />
                      </a>
                    )}
                  </div>

                  {/* Meta row */}
                  <div className="flex flex-wrap items-center gap-2">
                    {salary && <Badge variant="success">{salary}</Badge>}
                    {job.contract_time && <Badge>{job.contract_time.replace('_', ' ')}</Badge>}
                    {job.contract_type && <Badge>{job.contract_type.replace('_', ' ')}</Badge>}
                  </div>

                  {/* Matched skills chips */}
                  {job.matched_skills?.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-xs text-gray-500 dark:text-gray-400 mr-1">Top skills here:</span>
                      {job.matched_skills.map((s) => (
                        <Badge key={s} variant={s === skill ? 'warning' : 'primary'}>{s}</Badge>
                      ))}
                    </div>
                  )}

                  {/* Description with highlights */}
                  <div className="mt-1 max-h-64 overflow-y-auto rounded-lg bg-gray-50 dark:bg-gray-900/40 p-4 text-sm leading-relaxed text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
                    <HighlightedText text={job.description} highlighter={highlighter} />
                  </div>
                </div>
              </Card>
            )
          })}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0 || isFetching}
                className="inline-flex items-center gap-1 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-700/50"
              >
                <ChevronLeft className="h-4 w-4" /> Previous
              </button>
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Page {page + 1} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => (p + 1 < totalPages ? p + 1 : p))}
                disabled={page + 1 >= totalPages || isFetching}
                className="inline-flex items-center gap-1 rounded-lg border border-gray-200 dark:border-gray-700 px-3 py-2 text-sm text-gray-700 dark:text-gray-300 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-700/50"
              >
                Next <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
