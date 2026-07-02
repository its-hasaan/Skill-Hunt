"""
One-time (re-runnable) conservative cleanup of skills_taxonomy.json.

What it does:
  1) Removes high-confidence NON-SKILLS (company names, foreign/garbled tokens,
     generic phrases) — explicit lists, no fuzzy regex.
  2) Merges obvious duplicates/variants into a canonical skill (folding the
     variants in as aliases so future extraction still catches them).
  3) Adds a `type` (skill_type) to every remaining skill:
     Language | Framework/Library | Tool/Platform | Cloud/Infra | Database |
     Concept/Domain | Soft Skill | Human Language

Safe: backs up the original to skills_taxonomy.backup.json and writes a
human-readable changelog. Re-running is idempotent.

Usage:  python etl/tools/clean_taxonomy.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # etl/
TAX = ROOT / "config" / "skills_taxonomy.json"
BACKUP = ROOT / "config" / "skills_taxonomy.backup.json"
CHANGELOG = ROOT / "config" / "taxonomy_cleanup_changelog.md"


# --------------------------------------------------------------------------
# 1) REMOVE — high-confidence non-skills (companies, garbled, generic phrases)
# --------------------------------------------------------------------------
REMOVE = {
    # Companies / entities (not skills)
    "Adyen", "Airservices Australia", "Airwallex", "Amazon", "Amazon Music",
    "Amazon Prime Air", "Cloudflight", "Culture Amp", "DEUNA", "DeepL",
    "DiDi Global Inc.", "Epistemix", "Fiserv", "Flowserve", "Google Cl",
    "HUB International Canada", "IQVIA", "Kavak", "Klaxoon", "Leidos",
    "MetBrains", "Meta", "Mindrift", "Paysafe", "Procurify", "Quiet-Oceans",
    "Replica", "Servinformacion", "Servinformaci�n", "Swap", "Toutiao",
    "TripleTen", "Tucows", "UPS", "Xero", "Boam AI", "AgentForce", "CDAI",
    # Foreign-language / encoding-broken
    "Ciberseguran�a", "Ingl�s",
    # Generic phrases (not concrete skills)
    "AI-native services", "AWS Professional Services", "AWS services",
    "Analytics Platform", "B2B SaaS", "CDA platform", "Community Services Cluster",
    "Data & AI Platform", "Digital Experience Platform", "Fan Experience Platform",
    "MCP services", "Managed Services", "Modern Data Platform", "Network as a Service",
    "OmniPoint SaaS platform", "Professional Services", "Public Cloud Platform",
    "SaaS environment", "SaaS platform", "SAP Business Technology Platform",
    "Trust Data Platform", "cloud architecture", "cloud environments",
    "cloud services", "cloud solutions", "cloud-native architectures",
    "cloud-native services", "core platform", "data platform",
    "digital transformation services", "enterprise data platforms",
    "event-driven platform", "event-driven services", "global digital asset platform",
    "governance and assurance services", "high-performance platform",
    "hybrid cloud platforms", "infrastructure and operational services",
    "intelligent integration and automation platform", "multi-product platform",
    "payments platform", "public cloud", "single-page admin platform",
    "Web Services", "Search API", "dashboards", "After Effects",
    "Workflow Data Fabric", "Data Analysis & Decision Support Frame",
    "ML Frameworks", "machine learning frameworks", "RAG frameworks",
    "Microsoft Security", "Construction Cloud", "Service Cloud",
    "Oracle EPM Cloud", "SAP Commerce Cloud",
    # Garbled / broken tokens
    "BashOperating system", "Betriebssysteme", "LinuxAbout", "LinuxO",
    "WindowsAbout", "GitOptional", "Lattice OS", "PC", "OS", "Operating system",
    "operating systems", "CloudFormation Automate", "DevOps Toolchains",
    # Job titles / ambiguous acronyms
    "CISO", "SAM",
}


# --------------------------------------------------------------------------
# 2) MERGE — canonical name -> variants folded in as aliases (then removed)
# --------------------------------------------------------------------------
MERGE = {
    "Generative AI": ["Gen AI", "GenAI", "GenAI platform"],
    "Amazon Web Services": ["Amazon Web Service", "AWS Cloud", "AWS"],
    "Microsoft Azure": ["Azure Cloud platform", "Azure Platform",
                         "Microsoft Azure platform", "Microsoft Cloud", "Azure"],
    "Google Cloud": ["GCP", "Google Cloud Platform"],
    "Oracle Cloud Infrastructure": ["OCI", "Oracle cloud"],
    "Microsoft Power Platform": ["Power Platform", "MS Power Platform"],
    "Microsoft Fabric": ["Microsoft Fabric platform"],
    "REST": ["REST APIs", "RESTful APIs", "RESTful services", "API REST",
             "web APIs", "backend APIs", "communication APIs"],
    "API Integration": ["API integration", "API integrations"],
    "NLP": ["Natural Language Processing"],
    "RAG": ["RAG frameworks"],
    "Android": ["Android 12"],
    "OAuth": ["OAuth2"],
    "Linux": ["Linux systems", "Linux-based"],
}

# Rename a single entry (source has no canonical to merge into)
RENAME = {
    "Databricks platform": "Databricks",
    "Storybooks": "Storybook",
}


# --------------------------------------------------------------------------
# 3) TYPE assignment
# --------------------------------------------------------------------------
CATEGORY_TYPE = {
    "Programming Language": "Language",
    "Database": "Database",
    "Cloud Platform": "Cloud/Infra",
    "Cloud": "Cloud/Infra",
    "DevOps": "Tool/Platform",
    "Data Engineering": "Tool/Platform",
    "Big Data": "Tool/Platform",
    "Operating System": "Tool/Platform",
    "Version Control": "Tool/Platform",
    "Productivity": "Tool/Platform",
    "Data Warehouse": "Tool/Platform",
    "Data Platform": "Tool/Platform",
    "BI/Visualization": "Tool/Platform",
    "Data Visualization": "Tool/Platform",
    "Web Framework": "Framework/Library",
    "Frontend": "Framework/Library",
    "Backend": "Framework/Library",
    "Testing": "Framework/Library",
    "Mobile": "Framework/Library",
    "Machine Learning": "Concept/Domain",
    "Data Science": "Framework/Library",
    "API & Integration": "Concept/Domain",
    "Security": "Concept/Domain",
    "Architecture": "Concept/Domain",
    "Methodology": "Concept/Domain",
    "Soft Skills": "Soft Skill",
}

TYPE_OVERRIDES = {
    # ML libraries/frameworks
    "PyTorch": "Framework/Library", "TensorFlow": "Framework/Library",
    "Keras": "Framework/Library", "Scikit-learn": "Framework/Library",
    "XGBoost": "Framework/Library", "LightGBM": "Framework/Library",
    "Statsmodels": "Framework/Library", "LangChain": "Framework/Library",
    "langgraph": "Framework/Library", "Hugging Face": "Framework/Library",
    "transformers": "Framework/Library", "vLLM": "Framework/Library",
    "OpenCV": "Framework/Library", "MLflow": "Tool/Platform",
    "Kubeflow": "Tool/Platform", "CUDA": "Framework/Library",
    "CUDNN": "Framework/Library", "CUDA kernels": "Framework/Library",
    "PydanticAI": "Framework/Library", "YOLO": "Framework/Library",
    # ML concepts
    "LLM": "Concept/Domain", "NLP": "Concept/Domain", "Computer Vision": "Concept/Domain",
    "Deep Learning": "Concept/Domain", "Machine Learning": "Concept/Domain",
    "RAG": "Concept/Domain", "Generative AI": "Concept/Domain", "CNNs": "Concept/Domain",
    "Agentic AI": "Concept/Domain",
    # ML models / hosted services
    "OpenAI": "Tool/Platform", "Claude": "Tool/Platform", "Gemini": "Tool/Platform",
    "GPT": "Tool/Platform", "LLaMA": "Tool/Platform", "Confluent": "Tool/Platform",
    # Data science
    "Statistics": "Concept/Domain", "A/B Testing": "Concept/Domain",
    "Jupyter": "Tool/Platform",
    # Frontend languages
    "HTML": "Language", "CSS": "Language",
    # Security tools vs concepts
    "CrowdStrike": "Tool/Platform", "Keycloak": "Tool/Platform",
    "Proofpoint": "Tool/Platform", "SIEM": "Tool/Platform", "Firewall": "Tool/Platform",
    "firewalls": "Tool/Platform", "VPN": "Tool/Platform", "WAF": "Tool/Platform",
    "Security Groups": "Tool/Platform",
    # API tooling
    "OpenAPI": "Tool/Platform", "Swagger": "Tool/Platform",
    # Data-eng concepts
    "ETL": "Concept/Domain", "Data Modeling": "Concept/Domain",
    "Data Governance": "Concept/Domain",
    # Human languages
    "English": "Human Language",
    "German": "Human Language", "Spanish": "Human Language", "French": "Human Language",
}


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def main():
    data = json.loads(TAX.read_text(encoding="utf-8"))
    skills = data["skills"]

    # Backup once (don't overwrite an existing backup)
    if not BACKUP.exists():
        BACKUP.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Reverse merge lookup: variant name -> canonical
    variant_to_canon = {}
    for canon, variants in MERGE.items():
        for v in variants:
            variant_to_canon[v] = canon

    by_name = {}          # canonical/kept name -> entry
    removed, merged, renamed, deduped = [], [], [], []

    for s in skills:
        name = s["name"]

        # explicit list OR any non-ASCII/encoding-broken token (all such names
        # in this taxonomy are junk, e.g. "Ingl?s", "Ciberseguran?a")
        if name in REMOVE or any(ord(c) > 127 for c in name):
            removed.append(name)
            continue

        if name in RENAME:
            renamed.append((name, RENAME[name]))
            s = {**s, "name": RENAME[name]}
            name = s["name"]

        # Merge variant into canonical (fold as alias)
        if name in variant_to_canon:
            canon = variant_to_canon[name]
            merged.append((name, canon))
            tgt = by_name.get(canon)
            if tgt is None:
                # canonical not seen yet: stash aliases to attach later
                pending = by_name.setdefault("__pending__" + canon, {"aliases": []})
                pending["aliases"].append(name.lower())
                pending["aliases"] += [a.lower() for a in s.get("aliases", [])]
            else:
                al = set(tgt.get("aliases", []))
                al.add(name.lower())
                al.update(a.lower() for a in s.get("aliases", []))
                tgt["aliases"] = sorted(al)
            continue

        # Exact duplicate name already kept -> merge aliases
        if name in by_name:
            deduped.append(name)
            tgt = by_name[name]
            al = set(tgt.get("aliases", [])) | set(s.get("aliases", []))
            tgt["aliases"] = sorted(al)
            continue

        by_name[name] = s

    # Attach any aliases that were pending before their canonical appeared
    for key in [k for k in by_name if k.startswith("__pending__")]:
        canon = key[len("__pending__"):]
        pend = by_name.pop(key)
        if canon in by_name:
            al = set(by_name[canon].get("aliases", [])) | set(pend["aliases"])
            by_name[canon]["aliases"] = sorted(al)

    # Assign skill_type
    retype_counts = {}
    for name, s in by_name.items():
        stype = TYPE_OVERRIDES.get(name) or CATEGORY_TYPE.get(s.get("category"), "Concept/Domain")
        s["type"] = stype
        retype_counts[stype] = retype_counts.get(stype, 0) + 1

    cleaned = list(by_name.values())
    cleaned.sort(key=lambda x: (x.get("type", ""), x["name"].lower()))
    data["skills"] = cleaned
    TAX.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Changelog
    lines = ["# Taxonomy Cleanup Changelog", ""]
    lines.append(f"- Before: {len(skills)} skills")
    lines.append(f"- After:  {len(cleaned)} skills")
    lines.append(f"- Removed: {len(removed)} | Merged: {len(merged)} | Renamed: {len(renamed)} | Exact-deduped: {len(deduped)}")
    lines.append("")
    lines.append("## skill_type distribution")
    for t, n in sorted(retype_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- {t}: {n}")
    lines.append("")
    lines.append("## Removed (non-skills)")
    lines += [f"- {n}" for n in sorted(removed)]
    lines.append("")
    lines.append("## Merged into canonical")
    lines += [f"- {v}  ->  {c}" for v, c in sorted(merged)]
    if renamed:
        lines.append("")
        lines.append("## Renamed")
        lines += [f"- {a}  ->  {b}" for a, b in sorted(renamed)]
    if deduped:
        lines.append("")
        lines.append("## Exact duplicates removed")
        lines += [f"- {n}" for n in sorted(set(deduped))]
    CHANGELOG.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Before {len(skills)} -> After {len(cleaned)}")
    print(f"Removed {len(removed)}, merged {len(merged)}, renamed {len(renamed)}, deduped {len(deduped)}")
    print("Types:", retype_counts)
    print(f"Backup: {BACKUP.name}  Changelog: {CHANGELOG.name}")


if __name__ == "__main__":
    main()
