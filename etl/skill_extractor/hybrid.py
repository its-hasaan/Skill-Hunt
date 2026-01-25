"""
Hybrid Skill Extractor
======================
Orchestrates fast path (regex/taxonomy) and slow path (GLiNER) extraction.

Strategy:
1. Always run fast path first (free, instant) for known skills
2. Optionally run GLiNER for skill discovery
3. Validate GLiNER findings against taxonomy (whitelist)
4. Mark unmatched skills as "Unverified" for manual review
5. Normalization (React.js -> React) handled by dbt layer
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass

from .fast_path import FastPathExtractor
from .slow_path import SlowPathExtractor, SlowPathConfig
from .skill_discovery import SkillDiscoveryManager

logger = logging.getLogger(__name__)


@dataclass 
class HybridConfig:
    """Configuration for the hybrid extractor."""
    # Fast path settings
    taxonomy_path: Path = None
    
    # Slow path (GLiNER) settings
    enable_gliner: bool = True  # Enable GLiNER for skill discovery
    gliner_model: str = "urchade/gliner_medium-v2.1"
    gliner_threshold: float = 0.4
    gliner_min_confidence: float = 0.5
    
    # Routing settings
    min_skills_for_fast_only: int = 5  # If fast path finds >= N skills, skip GLiNER
    always_discover: bool = False  # If True, always run GLiNER
    discovery_sample_rate: float = 0.1  # Sample 10% of jobs for discovery
    
    # Discovery settings
    auto_promote: bool = True  # Auto-promote discoveries meeting threshold
    

class HybridSkillExtractor:
    """
    Production skill extractor combining taxonomy matching and GLiNER discovery.
    
    Flow:
    1. Run fast path on all job descriptions (taxonomy-based)
    2. Optionally run GLiNER for skill discovery
    3. Validate GLiNER findings against taxonomy (whitelist)
    4. Merge results: fast path = verified, GLiNER not in taxonomy = unverified
    5. Track new discoveries for manual review
    """
    
    def __init__(
        self,
        config: Optional[HybridConfig] = None,
        taxonomy_path: Optional[Path] = None,
        gemini_api_key: Optional[str] = None,  # Deprecated, ignored
        db_connection=None
    ):
        """
        Initialize the hybrid extractor.
        
        Args:
            config: Full configuration object
            taxonomy_path: Path to skills_taxonomy.json
            gemini_api_key: DEPRECATED - ignored
            db_connection: Optional database connection for discovery persistence
        """
        # Build config from individual params if not provided
        if config is None:
            config = HybridConfig(taxonomy_path=taxonomy_path)
        
        self.config = config
        
        # Initialize fast path (taxonomy-based extraction)
        if config.taxonomy_path:
            self.fast_path = FastPathExtractor(taxonomy_path=config.taxonomy_path)
        else:
            logger.warning("HybridExtractor: No taxonomy path provided, fast path disabled")
            self.fast_path = None
        
        # Initialize slow path (GLiNER)
        if config.enable_gliner:
            slow_config = SlowPathConfig(
                model_name=config.gliner_model,
                threshold=config.gliner_threshold,
                min_confidence=config.gliner_min_confidence,
                enabled=True
            )
            self.slow_path = SlowPathExtractor(config=slow_config)
        else:
            self.slow_path = SlowPathExtractor(config=SlowPathConfig(enabled=False))
        
        # Initialize discovery manager
        self.discovery_manager = SkillDiscoveryManager(
            db_connection=db_connection,
            taxonomy_path=config.taxonomy_path
        )
        
        # Statistics
        self._stats = {
            'total_extractions': 0,
            'fast_path_only': 0,
            'gliner_invoked': 0,
            'new_discoveries': 0,
            'verified_skills': 0,
            'unverified_skills': 0
        }
        
        # For sampling-based discovery
        self._extraction_counter = 0
        
        # Determine mode
        if config.enable_gliner and self.slow_path.is_available():
            self.mode = 'hybrid'
        else:
            self.mode = 'fast_only'
        
        logger.info(f"HybridExtractor initialized in '{self.mode}' mode")
    
    def _should_invoke_gliner(self, fast_results: List[Dict]) -> bool:
        """
        Decide whether to invoke GLiNER for a given job.
        
        Returns:
            True if GLiNER should be invoked
        """
        if not self.config.enable_gliner:
            return False
        
        if not self.slow_path.is_available():
            return False
        
        # Always discover mode
        if self.config.always_discover:
            return True
        
        # Too few skills found by fast path
        if len(fast_results) < self.config.min_skills_for_fast_only:
            return True
        
        # Random sampling for discovery
        self._extraction_counter += 1
        sample_interval = int(1 / self.config.discovery_sample_rate) if self.config.discovery_sample_rate > 0 else 0
        if sample_interval > 0 and self._extraction_counter % sample_interval == 0:
            return True
        
        return False
    
    def _validate_against_taxonomy(self, gliner_skills: List[Dict]) -> tuple:
        """
        Validate GLiNER findings against taxonomy whitelist.
        
        Returns:
            (verified_skills, unverified_skills)
        """
        verified = []
        unverified = []
        
        for skill in gliner_skills:
            skill_name = skill.get('skill_name', '')
            
            # Check if skill is in taxonomy (fast path knows it)
            if self.fast_path and self.fast_path.is_known_skill(skill_name):
                # GLiNER found a known skill - mark as verified
                skill['verified'] = True
                skill['extraction_method'] = 'gliner_verified'
                verified.append(skill)
            else:
                # New skill not in taxonomy - mark as unverified
                skill['verified'] = False
                skill['extraction_method'] = 'gliner_unverified'
                unverified.append(skill)
        
        return verified, unverified
    
    def _merge_results(
        self,
        fast_results: List[Dict],
        gliner_results: List[Dict]
    ) -> tuple:
        """
        Merge fast path and GLiNER results.
        
        Strategy:
        - Fast path results are authoritative for known skills
        - GLiNER adds new discoveries (unverified)
        - Deduplication is case-insensitive
        
        Returns:
            (merged_skills, new_discoveries)
        """
        # Index fast results by normalized name
        merged: Dict[str, Dict] = {}
        
        # Add fast path results first (authoritative)
        for skill in fast_results:
            key = skill['skill_name'].lower()
            skill['verified'] = True
            skill['extraction_method'] = 'taxonomy'
            merged[key] = skill
        
        # Validate GLiNER results against taxonomy
        verified_gliner, unverified_gliner = self._validate_against_taxonomy(gliner_results)
        
        # Add GLiNER verified (already in taxonomy, but found by GLiNER)
        # Skip if fast path already found it
        for skill in verified_gliner:
            key = skill['skill_name'].lower()
            if key not in merged:
                merged[key] = skill
        
        # Add unverified discoveries
        new_discoveries = []
        for skill in unverified_gliner:
            key = skill['skill_name'].lower()
            if key not in merged:
                merged[key] = skill
                new_discoveries.append(skill)
        
        return list(merged.values()), new_discoveries
    
    def extract_skills(self, text: str, context: str = "") -> List[Dict]:
        """
        Extract skills from text using hybrid approach.
        
        Args:
            text: Job description to analyze
            context: Optional context (e.g., job title) for discovery tracking
        
        Returns:
            List of skill dicts with:
            - skill_name: Skill name
            - category: Skill category
            - subcategory: More specific classification
            - mention_count/confidence: Score
            - verified: True if from taxonomy, False if GLiNER discovery
            - extraction_method: 'taxonomy', 'gliner_verified', 'gliner_unverified'
        """
        self._stats['total_extractions'] += 1
        
        # Step 1: Fast path (always)
        fast_results = []
        if self.fast_path:
            fast_results = self.fast_path.extract_skills(text)
        
        # Step 2: Decide on GLiNER
        if self._should_invoke_gliner(fast_results):
            self._stats['gliner_invoked'] += 1
            
            gliner_results = self.slow_path.extract_skills(text)
            
            # Step 3: Merge results
            merged_results, new_discoveries = self._merge_results(fast_results, gliner_results)
            
            # Step 4: Track discoveries
            if new_discoveries:
                new_count, _ = self.discovery_manager.record_discoveries_batch(
                    new_discoveries,
                    context=context
                )
                self._stats['new_discoveries'] += new_count
                self._stats['unverified_skills'] += len(new_discoveries)
                
                # Auto-promote if enabled
                if self.config.auto_promote:
                    self.discovery_manager.auto_promote(self.fast_path)
            
            # Count verified
            verified_count = sum(1 for s in merged_results if s.get('verified', False))
            self._stats['verified_skills'] += verified_count
            
            return merged_results
        else:
            self._stats['fast_path_only'] += 1
            self._stats['verified_skills'] += len(fast_results)
            
            # Mark fast path results as verified
            for skill in fast_results:
                skill['verified'] = True
                skill['extraction_method'] = 'taxonomy'
            
            return fast_results
    
    def extract_skills_batch(
        self,
        texts: List[str],
        contexts: Optional[List[str]] = None
    ) -> List[List[Dict]]:
        """
        Extract skills from multiple texts.
        
        Args:
            texts: List of job descriptions
            contexts: Optional list of contexts (same length as texts)
        
        Returns:
            List of skill lists, one per input text
        """
        if contexts is None:
            contexts = [''] * len(texts)
        
        results = []
        for text, context in zip(texts, contexts):
            skills = self.extract_skills(text, context)
            results.append(skills)
        
        return results
    
    def get_stats(self) -> Dict:
        """Get extraction statistics."""
        discovery_stats = self.discovery_manager.get_stats()
        
        return {
            **self._stats,
            'fast_path_ratio': (
                self._stats['fast_path_only'] / max(1, self._stats['total_extractions'])
            ),
            'gliner_ratio': (
                self._stats['gliner_invoked'] / max(1, self._stats['total_extractions'])
            ),
            'discovery': discovery_stats,
            'mode': self.mode,
            'gliner_available': self.slow_path.is_available() if self.slow_path else False
        }
    
    def reset_stats(self):
        """Reset extraction statistics."""
        self._stats = {
            'total_extractions': 0,
            'fast_path_only': 0,
            'gliner_invoked': 0,
            'new_discoveries': 0,
            'verified_skills': 0,
            'unverified_skills': 0
        }
    
    def force_discover(self, text: str, context: str = "") -> List[Dict]:
        """
        Force GLiNER extraction regardless of routing rules.
        Useful for targeted discovery runs.
        """
        if not self.slow_path or not self.slow_path.is_available():
            logger.warning("force_discover called but GLiNER unavailable, using fast path only")
            return self.extract_skills(text, context)
        
        # Run both paths
        fast_results = self.fast_path.extract_skills(text) if self.fast_path else []
        gliner_results = self.slow_path.extract_skills(text)
        
        # Merge and track
        merged, new_discoveries = self._merge_results(fast_results, gliner_results)
        
        if new_discoveries:
            self.discovery_manager.record_discoveries_batch(new_discoveries, context)
            if self.config.auto_promote:
                self.discovery_manager.auto_promote(self.fast_path)
        
        return merged
    
    def get_known_skills_count(self) -> int:
        """Get count of skills in the taxonomy."""
        if self.fast_path:
            return len(self.fast_path.skills)
        return 0
    
    def get_discovered_skills(self) -> List[Dict]:
        """Get all discovered skills (unverified)."""
        return self.discovery_manager.export_discoveries()
