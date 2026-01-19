import { useState } from 'react'
import { useRoleSimilarity, useCareerTransitions, useSkillGap } from '../hooks/useData'
import { Card, ChartLoading, EmptyState, Badge } from '../components/ui'
import { getDifficultyEmoji, getDifficultyColor } from '../utils/helpers'

export default function CareerPage() {
  const [selectedRole, setSelectedRole] = useState('')
  const [targetRole, setTargetRole] = useState('')

  const { data: roleSimilarity, isLoading: simLoading } = useRoleSimilarity()
  const { data: transitions, isLoading: transLoading } = useCareerTransitions(selectedRole)
  const { data: skillGap, isLoading: gapLoading } = useSkillGap(selectedRole, targetRole)

  // Get unique roles from similarity data
  const roles = roleSimilarity 
    ? [...new Set([...roleSimilarity.map(r => r.role_1), ...roleSimilarity.map(r => r.role_2)])]
    : []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">🔄 Career Transition Guide</h1>
        <p className="text-gray-600">
          Discover how similar different tech roles are based on required skills
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Role Selector */}
        <Card title="🎯 Find Your Path">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                I am currently a:
              </label>
              <select
                value={selectedRole}
                onChange={(e) => {
                  setSelectedRole(e.target.value)
                  setTargetRole('')
                }}
                className="select-input"
                disabled={simLoading}
              >
                <option value="">Select your current role...</option>
                {roles.sort().map(role => (
                  <option key={role} value={role}>{role}</option>
                ))}
              </select>
            </div>

            {selectedRole && transitions?.transitions && (
              <div className="mt-6">
                <h4 className="font-medium text-gray-900 mb-3">
                  Roles similar to {selectedRole}:
                </h4>
                <div className="space-y-2">
                  {transitions.transitions.map((transition, index) => (
                    <div 
                      key={index}
                      className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                        targetRole === transition.target_role 
                          ? 'border-primary-500 bg-primary-50' 
                          : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                      }`}
                      onClick={() => setTargetRole(transition.target_role)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-lg">{getDifficultyEmoji(transition.difficulty)}</span>
                          <span className="font-medium text-gray-900">{transition.target_role}</span>
                        </div>
                        <Badge 
                          variant={
                            transition.difficulty === 'easy' ? 'success' :
                            transition.difficulty === 'moderate' ? 'warning' : 'danger'
                          }
                        >
                          {(transition.similarity * 100).toFixed(0)}% match
                        </Badge>
                      </div>
                      <div className="mt-1 text-sm text-gray-500">
                        {transition.shared_skills} shared skills • {
                          transition.difficulty === 'easy' ? 'Easy transition' :
                          transition.difficulty === 'moderate' ? 'Moderate transition' : 
                          'Significant upskilling needed'
                        }
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {transLoading && selectedRole && (
              <div className="space-y-2">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-16 bg-gray-100 rounded animate-pulse" />
                ))}
              </div>
            )}
          </div>
        </Card>

        {/* Skill Gap Analysis */}
        <Card title="📚 Skill Gap Analysis">
          {!selectedRole ? (
            <div className="text-center py-12 text-gray-500">
              <p>Select your current role to see transition options</p>
            </div>
          ) : !targetRole ? (
            <div className="text-center py-12 text-gray-500">
              <p>Select a target role to see the skill gap</p>
            </div>
          ) : gapLoading ? (
            <ChartLoading height={300} />
          ) : skillGap ? (
            <div className="space-y-4">
              {/* Transition Summary */}
              <div className={`p-4 rounded-lg ${getDifficultyColor(skillGap.difficulty)}`}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg">{getDifficultyEmoji(skillGap.difficulty)}</span>
                  <span className="font-medium">
                    {skillGap.difficulty === 'easy' ? 'Easy Transition' :
                     skillGap.difficulty === 'moderate' ? 'Moderate Transition' : 
                     'Significant Upskilling Needed'}
                  </span>
                </div>
                <p className="text-sm">
                  {(skillGap.similarity * 100).toFixed(0)}% skill overlap with {skillGap.shared_skills_count} shared skills
                </p>
              </div>

              {/* Shared Skills */}
              {skillGap.shared_skills?.length > 0 && (
                <div>
                  <h4 className="font-medium text-gray-900 mb-2">✅ Skills You Already Have:</h4>
                  <div className="flex flex-wrap gap-2">
                    {skillGap.shared_skills.slice(0, 10).map((skill, i) => (
                      <span key={i} className="px-2 py-1 bg-green-100 text-green-700 rounded text-sm">
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Skills to Learn */}
              {skillGap.skills_to_learn?.length > 0 && (
                <div>
                  <h4 className="font-medium text-gray-900 mb-2">📖 Skills to Learn:</h4>
                  <div className="space-y-2">
                    {skillGap.skills_to_learn.map((skill, i) => (
                      <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                        <span className="text-gray-900">{skill.skill_name}</span>
                        <span className="text-sm text-gray-500">{skill.skill_category}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <EmptyState description="Could not load skill gap data" />
          )}
        </Card>
      </div>

      {/* Role Similarity Matrix Info */}
      <Card title="🔗 All Role Similarities">
        {simLoading ? (
          <ChartLoading height={400} />
        ) : roleSimilarity?.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Role 1</th>
                  <th className="text-left py-3 px-4 font-medium text-gray-600">Role 2</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600">Shared Skills</th>
                  <th className="text-right py-3 px-4 font-medium text-gray-600">Similarity</th>
                  <th className="text-center py-3 px-4 font-medium text-gray-600">Difficulty</th>
                </tr>
              </thead>
              <tbody>
                {roleSimilarity.slice(0, 20).map((pair, index) => {
                  const difficulty = pair.jaccard_similarity >= 0.5 ? 'easy' :
                                    pair.jaccard_similarity >= 0.3 ? 'moderate' : 'significant'
                  return (
                    <tr key={index} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-3 px-4 text-gray-900">{pair.role_1}</td>
                      <td className="py-3 px-4 text-gray-900">{pair.role_2}</td>
                      <td className="py-3 px-4 text-right text-gray-600">{pair.shared_skills_count}</td>
                      <td className="py-3 px-4 text-right font-medium text-gray-900">
                        {(pair.jaccard_similarity * 100).toFixed(1)}%
                      </td>
                      <td className="py-3 px-4 text-center">
                        <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${getDifficultyColor(difficulty)}`}>
                          {getDifficultyEmoji(difficulty)} {difficulty}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState description="No role similarity data available" />
        )}
      </Card>
    </div>
  )
}
