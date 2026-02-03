/**
 * API client for Skill Hunt backend
 */
import axios from 'axios'

// Base URL - use environment variable in production
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    throw error
  }
)

// ============================================
// Stats API
// ============================================

export const statsApi = {
  getSummary: () => api.get('/stats/summary'),
  getFilters: () => api.get('/stats/filters'),
  getRoles: () => api.get('/stats/roles'),
  getCountries: () => api.get('/stats/countries'),
}

// ============================================
// Skills API
// ============================================

export const skillsApi = {
  getDemand: (role, country = null, limit = 30) => {
    const params = { role, limit }
    if (country) params.country = country
    return api.get('/skills/demand', { params })
  },

  getAllDemand: (limit = 500) => 
    api.get('/skills/demand/all', { params: { limit } }),

  getCooccurrence: (role, skill = null, minCount = 5, limit = 100) => {
    const params = { role, min_count: minCount, limit }
    if (skill) params.skill = skill
    return api.get('/skills/cooccurrence', { params })
  },

  getNetwork: (role, minCount = 10, limit = 50) => 
    api.get('/skills/network', { params: { role, min_count: minCount, limit } }),

  getByCountry: (skill, role) => 
    api.get('/skills/by-country', { params: { skill, role } }),

  getCategories: () => api.get('/skills/categories'),

  getList: (category = null) => {
    const params = category ? { category } : {}
    return api.get('/skills/list', { params })
  },
}

// ============================================
// Companies API
// ============================================

export const companiesApi = {
  getLeaderboard: (role, country = null, limit = 50) => {
    const params = { role, limit }
    if (country) params.country = country
    return api.get('/companies/leaderboard', { params })
  },

  getContractTypes: (role, country = null) => {
    const params = { role }
    if (country) params.country = country
    return api.get('/companies/contract-types', { params })
  },

  search: (query, role = null, limit = 20) => {
    const params = { query, limit }
    if (role) params.role = role
    return api.get('/companies/search', { params })
  },
}

// ============================================
// Salary API
// ============================================

export const salaryApi = {
  getBySkill: (role, country = null, minJobs = 5, limit = 50) => {
    const params = { role, min_jobs: minJobs, limit }
    if (country) params.country = country
    return api.get('/salary/by-skill', { params })
  },

  getTopPaying: (role, country = null, limit = 15) => {
    const params = { role, limit }
    if (country) params.country = country
    return api.get('/salary/top-paying-skills', { params })
  },

  getPremiumSkills: (role, country = null, limit = 15) => {
    const params = { role, limit }
    if (country) params.country = country
    return api.get('/salary/premium-skills', { params })
  },

  getRange: (role, country = null) => {
    const params = { role }
    if (country) params.country = country
    return api.get('/salary/range', { params })
  },
}

// ============================================
// Career API
// ============================================

export const careerApi = {
  getRoleSimilarity: () => api.get('/career/role-similarity'),

  getTransitions: (currentRole) => 
    api.get(`/career/transitions/${encodeURIComponent(currentRole)}`),

  getSimilarityMatrix: () => api.get('/career/similarity-matrix'),

  getSkillGap: (fromRole, toRole) => 
    api.get('/career/skill-gap', { params: { from_role: fromRole, to_role: toRole } }),
}

// ============================================
// Resume Analysis API
// ============================================

export const resumeApi = {
  /**
   * Extract skills from uploaded resume
   * @param {File} file - Resume file (PDF, DOCX, TXT)
   */
  extractSkills: async (file) => {
    const formData = new FormData()
    formData.append('file', file)
    
    const response = await axios.post(`${API_BASE_URL}/resume/extract-skills`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    })
    return response.data
  },

  /**
   * Analyze resume against target role (Gap Analysis)
   * @param {File} file - Resume file
   * @param {string} targetRole - Target job role
   * @param {string|null} country - Country code (optional)
   */
  analyze: async (file, targetRole, country = null) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('target_role', targetRole)
    if (country) formData.append('country', country)
    
    const response = await axios.post(`${API_BASE_URL}/resume/analyze`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    })
    return response.data
  },

  /**
   * Match resume skills against all roles
   * @param {File} file - Resume file
   * @param {string|null} country - Country code (optional)
   * @param {number} limit - Max roles to return
   */
  matchRoles: async (file, country = null, limit = 10) => {
    const formData = new FormData()
    formData.append('file', file)
    if (country) formData.append('country', country)
    formData.append('limit', limit)
    
    const response = await axios.post(`${API_BASE_URL}/resume/match-roles`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    })
    return response.data
  },

  /**
   * Get list of supported roles for analysis
   */
  getSupportedRoles: () => api.get('/resume/supported-roles'),
}

export default api
