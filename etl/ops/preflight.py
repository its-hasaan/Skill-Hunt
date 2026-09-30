"""
Pipeline preflight: verify credentials and connectivity BEFORE any step
runs, and say exactly what to fix. The scheduled pipeline failed for
months with the cause buried in a stack trace inside the first step; this
turns it into one readable line.

    python -m ops.preflight            # database checks (fatal)
    python -m ops.preflight --adzuna   # + Adzuna credential probe (warning only)
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
import urllib.parse as urlparse
from dataclasses import dataclass

import psycopg2
import requests

from ops.dbconfig import load_local_env

ADZUNA_PROBE = "https://api.adzuna.com/v1/api/jobs/gb/search/1"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def diagnose_db_url(url: str | None) -> list[str]:
    """Problems visible in the URL itself, without touching the network."""
    if not url:
        return ["SUPABASE_URL is empty or not set. Add it as a repository secret."]
    problems = []
    u = urlparse.urlparse(url)
    if u.scheme not in ("postgres", "postgresql"):
        problems.append(f"URL scheme is '{u.scheme}', expected 'postgresql'.")
    host = u.hostname or ""
    if not host:
        problems.append("SUPABASE_URL has no host.")
    elif host.startswith("db.") and host.endswith(".supabase.co"):
        problems.append(
            f"{host} is Supabase's direct connection, which is IPv6-only, and GitHub "
            "Actions runners have no IPv6. Use the pooler connection string "
            "(host ends in .pooler.supabase.com) from Supabase > Connect."
        )
    try:
        port = u.port
    except ValueError:
        port = None
        problems.append("SUPABASE_URL has an invalid port.")
    if "supabase" in host and port not in (None, 5432, 6543):
        problems.append(f"Port {port} is unusual for Supabase (expected 5432 or 6543).")
    if not u.password:
        problems.append("SUPABASE_URL has no password.")
    return problems


def check_dns(host: str) -> Check:
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_INET)
    except socket.gaierror:
        return Check("dns", False, f"{host} has no IPv4 address.")
    return Check("dns", True, f"{host} resolves to {infos[0][4][0]}")


def check_db(url: str) -> Check:
    host = urlparse.urlparse(url).hostname
    try:
        conn = psycopg2.connect(url, connect_timeout=15)
    except psycopg2.OperationalError as exc:
        text = str(exc).lower()
        if "password authentication failed" in text:
            cause = "password authentication failed; the password in SUPABASE_URL is wrong (was it reset?)"
        elif "tenant or user not found" in text:
            cause = "the pooler user (postgres.<project-ref>) or the region host is wrong"
        elif "timeout" in text or "timed out" in text:
            cause = "connection timed out; is the Supabase project paused?"
        else:
            cause = "connection refused or rejected"
        return Check("database", False, f"Cannot connect to {host}: {cause}.")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    finally:
        conn.close()
    return Check("database", True, f"Connected to {host}")


def check_adzuna(app_id, app_key, http=requests) -> Check:
    if not app_id or not app_key:
        return Check("adzuna", False, "ADZUNA_APP_ID / ADZUNA_APP_KEY are not set.")
    try:
        resp = http.get(ADZUNA_PROBE, params={"app_id": app_id, "app_key": app_key,
                                              "results_per_page": 1, "what": "engineer"}, timeout=30)
    except requests.RequestException as exc:
        return Check("adzuna", False, f"Adzuna unreachable ({exc.__class__.__name__}).")
    if resp.status_code == 200:
        return Check("adzuna", True, "Adzuna credentials accepted")
    if resp.status_code in (401, 403):
        return Check("adzuna", False, f"Adzuna rejected the credentials (HTTP {resp.status_code}).")
    if resp.status_code == 429:
        return Check("adzuna", False, "Adzuna rate limit hit (HTTP 429); the daily/monthly quota may be used up.")
    return Check("adzuna", False, f"Adzuna returned HTTP {resp.status_code}.")


def run_checks(url, adzuna: bool, env=os.environ) -> list[Check]:
    problems = diagnose_db_url(url)
    checks = [Check("database url", not problems, " ".join(problems) or "Supabase URL looks valid")]
    if not problems:
        dns = check_dns(urlparse.urlparse(url).hostname)
        checks.append(dns)
        if dns.ok:
            checks.append(check_db(url))
    if adzuna:
        checks.append(check_adzuna(env.get("ADZUNA_APP_ID"), env.get("ADZUNA_APP_KEY")))
    return checks


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Check pipeline credentials and connectivity")
    parser.add_argument("--adzuna", action="store_true", help="also probe the Adzuna credentials")
    args = parser.parse_args(argv)
    checks = run_checks(os.getenv("SUPABASE_URL"), args.adzuna)
    for c in checks:
        print(f"[{'OK' if c.ok else 'FAIL':>4}] {c.name}: {c.detail}")
    fatal = [c for c in checks if not c.ok and c.name != "adzuna"]
    if any(not c.ok and c.name == "adzuna" for c in checks):
        print("::warning::Adzuna check failed; the Adzuna step will fail, other sources continue.")
    return 1 if fatal else 0


if __name__ == "__main__":
    load_local_env()
    sys.exit(main())
