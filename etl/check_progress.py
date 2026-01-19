"""
Quick script to check transformation progress
"""
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

conn = psycopg2.connect(os.getenv("SUPABASE_URL"))
cur = conn.cursor()

# Total raw records
cur.execute("SELECT COUNT(*) FROM raw.jobs")
total_raw = cur.fetchone()[0]

# Processed records
cur.execute("SELECT COUNT(*) FROM staging.stg_jobs")
total_processed = cur.fetchone()[0]

# Remaining
remaining = total_raw - total_processed

# Skills extracted
cur.execute("SELECT COUNT(*) FROM staging.stg_job_skills")
total_skills = cur.fetchone()[0]

print(f"\n{'='*60}")
print(f"TRANSFORMATION PROGRESS")
print(f"{'='*60}")
print(f"Total raw records:        {total_raw:,}")
print(f"Processed records:        {total_processed:,}")
print(f"Remaining to process:     {remaining:,}")
print(f"Progress:                 {(total_processed/total_raw*100):.1f}%")
print(f"Total skills extracted:   {total_skills:,}")
print(f"{'='*60}\n")

cur.close()
conn.close()
