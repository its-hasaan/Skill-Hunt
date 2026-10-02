"""
Company career pages (Phase 1d): schema.org JobPosting JSON-LD, read
politely, plus registry growth when a page embeds a hiring-system board.

Per site (ops.career_sites), one site per worker thread:
  1. robots.txt is required: unreadable -> skip (fail_count + 1);
     the careers page disallowed -> status 'blocked'.
  2. The careers page (stored URL, else /careers then /jobs), with a
     conditional GET. 304 -> the listing is unchanged: its open jobs get a
     sighting (ops.lifecycle.touch_board) and nothing is re-read.
  3. An embedded Greenhouse/Lever/Ashby/SmartRecruiters/Workable board wins:
     it goes to ops.companies (validated, then read by that connector) and
     the site is marked 'ats'.
  4. Otherwise JobPosting JSON-LD from the careers page and up to
     page_budget - 1 job-detail pages on the same site, delay_seconds apart.
     No JSON-LD and no job links (e.g. JavaScript-only pages) -> 'empty'.

A site joins seen_boards (its unlisted jobs may be closed) only when its
crawl wasn't cut short by the page budget.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Optional

from careers.html_links import ats_boards, extract_links, job_links
from careers.jsonld import extract_jobpostings, map_jobposting
from careers.robots import RobotsPolicy
from ops.discover_companies import extract_tokens

from .ats_base import AtsConnector

USER_AGENT = "JobwiseBot/1.0 (+https://github.com/its-hasaan; job-market research)"
DEFAULT_BUDGET = 25
DEFAULT_DELAY = 2.0
DEFAULT_MAX_SITES = 200
MAX_PAGE_BYTES = 2_000_000


def _db():
    import psycopg2
    from ops.dbconfig import session_pooler_url
    return psycopg2.connect(session_pooler_url(os.getenv("SUPABASE_URL")))


class CareerPageConnector(AtsConnector):
    name = "careerpage"

    def __init__(self, config, role_matcher, logger_=None):
        super().__init__(config, role_matcher, logger_)
        self._sites: dict[str, dict] = {}
        self._truncated: set[str] = set()
        self._http_local = threading.local()
        self._sleep = config.get("sleep", time.sleep)
        self.page_budget = int(config.get("page_budget", DEFAULT_BUDGET))
        self.delay = float(config.get("delay_seconds", DEFAULT_DELAY))

    # -- registry and side effects (test seams in config) -------------------------

    def boards(self) -> list[str]:
        if "sites" in self.config:
            sites = list(self.config["sites"])
        else:
            from ops.career_sites import sites_to_crawl
            conn = _db()
            try:
                sites = sites_to_crawl(conn, int(self.config.get("max_sites", DEFAULT_MAX_SITES)))
            finally:
                conn.close()
        self._sites = {s["domain"]: s for s in sites}
        return list(self._sites)

    def _record(self, board, ok, count, kept=None):
        """Board health lives in ops.career_sites (written by the crawl itself)."""

    def _record_site(self, domain: str, status: Optional[str], **kw) -> None:
        if "record" in self.config:
            self.config["record"](domain, status, **kw)
            return
        from ops.career_sites import record_crawl
        conn = _db()
        try:
            record_crawl(conn, domain, status, **kw)
        finally:
            conn.close()

    def _register_board(self, ats: str, tokens: set[str]) -> None:
        if "register_board" in self.config:
            self.config["register_board"](ats, tokens)
            return
        from ops.companies import upsert_candidates
        conn = _db()
        try:
            upsert_candidates(conn, ats, sorted(tokens), "careerpage")
        finally:
            conn.close()

    def _touch(self, domain: str) -> None:
        if "touch" in self.config:
            self.config["touch"](domain)
            return
        from ops.lifecycle import touch_board
        conn = _db()
        try:
            touch_board(conn, self.name, domain)
        finally:
            conn.close()

    def _fetch(self, url: str, headers: dict):
        if "fetch" in self.config:
            return self.config["fetch"](url, headers)
        import requests
        if not hasattr(self._http_local, "session"):
            session = requests.Session()
            session.headers["User-Agent"] = USER_AGENT
            self._http_local.session = session
        try:
            resp = self._http_local.session.get(url, headers=headers, timeout=20)
            # the final URL after redirects: a careers link often lands on a hiring-system board
            return resp.status_code, resp.text[:MAX_PAGE_BYTES], {**resp.headers, "_final_url": resp.url}
        except requests.RequestException:
            return None, "", {}

    # -- crawl -----------------------------------------------------------------------

    def fetch(self):
        self._truncated = set()
        yield from super().fetch()
        self.seen_boards -= self._truncated

    def map_job(self, board, item):
        fields = map_jobposting(item, item.get("_page_url") or f"https://{board}/")
        if fields is not None and not fields.get("company_name"):
            fields["company_name"] = board
        return fields

    def fetch_board(self, domain: str) -> Optional[list]:
        site = self._sites[domain]
        status, text, _ = self._fetch(f"https://{domain}/robots.txt", {})
        policy = RobotsPolicy.from_response(status, text)
        if policy is None:
            self._record_site(domain, None, failed=True)
            return None

        stored = site.get("careers_url")
        candidates = [stored] if stored else [f"https://{domain}/careers", f"https://{domain}/jobs"]
        blocked = False
        for url in candidates:
            if not policy.allowed(url):
                blocked = True
                continue
            headers = {}
            if url == stored and site.get("etag"):
                headers["If-None-Match"] = site["etag"]
            if url == stored and site.get("last_modified"):
                headers["If-Modified-Since"] = site["last_modified"]
            status, page, response_headers = self._fetch(url, headers)
            if status == 304:
                self._touch(domain)
                self._record_site(domain, site.get("status") or "jsonld")
                return None
            if status != 200:
                continue
            return self._read_listing(domain, url, page, response_headers, policy)

        if blocked:
            self._record_site(domain, "blocked")
        else:
            self._record_site(domain, None, failed=True)
        return None

    def _read_listing(self, domain, url, page, response_headers, policy) -> list:
        boards = ats_boards(page, url)
        for ats, tokens in extract_tokens([response_headers.get("_final_url") or url]).items():
            if tokens:
                boards.setdefault(ats, set()).update(tokens)
        if boards:
            for ats, tokens in boards.items():
                self._register_board(ats, tokens)
            first_ats = sorted(boards)[0]
            self._record_site(domain, "ats", ats=first_ats, board_token=sorted(boards[first_ats])[0])
            return []

        items = [dict(item, _page_url=url) for item in extract_jobpostings(page)]
        links = [link for link in job_links(extract_links(page, url), domain, limit=10_000) if link != url]
        to_read = links[: max(0, self.page_budget - 1)]
        if len(links) > len(to_read):
            self._truncated.add(domain)
        for link in to_read:
            if not policy.allowed(link):
                continue
            self._sleep(self.delay)
            status, job_page, _ = self._fetch(link, {})
            if status == 200:
                items += [dict(item, _page_url=link) for item in extract_jobpostings(job_page)]

        unique = {}
        for item in items:
            identifier = item.get("identifier")
            key = (identifier.get("value") if isinstance(identifier, dict) else identifier) \
                or item.get("url") or (item.get("_page_url"), item.get("title"))
            unique.setdefault(str(key), item)
        found = list(unique.values())
        self._record_site(domain, "jsonld" if found else "empty", jobs_found=len(found),
                          etag=response_headers.get("ETag"), last_modified=response_headers.get("Last-Modified"))
        return found
