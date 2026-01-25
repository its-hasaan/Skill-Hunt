"""
Slow Path Skill Extractor (GLiNER NER-Based)
=============================================
Uses GLiNER (Generalist and Lightweight model for NER) for skill extraction.
This is the "discovery" path - finds skills not in our taxonomy.

Design Principles:
- Local, free extraction (no API costs)
- Only invoked when fast path has low confidence or discovery mode enabled
- Extracted skills validated against taxonomy as "whitelist"
- Unmatched skills stored as "Unverified" for manual review
- Normalization (React.js -> React) handled by dbt layer

NOTE: GLiNER may extract variations like "React" and "React.js" separately.
The dbt transformation layer should handle deduplication and normalization.
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Skill labels for GLiNER - these guide what entities to extract
GLINER_SKILL_LABELS = [
    "programming language",
    "database",
    "cloud platform",
    "cloud service",
    "big data tool",
    "data engineering tool",
    "machine learning framework",
    "devops tool",
    "web framework",
    "frontend framework",
    "backend framework",
    "data visualization tool",
    "version control",
    "api technology",
    "testing framework",
    "security tool",
    "operating system",
    "containerization tool",
    "orchestration tool",
    "message queue",
    "data warehouse",
    "etl tool",
    "bi tool",
    "monitoring tool",
    "ci cd tool"
]

# Map GLiNER labels to our taxonomy categories
LABEL_TO_CATEGORY = {
    "programming language": "Programming Language",
    "database": "Database",
    "cloud platform": "Cloud Platform",
    "cloud service": "Cloud Platform",
    "big data tool": "Big Data",
    "data engineering tool": "Data Engineering",
    "machine learning framework": "Machine Learning",
    "devops tool": "DevOps",
    "web framework": "Web Framework",
    "frontend framework": "Web Framework",
    "backend framework": "Web Framework",
    "data visualization tool": "Data Visualization",
    "version control": "Version Control",
    "api technology": "API & Integration",
    "testing framework": "Testing",
    "security tool": "Security",
    "operating system": "Operating System",
    "containerization tool": "DevOps",
    "orchestration tool": "DevOps",
    "message queue": "Big Data",
    "data warehouse": "Database",
    "etl tool": "Data Engineering",
    "bi tool": "Data Visualization",
    "monitoring tool": "DevOps",
    "ci cd tool": "DevOps"
}


@dataclass
class SlowPathConfig:
    """Configuration for the GLiNER-based skill extractor."""
    model_name: str = "urchade/gliner_medium-v2.1"  # Good balance of speed/accuracy
    threshold: float = 0.4  # Confidence threshold for entity extraction
    min_confidence: float = 0.5  # Minimum confidence to include in results
    enabled: bool = True  # Enable GLiNER extraction
    flat_ner: bool = True  # Use flat NER (no nested entities)
    multi_label: bool = False  # Allow multiple labels per entity
    batch_size: int = 8  # Batch size for processing multiple texts


class SlowPathExtractor:
    """
    GLiNER-based skill extraction for discovering new skills.
    
    Features:
    - Local, free extraction (no API costs)
    - Uses pre-trained NER model fine-tuned for entity extraction
    - Extracts technical skills, tools, frameworks, platforms
    - Returns confidence scores for filtering
    
    Integration with Taxonomy:
    - Fast path handles known skills (authoritative)
    - GLiNER discovers potential new skills
    - Hybrid layer validates GLiNER findings against taxonomy
    - Unmatched skills stored as "Unverified" for review
    """
    
    def __init__(self, config: Optional[SlowPathConfig] = None):
        """
        Initialize the GLiNER extractor.
        
        Args:
            config: Configuration object with model settings
        """
        self.config = config or SlowPathConfig()
        self._model = None
        self._available = None  # Cached availability check
        
        if self.config.enabled:
            logger.info(f"SlowPath: GLiNER extraction enabled (model: {self.config.model_name})")
        else:
            logger.info("SlowPath: GLiNER extraction disabled in config")
    
    def _load_model(self):
        """Lazy load the GLiNER model."""
        if self._model is None and self.config.enabled:
            try:
                from gliner import GLiNER
                
                logger.info(f"SlowPath: Loading GLiNER model '{self.config.model_name}'...")
                self._model = GLiNER.from_pretrained(self.config.model_name)
                logger.info("SlowPath: GLiNER model loaded successfully")
                self._available = True
                
            except ImportError:
                logger.warning("SlowPath: gliner package not installed. Run: pip install gliner")
                self._available = False
            except Exception as e:
                logger.error(f"SlowPath: Failed to load GLiNER model: {e}")
                self._available = False
        
        return self._model
    
    def is_available(self) -> bool:
        """Check if GLiNER is configured and ready."""
        if self._available is not None:
            return self._available
        
        if not self.config.enabled:
            self._available = False
            return False
        
        # Try to load model to check availability
        try:
            self._load_model()
            return self._available
        except:
            self._available = False
            return False
    
    def extract_skills(self, text: str) -> List[Dict]:
        """
        Extract skills from text using GLiNER.
        
        Args:
            text: Job description to analyze
        
        Returns:
            List of skill dicts with:
            - skill_name: Extracted skill text
            - category: Mapped category from label
            - subcategory: Original GLiNER label
            - confidence: Extraction confidence score
            - extraction_method: 'gliner'
            - verified: False (needs validation against taxonomy)
        """
        if not self.config.enabled:
            return []
        
        if not text or len(text.strip()) < 50:
            logger.debug("SlowPath: Text too short for analysis")
            return []
        
        model = self._load_model()
        if model is None:
            return []
        
        try:
            # Run GLiNER prediction
            entities = model.predict_entities(
                text,
                GLINER_SKILL_LABELS,
                threshold=self.config.threshold,
                flat_ner=self.config.flat_ner,
                multi_label=self.config.multi_label
            )
            
            # Process and filter results
            skills = []
            seen_skills = set()  # Deduplicate within same text
            
            for entity in entities:
                skill_name = entity.get('text', '').strip()
                label = entity.get('label', 'other')
                score = entity.get('score', 0.0)
                
                # Skip low confidence or empty
                if score < self.config.min_confidence:
                    continue
                if not skill_name or len(skill_name) < 2:
                    continue
                
                # Skip if already seen (case-insensitive)
                skill_key = skill_name.lower()
                if skill_key in seen_skills:
                    continue
                seen_skills.add(skill_key)
                
                # Skip generic terms
                if self._is_generic_term(skill_name):
                    continue
                
                # Map label to category
                category = LABEL_TO_CATEGORY.get(label, "Other")
                
                skills.append({
                    'skill_name': skill_name,
                    'category': category,
                    'subcategory': label,
                    'confidence': round(score, 3),
                    'extraction_method': 'gliner',
                    'verified': False  # Needs validation against taxonomy
                })
            
            logger.debug(f"SlowPath: Extracted {len(skills)} skills via GLiNER")
            return skills
            
        except Exception as e:
            logger.error(f"SlowPath: GLiNER extraction failed: {e}")
            return []
    
    def _is_generic_term(self, term: str) -> bool:
        """Filter out generic terms that aren't real skills."""
        generic_terms = {
            'software', 'technology', 'data', 'system', 'systems',
            'application', 'applications', 'tool', 'tools', 'platform',
            'service', 'services', 'solution', 'solutions', 'product',
            'products', 'framework', 'frameworks', 'library', 'libraries',
            'code', 'coding', 'programming', 'development', 'engineering',
            'analysis', 'analytics', 'database', 'databases', 'cloud',
            'api', 'apis', 'web', 'mobile', 'backend', 'frontend',
            'server', 'servers', 'client', 'clients', 'user', 'users',
            'project', 'projects', 'team', 'teams', 'experience',
            'skills', 'skill', 'knowledge', 'expertise', 'ability'
        }
        return term.lower() in generic_terms
    
    def extract_skills_batch(self, texts: List[str], batch_size: int = None) -> List[List[Dict]]:
        """
        Extract skills from multiple texts efficiently.
        
        Args:
            texts: List of job descriptions
            batch_size: Override default batch size
        
        Returns:
            List of skill lists, one per input text
        """
        if not self.config.enabled or not texts:
            return [[] for _ in texts]
        
        model = self._load_model()
        if model is None:
            return [[] for _ in texts]
        
        batch_size = batch_size or self.config.batch_size
        results = []
        
        # Process in batches for efficiency
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            
            try:
                # GLiNER batch prediction
                batch_entities = model.batch_predict_entities(
                    batch_texts,
                    GLINER_SKILL_LABELS,
                    threshold=self.config.threshold,
                    flat_ner=self.config.flat_ner,
                    multi_label=self.config.multi_label
                )
                
                # Process each text's entities
                for entities in batch_entities:
                    skills = self._process_entities(entities)
                    results.append(skills)
                    
            except Exception as e:
                logger.error(f"SlowPath: Batch extraction failed: {e}")
                # Return empty lists for failed batch
                results.extend([[] for _ in batch_texts])
        
        logger.info(f"SlowPath: Batch processed {len(texts)} texts")
        return results
    
    def _process_entities(self, entities: List[Dict]) -> List[Dict]:
        """Process raw GLiNER entities into skill dicts."""
        skills = []
        seen_skills = set()
        
        for entity in entities:
            skill_name = entity.get('text', '').strip()
            label = entity.get('label', 'other')
            score = entity.get('score', 0.0)
            
            if score < self.config.min_confidence:
                continue
            if not skill_name or len(skill_name) < 2:
                continue
            
            skill_key = skill_name.lower()
            if skill_key in seen_skills:
                continue
            seen_skills.add(skill_key)
            
            if self._is_generic_term(skill_name):
                continue
            
            category = LABEL_TO_CATEGORY.get(label, "Other")
            
            skills.append({
                'skill_name': skill_name,
                'category': category,
                'subcategory': label,
                'confidence': round(score, 3),
                'extraction_method': 'gliner',
                'verified': False
            })
        
        return skills
