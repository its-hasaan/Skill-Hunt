"""Small helpers for database-backed tests."""
import psycopg2


def run_sql(url, sql, params=None):
    """Execute one statement (or a script) in autocommit mode; return rows if any."""
    conn = psycopg2.connect(url)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else None
    finally:
        conn.close()
