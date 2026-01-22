"""
Hybrid Skill Extraction Module
==============================
Combines fast keyword matching with LLM-based discovery for comprehensive skill extraction.

Architecture:
- FastPathExtractor: Regex-based matching for known skills (fast, free)
- SlowPathExtractor: LLM-based extraction for skill discovery (slower, costs tokens)
- HybridExtractor: Orchestrates both paths based on confidence thresholds

Usage:
    from skill_extractor import HybridSkillExtractor, HybridConfig
    
    config = HybridConfig(taxonomy_path=Path('config/skills_taxonomy.json'), gemini_api_key='...')
    extractor = HybridSkillExtractor(config=config)
    skills = extractor.extract_skills(job_description)
"""

from .fast_path import FastPathExtractor
from .slow_path import SlowPathExtractor, SlowPathConfig
from .hybrid import HybridSkillExtractor, HybridConfig
from .skill_discovery import SkillDiscoveryManager

__all__ = [
    'FastPathExtractor',
    'SlowPathExtractor',
    'SlowPathConfig',
    'HybridSkillExtractor',
    'HybridConfig',
    'SkillDiscoveryManager'
]
