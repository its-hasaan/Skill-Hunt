"""
Fast Path Skill Extractor
=========================
High-performance regex-based skill extraction for known skills.
Handles the top ~95% of skill mentions with zero latency and zero cost.

This is the "bread and butter" of the extraction pipeline - it handles
all the well-known skills like Python, SQL, AWS, etc. instantly.
"""

import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional

logger = logging.getLogger(__name__)


class FastPathExtractor:
    """
    Extracts skills using compiled regex patterns from a taxonomy.
    
    Optimizations:
    - Pre-compiled patterns for O(1) lookup
    - Word boundary matching to avoid false positives
    - Case-insensitive matching
    - Alias resolution to canonical names
    """
    
    def __init__(self, taxonomy_path: Optional[Path] = None, taxonomy_data: Optional[dict] = None):
        """
        Initialize with either a taxonomy file path or pre-loaded taxonomy data.
        
        Args:
            taxonomy_path: Path to skills_taxonomy.json
            taxonomy_data: Pre-loaded taxonomy dict (alternative to file)
        """
        self.skills: Dict[str, dict] = {}  # skill_name_lower -> {name, category, subcategory}
        self.patterns: List[Tuple[re.Pattern, str]] = []  # (compiled_pattern, canonical_name)
        self.known_skill_names: Set[str] = set()  # For quick membership testing
        
        if taxonomy_path:
            self._load_taxonomy_file(taxonomy_path)
        elif taxonomy_data:
            self._load_taxonomy_data(taxonomy_data)
    
    def _load_taxonomy_file(self, taxonomy_path: Path):
        """Load taxonomy from JSON file."""
        try:
            with open(taxonomy_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._load_taxonomy_data(data)
        except FileNotFoundError:
            logger.error(f"Taxonomy file not found: {taxonomy_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in taxonomy file: {e}")
            raise
    
    def _load_taxonomy_data(self, data: dict):
        """Load taxonomy from dict and compile patterns."""
        skills_list = data.get('skills', [])
        
        for skill in skills_list:
            name = skill['name']
            category = skill.get('category', 'Unknown')
            subcategory = skill.get('subcategory', '')
            aliases = skill.get('aliases', [])
            
            # Store skill metadata
            self.skills[name.lower()] = {
                'name': name,
                'category': category,
                'subcategory': subcategory
            }
            self.known_skill_names.add(name.lower())
            
            # Compile patterns for skill name and all aliases
            all_terms = [name] + aliases
            for term in all_terms:
                pattern = self._compile_pattern(term)
                self.patterns.append((pattern, name))
        
        logger.info(f"FastPath: Loaded {len(self.skills)} skills with {len(self.patterns)} patterns")
    
    def _compile_pattern(self, term: str) -> re.Pattern:
        """
        Compile a regex pattern for a skill term.
        Handles special cases like C++, C#, .NET, etc.
        """
        escaped = re.escape(term)
        
        # Special handling for programming language edge cases
        special_terms = {
            'C++': r'(?<![a-zA-Z])C\+\+(?![a-zA-Z])',
            'C#': r'(?<![a-zA-Z])C#(?![a-zA-Z])',
            '.NET': r'(?<![a-zA-Z])\.NET(?![a-zA-Z0-9])',
            'Node.js': r'\bNode\.?js\b',
            'Vue.js': r'\bVue\.?js\b',
            'Next.js': r'\bNext\.?js\b',
            'Nuxt.js': r'\bNuxt\.?js\b',
            'D3.js': r'\bD3\.?js\b',
            'Three.js': r'\bThree\.?js\b',
        }
        
        if term in special_terms:
            return re.compile(special_terms[term], re.IGNORECASE)
        
        # Standard word boundary pattern
        return re.compile(rf'\b{escaped}\b', re.IGNORECASE)
    
    def extract_skills(self, text: str) -> List[Dict]:
        """
        Extract known skills from text using regex matching.
        
        Args:
            text: Job description or any text to analyze
        
        Returns:
            List of skill dicts with name, category, subcategory, mention_count
        """
        if not text:
            return []
        
        found_skills: Dict[str, int] = {}  # canonical_name -> count
        
        for pattern, canonical_name in self.patterns:
            matches = pattern.findall(text)
            if matches:
                if canonical_name not in found_skills:
                    found_skills[canonical_name] = 0
                found_skills[canonical_name] += len(matches)
        
        # Build results with metadata
        results = []
        for skill_name, count in found_skills.items():
            skill_info = self.skills.get(skill_name.lower(), {})
            results.append({
                'skill_name': skill_name,
                'category': skill_info.get('category', 'Unknown'),
                'subcategory': skill_info.get('subcategory', ''),
                'mention_count': count,
                'extraction_method': 'fast_path'
            })
        
        # Sort by mention count descending
        results.sort(key=lambda x: x['mention_count'], reverse=True)
        return results
    
    def is_known_skill(self, skill_name: str) -> bool:
        """Check if a skill name exists in the taxonomy."""
        return skill_name.lower() in self.known_skill_names
    
    def get_skill_info(self, skill_name: str) -> Optional[dict]:
        """Get metadata for a known skill."""
        return self.skills.get(skill_name.lower())
    
    def add_skill(self, name: str, category: str, subcategory: str = '', aliases: List[str] = None):
        """
        Dynamically add a new skill to the extractor.
        Used for runtime taxonomy updates from discovered skills.
        """
        aliases = aliases or []
        
        self.skills[name.lower()] = {
            'name': name,
            'category': category,
            'subcategory': subcategory
        }
        self.known_skill_names.add(name.lower())
        
        # Compile and add patterns
        for term in [name] + aliases:
            pattern = self._compile_pattern(term)
            self.patterns.append((pattern, name))
        
        logger.debug(f"FastPath: Added new skill '{name}' with {len(aliases)} aliases")
    
    def get_coverage_stats(self, text: str) -> dict:
        """
        Analyze what percentage of technical terms are covered.
        Useful for deciding if slow path should be invoked.
        
        Returns:
            dict with coverage metrics
        """
        skills = self.extract_skills(text)
        total_skill_mentions = sum(s['mention_count'] for s in skills)
        unique_skills = len(skills)
        
        # Rough heuristic: count potential technical terms not matched
        # Look for CamelCase, ALL_CAPS, or terms with numbers
        potential_tech_terms = set(re.findall(
            r'\b(?:[A-Z][a-z]+[A-Z][a-z]*|[A-Z]{2,}|[a-zA-Z]+\d+|[a-zA-Z]+-[a-zA-Z]+)\b',
            text
        ))
        
        matched_terms = {s['skill_name'] for s in skills}
        unmatched_potential = potential_tech_terms - matched_terms
        
        return {
            'matched_skills': unique_skills,
            'total_mentions': total_skill_mentions,
            'unmatched_potential_terms': list(unmatched_potential)[:20],  # Limit to 20
            'coverage_confidence': min(1.0, unique_skills / max(1, len(potential_tech_terms)))
        }
