import json
import sys
from pathlib import Path

from app.routers.resume import ResumeSkillExtractor

ETL = Path(__file__).resolve().parents[2] / "etl"
sys.path.insert(0, str(ETL))
from skill_extractor.fast_path import FastPathExtractor  # noqa: E402

SKILLS = {"skills": [
    {"name": "Go", "aliases": ["golang"], "case_sensitive": ["Go"],
     "not_followed_by": r"[\s\-]+(?:to|further)\b", "category": "Programming Language"},
    {"name": "Apache Spark", "aliases": ["spark"], "case_sensitive": ["Spark"], "category": "Big Data"},
]}
TEXT = "We go further. Go to market. Python, Go, golang and Spark; sparks fly."


def names(results):
    return {r["skill_name"]: r["mention_count"] for r in results}


def test_backend_and_etl_extract_identically(tmp_path):
    path = tmp_path / "tax.json"
    path.write_text(json.dumps(SKILLS))
    backend = names(ResumeSkillExtractor(path).extract_skills(TEXT))
    etl = names(FastPathExtractor(taxonomy_path=path).extract_skills(TEXT))
    assert backend == etl == {"Go": 2, "Apache Spark": 1}
