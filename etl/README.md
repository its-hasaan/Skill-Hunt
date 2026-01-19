# ETL Pipeline

Data extraction and transformation scripts for Skill Hunt.

## Scripts

| Script | Purpose |
|--------|---------|
| `extractor.py` | Extracts job postings from Adzuna API |
| `transformer.py` | Extracts skills from job descriptions |
| `check_progress.py` | Check transformation progress |

## Configuration

- `config/extraction_config.json` - Roles, countries, API settings
- `config/skills_taxonomy.json` - Skills and aliases for matching

## Usage

```bash
# Activate virtual environment
cd etl
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file with credentials
# ADZUNA_APP_ID=your_id
# ADZUNA_APP_KEY=your_key
# SUPABASE_URL=your_connection_string

# Run extraction
python extractor.py

# Run transformation
python transformer.py

# Check progress
python check_progress.py
```

## Scheduling

The ETL pipeline runs via GitHub Actions (see `.github/workflows/`).
