"""
Skill Discovery Manager
=======================
Manages the discovery and persistence of new skills found by the slow path.
Keeps the taxonomy fresh and growing automatically.

Features:
- Tracks newly discovered skills with occurrence counts
- Promotes high-confidence discoveries to the main taxonomy
- Persists discovery state to database
- Provides stats on discovery trends
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredSkill:
    """Represents a skill discovered by the LLM but not yet in taxonomy."""
    name: str
    category: str
    subcategory: str
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int = 1
    avg_confidence: float = 0.8
    sample_contexts: List[str] = field(default_factory=list)  # Sample job titles/snippets
    is_promoted: bool = False  # True if added to main taxonomy


class SkillDiscoveryManager:
    """
    Manages skill discovery lifecycle:
    1. Track new skills found by LLM
    2. Accumulate occurrence counts
    3. Promote frequently-seen skills to taxonomy
    4. Persist state to database/file
    """
    
    # Thresholds for promotion
    MIN_OCCURRENCES_FOR_PROMOTION = 3  # Must appear in at least N job descriptions
    MIN_CONFIDENCE_FOR_PROMOTION = 0.75  # Average confidence must be above this
    
    def __init__(self, db_connection=None, taxonomy_path: Optional[Path] = None):
        """
        Initialize the discovery manager.
        
        Args:
            db_connection: psycopg2 connection for database persistence
            taxonomy_path: Path to skills_taxonomy.json for file-based updates
        """
        self.db_conn = db_connection
        self.taxonomy_path = taxonomy_path
        self.discovered_skills: Dict[str, DiscoveredSkill] = {}  # name_lower -> DiscoveredSkill
        self._pending_promotions: List[str] = []
        
        # Load existing discoveries from DB if available
        if db_connection:
            self._load_from_database()
    
    def _normalize_skill_name(self, name: str) -> str:
        """Normalize skill name for deduplication."""
        # Basic normalization - could be enhanced with fuzzy matching
        return name.strip().lower()
    
    def record_discovery(self, skill: Dict, context: str = "") -> bool:
        """
        Record a newly discovered skill from the slow path.
        
        Args:
            skill: Dict with skill_name, category, subcategory, confidence
            context: Optional context (e.g., job title) for debugging
        
        Returns:
            True if this is a new discovery, False if already known
        """
        name = skill.get('skill_name', '').strip()
        if not name or len(name) < 2:
            return False
        
        key = self._normalize_skill_name(name)
        confidence = skill.get('confidence', 0.8)
        
        if key in self.discovered_skills:
            # Update existing discovery
            existing = self.discovered_skills[key]
            existing.occurrence_count += 1
            existing.last_seen = datetime.now()
            # Running average of confidence
            existing.avg_confidence = (
                (existing.avg_confidence * (existing.occurrence_count - 1) + confidence)
                / existing.occurrence_count
            )
            if context and len(existing.sample_contexts) < 5:
                existing.sample_contexts.append(context[:100])
            return False
        else:
            # New discovery
            self.discovered_skills[key] = DiscoveredSkill(
                name=name,  # Keep original casing
                category=skill.get('category', 'Other'),
                subcategory=skill.get('subcategory', ''),
                first_seen=datetime.now(),
                last_seen=datetime.now(),
                occurrence_count=1,
                avg_confidence=confidence,
                sample_contexts=[context[:100]] if context else []
            )
            logger.info(f"Discovery: New skill found - '{name}' ({skill.get('category', 'Other')})")
            return True
    
    def record_discoveries_batch(self, skills: List[Dict], context: str = "") -> Tuple[int, int]:
        """
        Record multiple discoveries from a single job description.
        
        Returns:
            Tuple of (new_discoveries_count, updated_count)
        """
        new_count = 0
        updated_count = 0
        
        for skill in skills:
            is_new = self.record_discovery(skill, context)
            if is_new:
                new_count += 1
            else:
                updated_count += 1
        
        return new_count, updated_count
    
    def get_promotion_candidates(self) -> List[DiscoveredSkill]:
        """
        Get skills that meet promotion criteria.
        
        Returns:
            List of DiscoveredSkill objects ready for promotion
        """
        candidates = []
        for skill in self.discovered_skills.values():
            if skill.is_promoted:
                continue
            if skill.occurrence_count >= self.MIN_OCCURRENCES_FOR_PROMOTION:
                if skill.avg_confidence >= self.MIN_CONFIDENCE_FOR_PROMOTION:
                    candidates.append(skill)
        
        # Sort by occurrence count descending
        candidates.sort(key=lambda x: x.occurrence_count, reverse=True)
        return candidates
    
    def promote_to_taxonomy(self, skill_name: str, fast_path_extractor=None) -> bool:
        """
        Promote a discovered skill to the main taxonomy.
        
        Args:
            skill_name: Name of the skill to promote
            fast_path_extractor: Optional FastPathExtractor to update at runtime
        
        Returns:
            True if promotion succeeded
        """
        key = self._normalize_skill_name(skill_name)
        if key not in self.discovered_skills:
            logger.warning(f"Cannot promote unknown skill: {skill_name}")
            return False
        
        skill = self.discovered_skills[key]
        if skill.is_promoted:
            logger.debug(f"Skill already promoted: {skill_name}")
            return True
        
        # Update taxonomy file if path is set
        if self.taxonomy_path:
            self._add_to_taxonomy_file(skill)
        
        # Update database if connected
        if self.db_conn:
            self._add_to_database(skill)
        
        # Update runtime extractor if provided
        if fast_path_extractor:
            fast_path_extractor.add_skill(
                name=skill.name,
                category=skill.category,
                subcategory=skill.subcategory
            )
        
        skill.is_promoted = True
        logger.info(f"Discovery: Promoted '{skill.name}' to taxonomy (seen {skill.occurrence_count}x)")
        return True
    
    def auto_promote(self, fast_path_extractor=None) -> List[str]:
        """
        Automatically promote all eligible skills.
        
        Returns:
            List of promoted skill names
        """
        candidates = self.get_promotion_candidates()
        promoted = []
        
        for skill in candidates:
            if self.promote_to_taxonomy(skill.name, fast_path_extractor):
                promoted.append(skill.name)
        
        if promoted:
            logger.info(f"Discovery: Auto-promoted {len(promoted)} skills to taxonomy")
        
        return promoted
    
    def _add_to_taxonomy_file(self, skill: DiscoveredSkill):
        """Add a skill to the taxonomy JSON file."""
        if not self.taxonomy_path or not self.taxonomy_path.exists():
            return
        
        try:
            with open(self.taxonomy_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check if skill already exists
            existing_names = {s['name'].lower() for s in data.get('skills', [])}
            if skill.name.lower() in existing_names:
                return
            
            # Add new skill
            new_entry = {
                'name': skill.name,
                'category': skill.category,
                'subcategory': skill.subcategory,
                'aliases': [],
                '_discovered': True,  # Mark as auto-discovered
                '_first_seen': skill.first_seen.isoformat(),
                '_occurrence_count': skill.occurrence_count
            }
            
            data['skills'].append(new_entry)
            
            # Write back
            with open(self.taxonomy_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Added '{skill.name}' to taxonomy file")
            
        except Exception as e:
            logger.error(f"Failed to update taxonomy file: {e}")
    
    def _add_to_database(self, skill: DiscoveredSkill):
        """Add a skill to the dim_skills table in database."""
        if not self.db_conn:
            return
        
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(
                """
                INSERT INTO staging.dim_skills (skill_name, skill_category, skill_subcategory)
                VALUES (%s, %s, %s)
                ON CONFLICT (skill_name) DO NOTHING
                RETURNING skill_id
                """,
                (skill.name, skill.category, skill.subcategory)
            )
            self.db_conn.commit()
            cursor.close()
        except Exception as e:
            logger.error(f"Failed to insert skill into database: {e}")
            self.db_conn.rollback()
    
    def _load_from_database(self):
        """Load existing discovered skills from database."""
        # This could be enhanced to load from a dedicated discovery tracking table
        pass
    
    def get_stats(self) -> Dict:
        """Get discovery statistics."""
        total = len(self.discovered_skills)
        promoted = sum(1 for s in self.discovered_skills.values() if s.is_promoted)
        candidates = len(self.get_promotion_candidates())
        
        # Top discoveries by occurrence
        top_discoveries = sorted(
            [s for s in self.discovered_skills.values() if not s.is_promoted],
            key=lambda x: x.occurrence_count,
            reverse=True
        )[:10]
        
        return {
            'total_discoveries': total,
            'promoted_count': promoted,
            'pending_promotion': candidates,
            'top_pending': [
                {
                    'name': s.name,
                    'category': s.category,
                    'occurrences': s.occurrence_count,
                    'avg_confidence': round(s.avg_confidence, 2)
                }
                for s in top_discoveries
            ]
        }
    
    def export_discoveries(self) -> List[Dict]:
        """Export all discoveries as a list of dicts."""
        return [
            {
                'name': s.name,
                'category': s.category,
                'subcategory': s.subcategory,
                'occurrence_count': s.occurrence_count,
                'avg_confidence': s.avg_confidence,
                'first_seen': s.first_seen.isoformat(),
                'last_seen': s.last_seen.isoformat(),
                'is_promoted': s.is_promoted,
                'sample_contexts': s.sample_contexts
            }
            for s in self.discovered_skills.values()
        ]
