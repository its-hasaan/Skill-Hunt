# Skill Hunt Project Overview

## Project Description
Skill Hunt is a full-stack job market analysis dashboard that aggregates data from job postings to provide insights into skill demands, salary trends, and career paths. It leverages a modern data stack (MDS) approach with a Python extraction pipeline, hybrid skill extraction (regex + LLM), DBT for data transformation, FastAPI for the backend, and React for the frontend visualization.

## Data Flow
The data pipeline follows an ELT (Extract, Load, Transform) pattern:

1.  **Ingestion (Extract & Load)**:
    *   **Source**: Automated Python scripts (`etl/extractor.py`) query the **Adzuna API** for job postings across multiple roles and countries.
    *   **Destination**: Raw job data and descriptions are loaded into a **PostgreSQL** database (Supabase).

2.  **Skill Extraction (Hybrid Approach)**:
    *   **Fast Path**: Regex-based matching against a skills taxonomy (`etl/config/skills_taxonomy.json`) for known skills. Handles ~95% of skill mentions instantly at zero cost.
    *   **Slow Path**: LLM-based extraction (Google Gemini Flash) for skill discovery. Triggered when fast path has low confidence or via sampling.
    *   **Discovery Manager**: Tracks newly discovered skills, accumulates occurrence counts, and auto-promotes frequently-seen skills to the taxonomy.

3.  **Transformation**:
    *   **DBT (Data Build Tool)**: The `dbt_project/` contains SQL models that transform raw data into analytical "marts".
    *   It cleans, enriches, and facilitates complex aggregations (e.g., skill co-occurrence, role similarity, company leaderboards).

4.  **Serving**:
    *   **Backend**: A **FastAPI** application (`backend/`) exposes REST endpoints that query the final DBT marts.
    *   **Frontend**: A **React/Vite** application (`frontend/`) consumes these APIs to render interactive charts (Recharts) and heatmaps.

## Functionalities
The application offers several analytical modules:
*   **Dashboard**: High-level metrics on job market health, top skills, and recent trends.
*   **Skills Analysis**: Detailed breakdown of skill demand, growth vs. decline, and skill-to-skill relationships (co-occurrence).
*   **Salary Insights**: Compensation analysis correlating skills and roles with salary ranges.
*   **Company Leaderboards**: Analysis of top hiring companies and their specific skill requirements.
*   **Career Paths**: Role similarity analysis to suggest potential career pivots based on overlapping skill sets.
*   **Global View**: Geographic distribution of roles and skills (e.g., "Skills by Country").

## Automated Scheduled ETL Status
*   **Implementation Status**: **Fully Implemented**
    *   The scripts for extraction (`extractor.py`), transformation (`transformer.py`), and modeling (`dbt`) are complete.
    *   A CI/CD workflow (`.github/workflows/etl_pipeline.yml`) orchestrates the entire sequence.

*   **Usage Status**: **Being Used**
    *   The pipeline is actively scheduled via GitHub Actions.
    *   **Schedule**: Runs twice a week (Sundays and Wednesdays at 3:00 AM UTC).
    *   **Triggers**: Supports both cron scheduling and manual `workflow_dispatch` trigger.

## Use Case
**Target Audience**: Job Seekers, Data Analysts, Recruiters, and Career Coaches.

**Primary Use Case**:
To provide a data-driven interface for understanding the current labor market. A user can answer questions such as:
*   "What are the most required skills for a Data Engineer in the UK right now?"
*   "Which skills command the highest salary premiums?"
*   "Which companies are aggressively hiring for my skillset?"
*   "If I know Python and SQL, what other roles are similar to my current one?"
