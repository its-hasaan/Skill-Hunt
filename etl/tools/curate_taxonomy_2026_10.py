"""
One-off taxonomy curation (October 2026, Phase 1a).

Why: 325 of 487 skills had been auto-promoted by GLiNER discovery — company
names (adjoe, Genpact, Spotify...), generic phrases ("cloud platform"),
and duplicates of curated skills that double-counted demand (EC2 next to
"AWS EC2"). Several curated aliases were ordinary English words ("next",
"express", "image", "less") and inflated demand for Next.js, Express.js,
Computer Vision and CSS. This script applies explicit, reviewable decisions
and adds the skills the five new roles need.

Order: remove -> rename -> add new -> merge -> recategorise -> alias fixes
-> matching rules -> tidy. Idempotent: re-running on the curated file
changes nothing. Quality is guarded afterwards by etl/tests/test_taxonomy.py.

    python etl/tools/curate_taxonomy_2026_10.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clean_taxonomy import CATEGORY_TYPE, TYPE_OVERRIDES  # noqa: E402

TAX = Path(__file__).resolve().parents[1] / "config" / "skills_taxonomy.json"
META_KEYS = ("_discovered", "_first_seen", "_occurrence_count")

REMOVE = {
    # companies / employers / products that are not skills
    "adjoe", "ADP", "airSlate", "Atolls", "Backbase", "BEKO", "Brighte", "Cloud Imperium Games",
    "CONXAI", "Deel", "DKV Mobility", "Doctrine", "Dropbox", "Equinix", "Fresha", "Genpact",
    "Gorgias", "Gynzy", "HUB24", "ICE Data Services", "Improvado", "Lantern", "LetsGrow.com",
    "Luxury Presence", "Marina Bay Sands", "Meta Platforms, Inc.", "Mirakl Nexus", "Mirakl Platform",
    "OVHcloud", "Prudential", "QEMI", "Rakuten Symphony", "Rakuten Viki", "Reaxys", "Samsara",
    "Service NSW", "Service Stream", "Sia", "Spotify", "SSP", "Standard Chartered nexus", "Stripe",
    "The Key to Life", "Veem", "WPP Open", "KnowBe4", "Machine Learning Maestro", "Materia AI",
    "Secure Code Warrior", "Sensorfact", "ATHIA", "High Touch", "Human OS", "Perplexity",
    "CKEditor", "Proofpoint", "Eucalyptus", "CGI", "jasmine", "karma",
    # generic phrases
    "Azure Services", "big data platform", "Cloud DX", "cloud platform", "cloud platforms",
    "cloud-based services", "cloud-native platform", "Container platform", "Customer 360 platforms",
    "Customer Data Platform", "Digital Identity Services", "enterprise data platform",
    "enterprise-grade platforms", "financial intelligence platform", "fintech platform",
    "Global Business Services", "Global Data Platform", "global investment platform",
    "global platform", "modern cloud platform", "multi-cloud platform",
    "next-generation AI infrastructure platform",
    "next-generation ecommerce search and discovery platform", "Next-generation Managed Services",
    "Research and Data Platform", "shared services", "agentic frameworks", "AI Engines", "AI Studio",
    "analytical frameworks", "Architectures multi-agents", "Custom API", "Deep Learning algorithms",
    "high-performance APIs", "ML frameworks", "trading systems", "unified API",
    "user access controls", "20tb databases", "database schemas", "La risorsa", "Storage",
    "warehouse", "team backend", "industry aligned programming languages", "programming languages",
    "Java-based", "Python-based", "Pythonie", "Kotlin/Java", "containerisation", "containerization",
    "container orchestration", "data visualization tools", "Investment Data Engineering",
    "model versioning", "monitoring systems", "orchestration frameworks", "orchestrazione agentica",
    "performance monitoring", "proactive monitoring", "production monitoring", "real-time monitoring",
    "Transaction Monitoring", "meccanismi di sicurezza", "NATO SECRET", "version control",
    "versioning", "Security Groups", "SMS", "Vertex", "relational databases", "SQL databases",
    "data security", "Data Analytics", "CTR", "CVR", "RoAS", "OData services", "Secure SD-WAN",
    # human languages are not tech skills
    "English", "French", "German", "deutsch", "eng", "Englisch", "Ingles",
}

# old name -> new name (the old name is kept as an alias)
RENAME = {
    "API Gateway": "AWS API Gateway", "CloudFront": "AWS CloudFront",
    "Cloud Functions": "Google Cloud Functions", "App Service": "Azure App Service",
    "Cosmos DB": "Azure Cosmos DB", "ECS": "AWS ECS", "SQS": "AWS SQS", "KMS": "AWS KMS",
    "MQ": "IBM MQ", "Sentinel": "Microsoft Sentinel",
    "MDM": "Master Data Management", "langgraph": "LangGraph", "crewai": "CrewAI",
    "JetPack Compose": "Jetpack Compose", "LLaMA": "Llama",
    "Model Context Pro": "Model Context Protocol", "Monte Carlo": "Monte Carlo Methods",
    "SPRING BATCH": "Spring Batch", "data lake": "Data Lake",
    "application security": "Application Security", "network security": "Network Security",
    "Oracle Cloud Infrastructure": "Oracle Cloud",
}

TOOL = "Tool/Platform"
CONCEPT = "Concept/Domain"
NEW = [
    # merge targets that may not exist yet
    ("AI Agents", "Machine Learning", ["ai agents", "agentic ai"], CONCEPT),
    ("Java EE", "Web Framework", ["jakarta ee"], "Framework/Library"),
    ("Data Warehouse", "Data Warehouse", ["data warehousing"], CONCEPT),
    ("Recommender Systems", "Machine Learning", ["recommendation engine", "recommendation engines"], CONCEPT),
    ("AWS", "Cloud Platform", ["amazon web services"], "Cloud/Infra"),
    ("Azure", "Cloud Platform", ["microsoft azure"], "Cloud/Infra"),
    ("Google Cloud", "Cloud Platform", ["gcp", "google cloud platform"], "Cloud/Infra"),
    # UI/UX Designer
    ("Figma", "Design", [], TOOL), ("Sketch", "Design", [], TOOL), ("Adobe XD", "Design", [], TOOL),
    ("Adobe Photoshop", "Design", ["photoshop"], TOOL),
    ("Adobe Illustrator", "Design", ["illustrator"], TOOL),
    ("InVision", "Design", [], TOOL), ("Framer", "Design", [], TOOL), ("Zeplin", "Design", [], TOOL),
    ("Balsamiq", "Design", [], TOOL), ("Miro", "Design", [], TOOL),
    ("Prototyping", "Design", ["prototypes"], CONCEPT),
    ("Wireframing", "Design", ["wireframes", "wireframe"], CONCEPT),
    ("User Research", "Design", ["ux research"], CONCEPT),
    ("Usability Testing", "Design", ["usability tests"], CONCEPT),
    ("Design Systems", "Design", ["design system"], CONCEPT),
    ("Interaction Design", "Design", [], CONCEPT), ("Visual Design", "Design", [], CONCEPT),
    ("UX Writing", "Design", [], CONCEPT), ("Information Architecture", "Design", [], CONCEPT),
    ("Accessibility", "Design", ["wcag", "a11y"], CONCEPT),
    # Product Manager
    ("Product Roadmap", "Product Management", ["roadmapping", "product roadmaps"], CONCEPT),
    ("Product Strategy", "Product Management", [], CONCEPT),
    ("Product Discovery", "Product Management", [], CONCEPT),
    ("PRD", "Product Management", ["product requirements document"], CONCEPT),
    ("User Stories", "Product Management", ["user story"], CONCEPT),
    ("OKRs", "Product Management", ["okr"], CONCEPT),
    ("Stakeholder Management", "Product Management", [], CONCEPT),
    ("Market Research", "Product Management", [], CONCEPT),
    ("Product Analytics", "Product Management", [], CONCEPT),
    ("Amplitude", "Product Management", [], TOOL), ("Mixpanel", "Product Management", [], TOOL),
    ("Google Analytics", "Product Management", ["ga4"], TOOL),
    ("Hotjar", "Product Management", [], TOOL), ("Productboard", "Product Management", [], TOOL),
    ("Pendo", "Product Management", [], TOOL),
    ("Go-to-Market", "Product Management", ["gtm strategy"], CONCEPT),
    # QA Engineer
    ("Cypress", "Testing", [], "Framework/Library"), ("Playwright", "Testing", [], "Framework/Library"),
    ("Appium", "Testing", [], "Framework/Library"), ("TestNG", "Testing", [], "Framework/Library"),
    ("JUnit", "Testing", [], "Framework/Library"), ("pytest", "Testing", [], "Framework/Library"),
    ("Postman", "Testing", [], TOOL), ("JMeter", "Testing", [], TOOL), ("LoadRunner", "Testing", [], TOOL),
    ("Cucumber", "Testing", [], "Framework/Library"),
    ("BDD", "Testing", ["behavior-driven development", "behaviour-driven development"], CONCEPT),
    ("TDD", "Testing", ["test-driven development"], CONCEPT),
    ("Test Automation", "Testing", ["automated testing", "automation testing"], CONCEPT),
    ("Manual Testing", "Testing", [], CONCEPT), ("Regression Testing", "Testing", [], CONCEPT),
    ("API Testing", "Testing", [], CONCEPT),
    ("Performance Testing", "Testing", ["load testing"], CONCEPT),
    ("TestRail", "Testing", [], TOOL), ("Katalon", "Testing", [], TOOL),
    ("Robot Framework", "Testing", [], "Framework/Library"),
    ("WebdriverIO", "Testing", [], "Framework/Library"), ("Mocha", "Testing", [], "Framework/Library"),
    # Technical Support Engineer
    ("Zendesk", "Customer Support", [], TOOL), ("Freshdesk", "Customer Support", [], TOOL),
    ("Intercom", "Customer Support", [], TOOL),
    ("Jira Service Management", "Customer Support", [], TOOL),
    ("ITIL", "Customer Support", [], CONCEPT), ("Active Directory", "Customer Support", [], TOOL),
    ("Help Desk", "Customer Support", ["helpdesk", "service desk"], CONCEPT),
    ("Troubleshooting", "Customer Support", [], CONCEPT),
    ("Ticketing Systems", "Customer Support", ["ticketing system"], CONCEPT),
    ("Customer Success", "Customer Support", [], CONCEPT),
    ("HubSpot", "Customer Support", [], TOOL), ("Gainsight", "Customer Support", [], TOOL),
    ("Customer Onboarding", "Customer Support", [], CONCEPT),
    ("Remote Desktop", "Customer Support", ["rdp"], TOOL),
    ("DNS", "Customer Support", [], CONCEPT), ("TCP/IP", "Customer Support", [], CONCEPT),
    ("SLA Management", "Customer Support", ["sla"], CONCEPT),
]

# variant -> canonical (variant name + aliases fold into the canonical)
MERGE = {
    "EC2": "AWS EC2", "EKS": "Kubernetes", "Lambda": "AWS Lambda", "RDS": "AWS RDS", "S3": "AWS S3",
    "Redshift": "AWS Redshift", "DynamoDB": "AWS DynamoDB", "Data Factory": "Azure Data Factory",
    "Azure Machine Learning": "Azure ML", "Google BigQuery": "BigQuery", "Dataflow": "Google Dataflow",
    "dbt Cloud": "dbt", "Airflow": "Apache Airflow", "Spark": "Apache Spark",
    "PySpark": "Apache Spark", "Confluent": "Apache Kafka",
    "MariaDB": "MySQL", "MS SQL Server": "Microsoft SQL Server", "MSSQL": "Microsoft SQL Server",
    "SQL Server": "Microsoft SQL Server", "Oracle": "Oracle Database", "Postgres": "PostgreSQL",
    "T-SQL": "SQL", "vector databases": "Vector Database",
    "data lakes": "Data Lake", "Data Warehouses": "Data Warehouse",
    "datawarehouses": "Data Warehouse", "enterprise data warehouse": "Data Warehouse",
    "CSS3": "CSS", "HTML5": "HTML", "ES6": "JavaScript", "Golang": "Go", "AngularJS": "Angular",
    "Core Java": "Java", "Node": "Node.js", "NodeJS": "Node.js", "vuejs": "Vue.js",
    "React 18": "React", "React JS": "React", "React.js": "React", "SwiftUI": "Swift",
    "TS": "TypeScript", "Shell": "Bash", "PHP-developer": "PHP", "C# .Net": "C#", "C#.Net": "C#",
    ".NET Core": ".NET", ".NET 8": ".NET",
    "CNNs": "Deep Learning", "LSTM": "Deep Learning", "Keras": "TensorFlow",
    "transformers": "Hugging Face", "Large Language Model": "LLM", "GPT": "OpenAI",
    "CUDNN": "CUDA", "CUDA kernels": "CUDA", "J2EE": "Java EE", "JEE": "Java EE",
    "BitBucket": "Git", "Github": "Git", "Gitlab": "Git", "CI/CD pipelines": "CI/CD",
    "firewalls": "Firewall", "DevSecOps Engineer": "DevSecOps", "Swagger": "OpenAPI",
    "API development": "REST API", "REST": "REST API",
    "Recommendation Systems": "Recommender Systems", "multi-agent systems": "AI Agents",
    "agent orchestration": "AI Agents", "Agentic AI": "AI Agents",
    "Salesforce Data Cloud": "Salesforce", "Salesforce Platform": "Salesforce",
    "Force.com platform": "Salesforce", "ServiceNow-based": "ServiceNow",
    "VMware Cloud Foundation": "VMware", "RHEL": "Linux", "Ubuntu": "Linux",
}

CATEGORY = {
    **{n: "API & Integration" for n in ("JSON", "XML", "SOAP", "OAuth", "SAML", "OpenAPI")},
    **{n: "Testing" for n in ("Selenium", "Jest")},
    **{n: "Productivity" for n in ("Microsoft 365", "Microsoft Power Platform")},
    "Microsoft Fabric": "Data Platform", "Salesforce": "Business Applications",
    "ServiceNow": "Business Applications", "Vercel": "DevOps", "VMware": "Cloud Platform",
    "OpenStack": "Cloud Platform", "Oracle Cloud": "Cloud Platform",
    **{n: "Cloud" for n in ("AWS API Gateway", "AWS CloudFront", "Google Cloud Functions",
                           "Azure App Service", "AWS ECS", "AWS SQS")},
    "Azure Cosmos DB": "Database", "AWS KMS": "Security", "Microsoft Sentinel": "Security",
    "SAP BusinessObjects": "BI/Visualization", "Jetpack Compose": "Mobile", "AOSP": "Mobile",
    "Storybook": "Frontend", "tidyr": "Data Science", "Statsmodels": "Data Science",
    "CrewAI": "Machine Learning", "Data Vault": "Data Engineering", "Data Lake": "Data Engineering",
    "Monte Carlo Methods": "Data Science", "Master Data Management": "Data Engineering",
    "Application Security": "Security", "Network Security": "Security", "Cybersecurity": "Security",
}

ALIAS_REMOVALS = {
    "Next.js": ["next"], "Express.js": ["express"], "Computer Vision": ["image"],
    "Great Expectations": ["ge"], "CSS": ["less"], "Elasticsearch": ["elastic"], "Plotly": ["dash"],
    "Vertex AI": ["vertex"], "TensorFlow": ["tf"], "Pandas": ["pd"], "Deep Learning": ["dl"],
    "Bash": ["shell"], "Flutter": ["dart"], "C#": ["dotnet", ".net"], "React": ["react native"],
    "SQL": ["sql server"], "Git": ["version control"], "IBM MQ": ["mq"],
    "Microsoft Sentinel": ["sentinel"], "Master Data Management": ["mdm"],
    "Model Context Protocol": ["model context pro"],
    # each term has exactly one owner (tests/test_taxonomy.py)
    "Azure Blob Storage": ["data lake"], "Azure Databricks": ["databricks"],
    "SQL": ["sql server", "pl/sql"], "Excel": ["vba"],
}

ALIAS_ADDITIONS = {
    ".NET": ["dotnet"], "IBM MQ": ["websphere mq", "mqseries"],
    "Microsoft Sentinel": ["azure sentinel"], "Monte Carlo Methods": ["monte carlo simulation"],
    "Model Context Protocol": ["mcp server", "mcp servers"],
}

GO_NOT_FOLLOWED = (r"[\s\-]+(?:to|live|further|beyond|ahead|back|forward|above|through|out|green"
                   r"|big|home|get|global|deep|over|faster|far|wrong)\b")
RULES = {
    "Go": {"case_sensitive": ["Go"], "not_followed_by": GO_NOT_FOLLOWED},
    "R": {"case_sensitive": ["R"], "not_followed_by": r"\s*[&+']|\.\s?[A-Z]", "not_preceded_by": r"&\s*$"},
    "AWS Glue": {"case_sensitive": ["Glue"], "not_followed_by": r"\s+(?:code|logic|layer)\b"},
    # sentence-start "Excel at/in ..." is the verb, not the spreadsheet
    "Excel": {"case_sensitive": ["Excel"], "not_followed_by": r"\s+(?:at|in)\b"},
    **{skill: {"case_sensitive": [term]} for skill, term in [
        ("REST API", "REST"), ("Apache Spark", "Spark"), ("Swift", "Swift"), ("Rust", "Rust"),
        ("Dart", "Dart"), ("Spring Boot", "Spring"), ("Apache Airflow", "Airflow"),
        ("Superset", "Superset"), ("AWS Lambda", "Lambda"), ("Azure Synapse", "Synapse"),
        ("AWS Athena", "Athena"), ("Apache Hive", "Hive"), ("Prefect", "Prefect"), ("Luigi", "Luigi"),
        ("Presto", "Presto"), ("Stitch", "Stitch"), ("Puppet", "Puppet"), ("Windows", "Windows"),
        ("Node.js", "Node"), ("Claude", "Claude"), ("Gemini", "Gemini"), ("TypeScript", "TS"),
        ("SAS", "SAS"), ("SOAP", "SOAP"), ("WAF", "WAF"), ("AWS ECS", "ECS"), ("JMS", "JMS"),
        ("AWS KMS", "KMS"), ("EDR", "EDR"), ("SSO", "SSO"), ("React", "React"),
        ("Tableau", "Tableau"), ("Oracle Database", "Oracle"), ("RAG", "RAG"), ("PRD", "PRD"),
        ("SLA Management", "SLA"),
    ]},
}


def _fold(target: dict, variant: dict) -> None:
    aliases = set(target.get("aliases", []))
    aliases.add(variant["name"].lower())
    aliases.update(a.lower() for a in variant.get("aliases", []))
    target["aliases"] = sorted(aliases)


def curate(skills: list[dict]) -> list[dict]:
    by_name = {s["name"]: dict(s) for s in skills if s["name"] not in REMOVE}

    for old, new in RENAME.items():
        if old in by_name:
            entry = by_name.pop(old)
            entry["name"] = new
            entry["aliases"] = sorted(set(entry.get("aliases", [])) | {old.lower()})
            if new in by_name:
                _fold(by_name[new], entry)
            else:
                by_name[new] = entry

    for name, category, aliases, stype in NEW:
        entry = by_name.setdefault(name, {"name": name, "category": category,
                                          "subcategory": category.lower(), "aliases": []})
        entry["aliases"] = sorted(set(entry.get("aliases", [])) | set(aliases))
        entry["category"] = category
        entry["type"] = stype

    for variant, canon in MERGE.items():
        if variant in by_name and variant != canon:
            if canon not in by_name:
                raise KeyError(f"merge target missing: {canon} (for {variant})")
            _fold(by_name[canon], by_name.pop(variant))

    for name, category in CATEGORY.items():
        if name in by_name:
            by_name[name]["category"] = category
            by_name[name]["subcategory"] = category.lower()

    for name, drop in ALIAS_REMOVALS.items():
        if name in by_name:
            by_name[name]["aliases"] = [a for a in by_name[name].get("aliases", []) if a not in drop]
    for name, extra in ALIAS_ADDITIONS.items():
        if name in by_name:
            by_name[name]["aliases"] = sorted(set(by_name[name].get("aliases", [])) | set(extra))

    for name, rules in RULES.items():
        if name in by_name:
            by_name[name].update(rules)

    new_types = {n: t for n, _, _, t in NEW}
    for name, entry in by_name.items():
        for key in META_KEYS:
            entry.pop(key, None)
        own = name.lower()
        entry["aliases"] = sorted({a.lower() for a in entry.get("aliases", []) if a.lower() != own})
        entry["type"] = (new_types.get(name) or TYPE_OVERRIDES.get(name)
                         or CATEGORY_TYPE.get(entry.get("category"), CONCEPT))

    return sorted(by_name.values(), key=lambda s: (s.get("category", ""), s["name"].lower()))


def main() -> None:
    data = json.loads(TAX.read_text(encoding="utf-8"))
    before = len(data["skills"])
    data["skills"] = curate(data["skills"])
    TAX.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"skills: {before} -> {len(data['skills'])}")


if __name__ == "__main__":
    main()
