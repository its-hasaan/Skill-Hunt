import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

# Connect to Supabase
conn_string = os.getenv('SUPABASE_URL')
conn = psycopg2.connect(conn_string)
cur = conn.cursor()

print("Checking existing tables...\n")

# Check all schemas
for schema in ['raw', 'staging', 'marts', 'public']:
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = %s 
        ORDER BY table_name;
    """, (schema,))
    
    tables = cur.fetchall()
    if tables:
        print(f"Tables in '{schema}' schema:")
        for table in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {schema}.{table[0]}")
                count = cur.fetchone()[0]
                print(f"  - {table[0]}: {count} rows")
            except Exception as e:
                print(f"  - {table[0]}: Error getting count - {str(e)}")
        print()

# Check if dbt_transform schema exists
cur.execute("""
    SELECT schema_name 
    FROM information_schema.schemata 
    WHERE schema_name = 'dbt_transform';
""")

if cur.fetchone():
    print("Tables in 'dbt_transform' schema:")
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'dbt_transform' 
        ORDER BY table_name;
    """)
    tables = cur.fetchall()
    for table in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM dbt_transform.{table[0]}")
            count = cur.fetchone()[0]
            print(f"  - {table[0]}: {count} rows")
        except Exception as e:
            print(f"  - {table[0]}: Error - {str(e)}")
else:
    print("'dbt_transform' schema does not exist")

cur.close()
conn.close()