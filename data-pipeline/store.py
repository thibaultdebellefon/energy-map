"""Write-backend selector. If a Supabase connection string is configured
(SUPABASE_POOLER_URL / SUPABASE_DB_URL), the fetchers write to Supabase
(Postgres); otherwise they fall back to the local SQLite db. Fetchers just do
`import store as db` instead of `import db`.
"""
import os

try:
    import config  # noqa: F401 — loads .env into os.environ (safe if absent)
except Exception:
    pass

if os.environ.get("SUPABASE_POOLER_URL") or os.environ.get("SUPABASE_DB_URL"):
    from sbdb import *  # noqa: F401,F403  (Supabase backend)
    BACKEND = "supabase"
else:
    from db import *  # noqa: F401,F403  (local SQLite backend)
    BACKEND = "sqlite"
