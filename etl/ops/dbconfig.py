"""
Database connection settings derived from ONE secret: SUPABASE_URL.

Every pipeline step (ETL scripts, dbt, CI) derives what it needs from that
single URL, so a rotated password or a moved pooler host is fixed in exactly
one place.

CLI (used by CI to configure dbt):
    python -m ops.dbconfig --github-env
appends DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME and SUPABASE_SESSION_URL
to $GITHUB_ENV and masks the password in the Actions log.
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.parse as urlparse

TRANSACTION_POOLER_PORT = 6543
SESSION_POOLER_PORT = 5432


def session_pooler_url(url: str | None) -> str | None:
    """Supabase's transaction pooler (6543) drops long-lived connections; the
    session pooler (5432, same host) keeps them. Long steps must use 5432."""
    if url and f":{TRANSACTION_POOLER_PORT}/" in url:
        return url.replace(f":{TRANSACTION_POOLER_PORT}/", f":{SESSION_POOLER_PORT}/")
    return url


def dbt_env_vars(url: str) -> dict[str, str]:
    """The DB_* variables dbt_project/profiles.yml reads, on the session pooler."""
    u = urlparse.urlparse(session_pooler_url(url))
    return {
        "DB_HOST": u.hostname or "",
        "DB_PORT": str(u.port or SESSION_POOLER_PORT),
        "DB_USER": urlparse.unquote(u.username or ""),
        "DB_PASSWORD": urlparse.unquote(u.password or ""),
        "DB_NAME": (u.path or "/postgres").lstrip("/") or "postgres",
    }


def write_github_env(url: str, env_file: str, out=sys.stdout) -> None:
    values = dbt_env_vars(url)
    values["SUPABASE_SESSION_URL"] = session_pooler_url(url)
    if values["DB_PASSWORD"]:
        print(f"::add-mask::{values['DB_PASSWORD']}", file=out)
    with open(env_file, "a", encoding="utf-8") as fh:
        for key, value in values.items():
            fh.write(f"{key}={value}\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Derive DB settings from SUPABASE_URL")
    parser.add_argument("--github-env", action="store_true",
                        help="Append derived variables to $GITHUB_ENV")
    args = parser.parse_args(argv)
    url = os.getenv("SUPABASE_URL")
    if not url:
        print("SUPABASE_URL is not set", file=sys.stderr)
        return 1
    if args.github_env:
        env_file = os.getenv("GITHUB_ENV")
        if not env_file:
            print("GITHUB_ENV is not set (not running in GitHub Actions?)", file=sys.stderr)
            return 1
        write_github_env(url, env_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
