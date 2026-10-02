"""
Discover company job boards from the Common Crawl URL index.

Common Crawl publishes an open, free index of the URLs it crawled. Querying
it for the hiring systems' job-board hosts (boards.greenhouse.io/<company>,
jobs.lever.co/<company>, ...) yields board tokens; new ones are added to
ops.companies as candidates and probed by the validator. One request per
second to the index, as Common Crawl asks.

    python -m ops.discover_companies [--index CC-MAIN-2026-39] [--max-pages 3] [--validate-limit 200]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse as urlparse
from typing import Callable, Optional

import psycopg2

from ops.dbconfig import load_local_env, session_pooler_url

INDEX_LIST = "https://index.commoncrawl.org/collinfo.json"
CDX = "https://index.commoncrawl.org/{index}-index?url={host}/*&output=json&fl=url&page={page}"
# host -> hiring system
HOSTS = {
    "boards.greenhouse.io": "greenhouse",
    "job-boards.greenhouse.io": "greenhouse",
    "jobs.lever.co": "lever",
    "jobs.ashbyhq.com": "ashby",
    "jobs.smartrecruiters.com": "smartrecruiters",
    "apply.workable.com": "workable",
}
RESERVED = {"", "embed", "api", "j", "assets", "static", "js", "css", "favicon.ico", "robots.txt"}
TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,79}$")
CASE_SENSITIVE = {"smartrecruiters"}


def extract_tokens(urls) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {ats: set() for ats in set(HOSTS.values())}
    for url in urls:
        parsed = urlparse.urlparse(url)
        ats = HOSTS.get((parsed.hostname or "").lower())
        if not ats:
            continue
        first = parsed.path.strip("/").split("/", 1)[0]
        if first == "embed":
            first = (urlparse.parse_qs(parsed.query).get("for") or [""])[0]
        if first.lower() in RESERVED or not TOKEN_RE.match(first):
            continue
        found[ats].add(first if ats in CASE_SENSITIVE else first.lower())
    return found


def crawl(index: str, max_pages: int, fetch: Callable[[str], Optional[str]],
          sleep: Callable[[float], None] = time.sleep) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {ats: set() for ats in set(HOSTS.values())}
    for host in HOSTS:
        for page in range(max_pages):
            body = fetch(CDX.format(index=index, host=host, page=page))
            sleep(1.0)
            if not body:
                break  # empty page, timeout or 5xx: move to the next host
            urls = []
            for line in body.splitlines():
                try:
                    urls.append(json.loads(line)["url"])
                except (ValueError, KeyError):
                    continue
            if not urls:
                break
            for ats, tokens in extract_tokens(urls).items():
                found[ats] |= tokens
    return found


RETRY_STATUSES = {429, 500, 502, 503, 504}


def http_fetch(url: str, attempts: int = 3, get=None, sleep: Callable[[float], None] = time.sleep,
               backoff: float = 10.0) -> Optional[str]:
    """GET a CDX page. The index often answers 503/504 under load, so those
    (and 429s and timeouts) are retried with growing waits; other errors
    return None at once."""
    import requests
    get = get or requests.get
    for attempt in range(attempts):
        try:
            resp = get(url, timeout=120, headers={"User-Agent": "JobwiseBot/1.0 (job-market research)"})
            if resp.status_code == 200:
                return resp.text
            if resp.status_code not in RETRY_STATUSES:
                return None
        except requests.RequestException:
            pass
        if attempt < attempts - 1:
            sleep(backoff * (attempt + 1))
    return None


def latest_index() -> str:
    import requests
    return requests.get(INDEX_LIST, timeout=60).json()[0]["id"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Discover company job boards from Common Crawl")
    parser.add_argument("--index", help="Common Crawl index id (default: latest)")
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--validate-limit", type=int, default=200)
    args = parser.parse_args(argv)

    url = session_pooler_url(os.getenv("SUPABASE_URL"))
    if not url:
        print("SUPABASE_URL is not set", file=sys.stderr)
        return 1
    from ops.companies import http_probe, upsert_candidates, validate

    index = args.index or latest_index()
    found = crawl(index, args.max_pages, http_fetch)
    conn = psycopg2.connect(url)
    try:
        added = {ats: upsert_candidates(conn, ats, tokens, "commoncrawl") for ats, tokens in found.items()}
        print(f"{index}: tokens found {({a: len(t) for a, t in found.items()})}, new candidates {added}")
        print(f"validated: {validate(conn, http_probe(), limit=args.validate_limit)}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    load_local_env()
    sys.exit(main())
