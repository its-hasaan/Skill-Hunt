import os

# Settings requires a DB URL at import time; tests never connect with it.
os.environ.setdefault("SUPABASE_URL", "postgresql://test:test@localhost:5432/test")
