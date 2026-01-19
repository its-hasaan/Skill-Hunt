/**
 * Custom hooks for data fetching with React Query
 */
import { useQuery } from '@tanstack/react-query'
import { statsApi, skillsApi, companiesApi, salaryApi, careerApi } from '../api'

// ============================================
// Stats Hooks
// ============================================

export function useSummaryStats() {
  return useQuery({
    queryKey: ['stats', 'summary'],
    queryFn: statsApi.getSummary,
    staleTime: 1000 * 60 * 10, // 10 minutes
  })
}

export function useFilterOptions() {
  return useQuery({
    queryKey: ['stats', 'filters'],
    queryFn: statsApi.getFilters,
    staleTime: 1000 * 60 * 30, // 30 minutes
  })
}

// ============================================
// Skills Hooks
// ============================================

export function useSkillDemand(role, country = null, limit = 30) {
  return useQuery({
    queryKey: ['skills', 'demand', role, country, limit],
    queryFn: () => skillsApi.getDemand(role, country, limit),
    enabled: !!role,
  })
}

export function useSkillCooccurrence(role, skill = null, minCount = 5) {
  return useQuery({
    queryKey: ['skills', 'cooccurrence', role, skill, minCount],
    queryFn: () => skillsApi.getCooccurrence(role, skill, minCount),
    enabled: !!role,
  })
}

export function useSkillNetwork(role, minCount = 10, limit = 50) {
  return useQuery({
    queryKey: ['skills', 'network', role, minCount, limit],
    queryFn: () => skillsApi.getNetwork(role, minCount, limit),
    enabled: !!role,
  })
}

export function useSkillByCountry(skill, role) {
  return useQuery({
    queryKey: ['skills', 'byCountry', skill, role],
    queryFn: () => skillsApi.getByCountry(skill, role),
    enabled: !!skill && !!role,
  })
}

export function useSkillCategories() {
  return useQuery({
    queryKey: ['skills', 'categories'],
    queryFn: skillsApi.getCategories,
    staleTime: 1000 * 60 * 60, // 1 hour
  })
}

// ============================================
// Companies Hooks
// ============================================

export function useCompanyLeaderboard(role, country = null, limit = 50) {
  return useQuery({
    queryKey: ['companies', 'leaderboard', role, country, limit],
    queryFn: () => companiesApi.getLeaderboard(role, country, limit),
    enabled: !!role,
  })
}

export function useContractTypes(role, country = null) {
  return useQuery({
    queryKey: ['companies', 'contractTypes', role, country],
    queryFn: () => companiesApi.getContractTypes(role, country),
    enabled: !!role,
  })
}

// ============================================
// Salary Hooks
// ============================================

export function useSalaryBySkill(role, country = null, minJobs = 5) {
  return useQuery({
    queryKey: ['salary', 'bySkill', role, country, minJobs],
    queryFn: () => salaryApi.getBySkill(role, country, minJobs),
    enabled: !!role,
  })
}

export function useTopPayingSkills(role, country = null, limit = 15) {
  return useQuery({
    queryKey: ['salary', 'topPaying', role, country, limit],
    queryFn: () => salaryApi.getTopPaying(role, country, limit),
    enabled: !!role,
  })
}

export function usePremiumSkills(role, country = null, limit = 15) {
  return useQuery({
    queryKey: ['salary', 'premium', role, country, limit],
    queryFn: () => salaryApi.getPremiumSkills(role, country, limit),
    enabled: !!role,
  })
}

// ============================================
// Career Hooks
// ============================================

export function useRoleSimilarity() {
  return useQuery({
    queryKey: ['career', 'roleSimilarity'],
    queryFn: careerApi.getRoleSimilarity,
    staleTime: 1000 * 60 * 30, // 30 minutes
  })
}

export function useCareerTransitions(currentRole) {
  return useQuery({
    queryKey: ['career', 'transitions', currentRole],
    queryFn: () => careerApi.getTransitions(currentRole),
    enabled: !!currentRole,
  })
}

export function useSimilarityMatrix() {
  return useQuery({
    queryKey: ['career', 'similarityMatrix'],
    queryFn: careerApi.getSimilarityMatrix,
    staleTime: 1000 * 60 * 30, // 30 minutes
  })
}

export function useSkillGap(fromRole, toRole) {
  return useQuery({
    queryKey: ['career', 'skillGap', fromRole, toRole],
    queryFn: () => careerApi.getSkillGap(fromRole, toRole),
    enabled: !!fromRole && !!toRole && fromRole !== toRole,
  })
}
