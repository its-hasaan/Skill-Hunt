"""
Hybrid Skill Extraction Module
==============================
Combines fast keyword matching with GLiNER-based discovery for comprehensive skill extraction.

Architecture:
- FastPathExtractor: Regex-based matching for known skills (fast, free)
- SlowPathExtractor: GLiNER NER-based extraction for skill discovery (local, free)
- HybridExtractor: Orchestrates both paths, validates against taxonomy

Strategy:
1. Fast path extracts known skills from taxonomy (verified)
2. GLiNER discovers new skills not in taxonomy (unverified)
3. Unverified skills stored for manual review
4. Normalization (React.js -> React) handled by dbt layer

Usage:
    from skill_extractor import HybridSkillExtractor, HybridConfig
    
    config = HybridConfig(
        taxonomy_path=Path('config/skills_taxonomy.json'),
        enable_gliner=True
    )
    extractor = HybridSkillExtractor(config=config)
    skills = extractor.extract_skills(job_description)
    
    # Skills include:
    # - verified=True, extraction_method='taxonomy' (known skills)
    # - verified=False, extraction_method='gliner_unverified' (new discoveries)
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
