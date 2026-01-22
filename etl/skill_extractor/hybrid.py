"""
Hybrid Skill Extractor
======================
Orchestrates fast path (regex) and slow path (LLM) extraction.
Implements the intelligent routing logic for optimal cost/coverage tradeoff.

Strategy:
1. Always run fast path first (free, instant)
2. Analyze coverage confidence
3. If confidence low OR discovery mode enabled, invoke slow path
4. Merge results, deduplicate, track discoveries
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
    
    # Slow path settings
    gemini_api_key: str = None
    gemini_model: str = "gemini-2.0-flash"
    
    # Hybrid routing settings
    coverage_threshold: float = 0.3  # Below this, invoke slow path
    min_skills_for_fast_only: int = 3  # If fast path finds >= N skills, skip slow path
    always_discover: bool = False  # If True, always run slow path for discovery
    discovery_sample_rate: float = 0.1  # Sample 10% of jobs for discovery even if coverage is good
    
    # Discovery settings
    auto_promote: bool = True  # Auto-promote discoveries meeting threshold
    

class HybridSkillExtractor:
    """
    Production skill extractor combining regex and LLM approaches.
    
    Flow:
    1. Run fast path on all job descriptions
    2. Calculate coverage confidence
    3. Route to slow path if:
       - Coverage below threshold, OR
       - Too few skills found, OR
       - Discovery mode enabled, OR
       - Randomly sampled for discovery
    4. Merge and deduplicate results
    5. Track new discoveries for taxonomy growth
    """
    
    def __init__(
        self,
        config: Optional[HybridConfig] = None,
        taxonomy_path: Optional[Path] = None,
        gemini_api_key: Optional[str] = None,
        db_connection=None
    ):
        """
        Initialize the hybrid extractor.
        
        Args:
            config: Full configuration object
            taxonomy_path: Path to skills_taxonomy.json
            gemini_api_key: Google Gemini API key
            db_connection: Optional database connection for discovery persistence
        """
        # Build config from individual params if not provided
        if config is None:
            config = HybridConfig(
                taxonomy_path=taxonomy_path,
                gemini_api_key=gemini_api_key
            )
        
        self.config = config
        
        # Initialize fast path
        if config.taxonomy_path:
            self.fast_path = FastPathExtractor(taxonomy_path=config.taxonomy_path)
        else:
            logger.warning("HybridExtractor: No taxonomy path provided, fast path disabled")
            self.fast_path = None
        
        # Initialize slow path
        if config.gemini_api_key:
            slow_config = SlowPathConfig(
                api_key=config.gemini_api_key,
                model=config.gemini_model
            )
            self.slow_path = SlowPathExtractor(config=slow_config)
        else:
            logger.info("HybridExtractor: No Gemini API key, slow path disabled")
            self.slow_path = None
        
        # Initialize discovery manager
        self.discovery_manager = SkillDiscoveryManager(
            db_connection=db_connection,
            taxonomy_path=config.taxonomy_path
        )
        
        # Statistics
        self._stats = {
            'total_extractions': 0,
            'fast_path_only': 0,
            'slow_path_invoked': 0,
            'new_discoveries': 0
        }
        
        # For sampling-based discovery
        self._extraction_counter = 0
    
    def _should_invoke_slow_path(self, fast_results: List[Dict], coverage_stats: dict) -> bool:
        """
        Decide whether to invoke the slow path for a given job.
        
        Returns:
            True if slow path should be invoked
        """
        if not self.slow_path or not self.slow_path.is_available():
            return False
        
        # Always discover mode
        if self.config.always_discover:
            return True
        
        # Too few skills found
        if len(fast_results) < self.config.min_skills_for_fast_only:
            return True
        
        # Low coverage confidence
        if coverage_stats.get('coverage_confidence', 1.0) < self.config.coverage_threshold:
            return True
        
        # Has unmatched potential terms
        unmatched = coverage_stats.get('unmatched_potential_terms', [])
        if len(unmatched) > 5:  # Many potential skills not in taxonomy
            return True
        
        # Random sampling for discovery
        self._extraction_counter += 1
        sample_interval = int(1 / self.config.discovery_sample_rate) if self.config.discovery_sample_rate > 0 else 0
        if sample_interval > 0 and self._extraction_counter % sample_interval == 0:
            return True
        
        return False
    
    def _merge_results(
        self,
        fast_results: List[Dict],
        slow_results: List[Dict]
    ) -> List[Dict]:
        """
        Merge fast and slow path results, preferring fast path for known skills.
        
        Returns:
            Merged and deduplicated skill list
        """
        # Index fast results by normalized name
        merged: Dict[str, Dict] = {}
        
        # Add fast path results first (authoritative for known skills)
        for skill in fast_results:
            key = skill['skill_name'].lower()
            merged[key] = skill
        
        # Add slow path results (new discoveries only)
        new_discoveries = []
        for skill in slow_results:
            key = skill['skill_name'].lower()
            if key not in merged:
                # Check if it's truly new (not in fast path taxonomy)
                if self.fast_path and not self.fast_path.is_known_skill(skill['skill_name']):
                    merged[key] = skill
                    new_discoveries.append(skill)
                elif not self.fast_path:
                    merged[key] = skill
                    new_discoveries.append(skill)
        
        return list(merged.values()), new_discoveries
    
    def extract_skills(self, text: str, context: str = "") -> List[Dict]:
        """
        Extract skills from text using the hybrid approach.
        
        Args:
            text: Job description to analyze
            context: Optional context (e.g., job title) for discovery tracking
        
        Returns:
            List of skill dicts with name, category, subcategory, mention_count/confidence
        """
        self._stats['total_extractions'] += 1
        
        # Step 1: Fast path (always)
        fast_results = []
        coverage_stats = {}
        
        if self.fast_path:
            fast_results = self.fast_path.extract_skills(text)
            coverage_stats = self.fast_path.get_coverage_stats(text)
        
        # Step 2: Decide on slow path
        if self._should_invoke_slow_path(fast_results, coverage_stats):
            self._stats['slow_path_invoked'] += 1
            
            slow_results = self.slow_path.extract_skills(text)
            
            # Step 3: Merge results
            merged_results, new_discoveries = self._merge_results(fast_results, slow_results)
            
            # Step 4: Track discoveries
            if new_discoveries:
                new_count, _ = self.discovery_manager.record_discoveries_batch(
                    new_discoveries,
                    context=context
                )
                self._stats['new_discoveries'] += new_count
                
                # Auto-promote if enabled
                if self.config.auto_promote:
                    promoted = self.discovery_manager.auto_promote(self.fast_path)
            
            return merged_results
        else:
            self._stats['fast_path_only'] += 1
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
            'slow_path_ratio': (
                self._stats['slow_path_invoked'] / max(1, self._stats['total_extractions'])
            ),
            'discovery': discovery_stats
        }
    
    def reset_stats(self):
        """Reset extraction statistics."""
        self._stats = {
            'total_extractions': 0,
            'fast_path_only': 0,
            'slow_path_invoked': 0,
            'new_discoveries': 0
        }
    
    def force_discover(self, text: str, context: str = "") -> List[Dict]:
        """
        Force slow path extraction regardless of coverage.
        Useful for targeted discovery runs.
        """
        if not self.slow_path or not self.slow_path.is_available():
            logger.warning("force_discover called but slow path unavailable")
            return self.extract_skills(text, context)
        
        # Run both paths
        fast_results = self.fast_path.extract_skills(text) if self.fast_path else []
        slow_results = self.slow_path.extract_skills(text)
        
        # Merge and track
        merged, new_discoveries = self._merge_results(fast_results, slow_results)
        
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
        """Get all discovered skills."""
        return self.discovery_manager.export_discoveries()
