# Skill Hunt Backend

FastAPI backend for the Skill Hunt job market analysis dashboard.

## Setup

1. Create virtual environment:
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
copy .env.example .env
# Edit .env with your Supabase credentials
```

4. Run development server:
```bash
uvicorn app.main:app --reload --port 8000
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Skills
- `GET /api/v1/skills/demand` - Skill demand by role/country
- `GET /api/v1/skills/cooccurrence` - Skills that appear together
- `GET /api/v1/skills/network` - D3.js network graph data
- `GET /api/v1/skills/by-country` - Compare skill across countries

### Companies
- `GET /api/v1/companies/leaderboard` - Top hiring companies
- `GET /api/v1/companies/contract-types` - Job type distribution

### Salary
- `GET /api/v1/salary/by-skill` - Salary data by skill
- `GET /api/v1/salary/top-paying-skills` - Highest paying skills
- `GET /api/v1/salary/premium-skills` - Skills with salary premium

### Career
- `GET /api/v1/career/role-similarity` - All role similarities
- `GET /api/v1/career/transitions/{role}` - Career transitions from a role
- `GET /api/v1/career/skill-gap` - Skills needed for transition

### Stats
- `GET /api/v1/stats/summary` - Dashboard statistics
- `GET /api/v1/stats/filters` - Available filter options

## Deployment (Render)

1. Create a new Web Service on Render
2. Connect your GitHub repo
3. Set build command: `pip install -r backend/requirements.txt`
4. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables from `.env.example`

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application
│   ├── config.py        # Settings management
│   ├── database.py      # Database connection
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py   # Pydantic models
│   └── routers/
│       ├── __init__.py
│       ├── skills.py    # Skills endpoints
│       ├── companies.py # Companies endpoints
│       ├── salary.py    # Salary endpoints
│       ├── career.py    # Career endpoints
│       └── stats.py     # Statistics endpoints
├── requirements.txt
├── .env.example
└── README.md
```
