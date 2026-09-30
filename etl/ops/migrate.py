"""
Versioned schema migrations.

Files in database/migrations named NNN_description.sql are applied in order
and recorded in ops.schema_migrations. Each file manages its own transaction
(BEGIN; ... COMMIT;) so a failure leaves nothing half-applied.

    python -m ops.migrate status
    python -m ops.migrate up
    python -m ops.migrate baseline 005   # mark 001..005 applied (run by hand earlier)
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

import psycopg2

from ops.dbconfig import session_pooler_url

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "database" / "migrations"
NAME_RE = re.compile(r"^(\d{3})_[\w-]+\.sql$")

TRACKING_DDL = """
CREATE SCHEMA IF NOT EXISTS ops;
CREATE TABLE IF NOT EXISTS ops.schema_migrations (
    filename   TEXT PRIMARY KEY,
    checksum   TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def connect(url: str):
    conn = psycopg2.connect(url)
    conn.autocommit = True  # each migration file controls its own transaction
    return conn


def checksum(path: Path) -> str:
    """SHA-256 of the file with line endings normalised (Windows checkouts use CRLF)."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def discover(directory: Path = MIGRATIONS_DIR) -> list[Path]:
    return sorted((p for p in directory.iterdir() if NAME_RE.match(p.name)), key=lambda p: p.name)


def applied(conn) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(TRACKING_DDL)
        cur.execute("SELECT filename, checksum FROM ops.schema_migrations")
        return dict(cur.fetchall())


def pending(conn, directory: Path = MIGRATIONS_DIR) -> list[Path]:
    done = applied(conn)
    return [p for p in discover(directory) if p.name not in done]


def changed(conn, directory: Path = MIGRATIONS_DIR) -> list[str]:
    done = applied(conn)
    return [p.name for p in discover(directory) if p.name in done and done[p.name] != checksum(p)]


def _record(conn, path: Path) -> None:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO ops.schema_migrations (filename, checksum) VALUES (%s, %s)",
                    (path.name, checksum(path)))


def up(conn, directory: Path = MIGRATIONS_DIR) -> list[str]:
    done = []
    for path in pending(conn, directory):
        try:
            with conn.cursor() as cur:
                cur.execute(path.read_text(encoding="utf-8"))
        except psycopg2.Error:
            with conn.cursor() as cur:
                cur.execute("ROLLBACK")  # leave no aborted transaction behind
            raise
        _record(conn, path)
        done.append(path.name)
    return done


def baseline(conn, through: str, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Record migrations numbered <= `through` as applied without running them."""
    limit = through.zfill(3)
    done = applied(conn)
    marked = []
    for path in discover(directory):
        if NAME_RE.match(path.name).group(1) > limit:
            break
        if path.name not in done:
            _record(conn, path)
            marked.append(path.name)
    return marked


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Apply database migrations")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("up")
    base = sub.add_parser("baseline")
    base.add_argument("through", help="last migration number already applied by hand, e.g. 005")
    args = parser.parse_args(argv)

    url = session_pooler_url(os.getenv("SUPABASE_URL"))
    if not url:
        print("SUPABASE_URL is not set", file=sys.stderr)
        return 1
    conn = connect(url)
    try:
        if args.command == "status":
            done = applied(conn)
            for path in discover():
                print(f"  {'applied' if path.name in done else 'PENDING'}  {path.name}")
            for name in changed(conn):
                print(f"  WARNING: {name} changed after it was applied")
        elif args.command == "baseline":
            for name in baseline(conn, args.through):
                print(f"  baselined {name}")
        else:
            try:
                names = up(conn)
            except psycopg2.Error as exc:
                print(f"Migration failed: {exc}", file=sys.stderr)
                return 1
            print("\n".join(f"  applied {n}" for n in names) or "  nothing to apply")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
