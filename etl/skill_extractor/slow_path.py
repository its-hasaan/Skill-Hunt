"""
Slow Path Skill Extractor (LLM-Based)
=====================================
Uses Google Gemini Flash for intelligent skill extraction from job descriptions.
This is the "discovery" path - it finds skills not in our taxonomy.

Design Principles:
- Only invoked when fast path has low confidence or explicit discovery mode
- Uses structured JSON output for reliable parsing
- Includes skill categorization in the prompt
- Rate-limited and batched for cost efficiency
"""

import os
import json
import time
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Skill categories for LLM guidance
SKILL_CATEGORIES = {
    "Programming Language": "Languages used to write code (Python, Java, Rust, etc.)",
    "Database": "Database systems and query languages (PostgreSQL, MongoDB, Redis, etc.)",
    "Cloud Platform": "Cloud providers and their services (AWS, GCP, Azure services)",
    "Big Data": "Distributed data processing tools (Spark, Kafka, Hadoop, etc.)",
    "Data Engineering": "Data pipeline and transformation tools (Airflow, dbt, Fivetran, etc.)",
    "Machine Learning": "ML frameworks and libraries (TensorFlow, PyTorch, scikit-learn, etc.)",
    "DevOps": "CI/CD, containers, and infrastructure tools (Docker, Kubernetes, Terraform, etc.)",
    "Web Framework": "Backend and frontend frameworks (React, Django, FastAPI, etc.)",
    "Data Visualization": "Charting and BI tools (Tableau, Power BI, Matplotlib, etc.)",
    "Version Control": "Source control systems (Git, GitHub, GitLab, etc.)",
    "API & Integration": "API technologies and protocols (REST, GraphQL, gRPC, etc.)",
    "Testing": "Testing frameworks and methodologies (pytest, Jest, Selenium, etc.)",
    "Security": "Security tools and practices (OAuth, encryption, penetration testing, etc.)",
    "Operating System": "OS and system administration (Linux, Windows Server, etc.)",
    "Methodology": "Development methodologies and practices (Agile, Scrum, TDD, etc.)",
    "Soft Skill": "Non-technical professional skills (communication, leadership, etc.)",
    "Other": "Skills that don't fit other categories"
}

# Prompt template for skill extraction
EXTRACTION_PROMPT = """You are a technical recruiter AI that extracts skills from job descriptions.

TASK: Extract ALL technical skills, tools, frameworks, platforms, and methodologies mentioned in this job description.

RULES:
1. Be SPECIFIC - extract "Apache Kafka" not just "streaming", "PostgreSQL" not just "database"
2. Include version-agnostic names (e.g., "Python" not "Python 3.9")
3. Extract both explicit mentions AND implied skills (e.g., "ETL pipelines" implies data engineering skills)
4. Categorize each skill appropriately
5. Do NOT include generic terms like "software", "technology", "data", "systems"
6. Do NOT include job titles or roles
7. Extract emerging/newer tools even if uncommon (Polars, DuckDB, Qdrant, etc.)

SKILL CATEGORIES:
{categories}

JOB DESCRIPTION:
---
{job_description}
---

Respond with ONLY a JSON array of objects. Each object must have:
- "skill_name": The canonical/official name of the skill (string)
- "category": One of the categories listed above (string)
- "subcategory": More specific classification if applicable (string, can be empty)
- "confidence": Your confidence 0.0-1.0 that this is a real skill mention (float)

Example response format:
[
  {{"skill_name": "Apache Kafka", "category": "Big Data", "subcategory": "Streaming", "confidence": 0.95}},
  {{"skill_name": "Python", "category": "Programming Language", "subcategory": "General Purpose", "confidence": 1.0}}
]

JSON Response:"""


@dataclass
class SlowPathConfig:
    """Configuration for the slow path extractor."""
    api_key: str
    model: str = "gemini-2.0-flash"  # Fast and cheap
    max_tokens: int = 2048
    temperature: float = 0.1  # Low for consistency
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    min_confidence: float = 0.7  # Filter out low-confidence extractions


class SlowPathExtractor:
    """
    LLM-based skill extraction using Google Gemini.
    
    Features:
    - Structured JSON output parsing
    - Automatic retry with exponential backoff
    - Confidence filtering
    - Rate limiting support
    """
    
    def __init__(self, config: Optional[SlowPathConfig] = None, api_key: Optional[str] = None):
        """
        Initialize the Gemini-based extractor.
        
        Args:
            config: Full configuration object
            api_key: Just the API key (uses defaults for other settings)
        """
        if config:
            self.config = config
        else:
            key = api_key or os.getenv("GEMINI_API_KEY")
            if not key:
                logger.warning("SlowPath: No GEMINI_API_KEY found. LLM extraction disabled.")
                self.config = None
            else:
                self.config = SlowPathConfig(api_key=key)
        
        self._client = None
        self._last_request_time = 0
        self._min_request_interval = 0.1  # 100ms between requests (10 RPS)
    
    def _get_client(self):
        """Lazy initialization of Gemini client."""
        if self._client is None and self.config:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.config.api_key)
                self._client = genai.GenerativeModel(self.config.model)
                logger.info(f"SlowPath: Initialized Gemini client with model {self.config.model}")
            except ImportError:
                logger.error("SlowPath: google-generativeai package not installed")
                raise
        return self._client
    
    def _rate_limit(self):
        """Simple rate limiting to avoid API throttling."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()
    
    def _build_prompt(self, job_description: str) -> str:
        """Build the extraction prompt with categories."""
        categories_str = "\n".join(f"- {k}: {v}" for k, v in SKILL_CATEGORIES.items())
        return EXTRACTION_PROMPT.format(
            categories=categories_str,
            job_description=job_description[:8000]  # Truncate very long descriptions
        )
    
    def _parse_response(self, response_text: str) -> List[Dict]:
        """Parse and validate the JSON response from Gemini."""
        # Clean up response - sometimes LLMs add markdown code blocks
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        try:
            skills = json.loads(text)
            if not isinstance(skills, list):
                logger.warning("SlowPath: Response is not a list")
                return []
            
            # Validate and filter each skill
            valid_skills = []
            for skill in skills:
                if not isinstance(skill, dict):
                    continue
                if 'skill_name' not in skill:
                    continue
                
                # Normalize the skill entry
                valid_skill = {
                    'skill_name': str(skill.get('skill_name', '')).strip(),
                    'category': str(skill.get('category', 'Other')).strip(),
                    'subcategory': str(skill.get('subcategory', '')).strip(),
                    'confidence': float(skill.get('confidence', 0.8)),
                    'extraction_method': 'slow_path'
                }
                
                # Filter by confidence threshold
                if valid_skill['confidence'] >= self.config.min_confidence:
                    # Skip empty or too-short skill names
                    if len(valid_skill['skill_name']) >= 2:
                        valid_skills.append(valid_skill)
            
            return valid_skills
            
        except json.JSONDecodeError as e:
            logger.warning(f"SlowPath: Failed to parse JSON response: {e}")
            return []
    
    def extract_skills(self, text: str) -> List[Dict]:
        """
        Extract skills from text using Gemini LLM.
        
        Args:
            text: Job description to analyze
        
        Returns:
            List of skill dicts with name, category, subcategory, confidence
        """
        if not self.config:
            logger.debug("SlowPath: Disabled (no API key)")
            return []
        
        if not text or len(text.strip()) < 50:
            logger.debug("SlowPath: Text too short for analysis")
            return []
        
        client = self._get_client()
        if not client:
            return []
        
        prompt = self._build_prompt(text)
        
        for attempt in range(self.config.max_retries):
            try:
                self._rate_limit()
                
                response = client.generate_content(
                    prompt,
                    generation_config={
                        'temperature': self.config.temperature,
                        'max_output_tokens': self.config.max_tokens,
                    }
                )
                
                if response.text:
                    skills = self._parse_response(response.text)
                    logger.debug(f"SlowPath: Extracted {len(skills)} skills")
                    return skills
                else:
                    logger.warning("SlowPath: Empty response from Gemini")
                    
            except Exception as e:
                logger.warning(f"SlowPath: Attempt {attempt + 1} failed: {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (2 ** attempt))
                continue
        
        logger.error("SlowPath: All retry attempts exhausted")
        return []
    
    def extract_skills_batch(self, texts: List[str], batch_size: int = 5) -> List[List[Dict]]:
        """
        Extract skills from multiple texts.
        Processes sequentially with rate limiting.
        
        Args:
            texts: List of job descriptions
            batch_size: Unused (kept for API compatibility)
        
        Returns:
            List of skill lists, one per input text
        """
        results = []
        for i, text in enumerate(texts):
            skills = self.extract_skills(text)
            results.append(skills)
            
            if (i + 1) % 10 == 0:
                logger.info(f"SlowPath: Processed {i + 1}/{len(texts)} descriptions")
        
        return results
    
    def is_available(self) -> bool:
        """Check if the slow path extractor is configured and ready."""
        return self.config is not None
