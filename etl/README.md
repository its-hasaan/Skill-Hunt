# ETL Pipeline

Data extraction and transformation scripts for Skill Hunt.

## Scripts

| Script | Purpose |
|--------|---------|
| `extractor.py` | Extracts job postings from Adzuna API |
| `transformer.py` | Extracts skills using **Hybrid Approach** (regex + LLM) |
| `check_progress.py` | Check transformation progress |
| `skill_extractor/` | Modular skill extraction package |

## Hybrid Skill Extraction Architecture

The transformer uses a two-path approach for optimal cost/coverage:

### Fast Path (Free, Instant)
- Regex-based matching against `skills_taxonomy.json`
- Handles ~95% of skill mentions (Python, SQL, AWS, etc.)
- Zero latency, zero cost

### Slow Path (LLM Discovery)
- Uses **Google Gemini Flash** for intelligent extraction
- Triggered when:
  - Fast path coverage is low (<30%)
  - Too few skills found (<3)
  - Random sampling (10% of jobs for discovery)
  - Explicit `--discovery-mode` flag
- Discovers emerging skills (Polars, Qdrant, etc.)
- Auto-promotes frequently-seen discoveries to taxonomy

### Skill Discovery Flow
```
Job Description
      ↓
┌─────────────────┐
│   Fast Path     │ → Known skills (instant)
│   (Regex)       │
└────────┬────────┘
         ↓
   Low confidence?
         ↓ Yes
┌─────────────────┐
│   Slow Path     │ → All skills + NEW discoveries
│   (Gemini)      │
└────────┬────────┘
         ↓
┌─────────────────┐
│  Discovery Mgr  │ → Track, count, auto-promote
└─────────────────┘
```

## Configuration

- `config/extraction_config.json` - Roles, countries, API settings
- `config/skills_taxonomy.json` - Skills and aliases (auto-updated by discoveries)

### Environment Variables

```bash
# Required
ADZUNA_APP_ID=your_id
ADZUNA_APP_KEY=your_key
SUPABASE_URL=your_connection_string

# Optional (for hybrid extraction)
GEMINI_API_KEY=your_gemini_key     # Enables LLM discovery
DISCOVERY_SAMPLE_RATE=0.1          # Sample 10% of jobs for discovery
COVERAGE_THRESHOLD=0.3             # Trigger slow path below 30% coverage
```

## Usage

```bash
# Activate virtual environment
cd etl
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run extraction
python extractor.py

# Run transformation (hybrid mode - default)
python transformer.py

# Run transformation (fast only - no LLM)
python transformer.py --fast-only

# Run transformation (discovery mode - LLM for all)
python transformer.py --discovery-mode

# Check progress
python check_progress.py
```

## CLI Options

| Flag | Description |
|------|-------------|
| `--batch-size N` | Process N jobs per batch (default: 1000) |
| `--reprocess` | Re-transform all jobs (truncates staging) |
| `--fast-only` | Disable LLM, regex matching only |
| `--discovery-mode` | Force LLM extraction for all jobs |

## Scheduling

The ETL pipeline runs via GitHub Actions (see `.github/workflows/`).
- **Schedule**: Twice weekly (Sun/Wed at 3 AM UTC)
- **Hybrid Mode**: Default for scheduled runs
- **Discovery Mode**: Can be triggered manually
