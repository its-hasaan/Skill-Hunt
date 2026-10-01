"""
Shared machinery for company job-board connectors (Greenhouse, Lever,
Ashby, SmartRecruiters).

Each hiring system's module supplies:
  map_job(board, item)  -> dict of NormalizedJob fields plus `id`,
                           `locations`, `workplace_hint`, `remote_flag`
                           (pure: unit-tested against real API samples)
  fetch_board(board)    -> list of raw items, or None when the board failed
  enrich(board, item, job) -> optional extra call (SmartRecruiters detail)

AtsConnector fetches boards concurrently (bounded), keeps only tracked
roles that are remote or located in Pakistan/India, namespaces ids as
"<board>:<id>" (job_platform_id "<ats>:<board>:<id>"), records each board's
health in ops.companies, and exposes `seen_boards`: the boards fetched in
full this run, whose missing jobs the orchestrator may close.
"""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator, Optional

from .base import BaseConnector, NormalizedJob, build_session
from .location import classify_location
from .utils import to_iso

DEFAULT_CONCURRENCY = 4
DEFAULT_MAX_BOARDS = 400


class AtsConnector(BaseConnector):
    name = "ats"
    requires_key = False

    def __init__(self, config, role_matcher, logger_=None):
        super().__init__(config, role_matcher, logger_)
        self.seen_boards: set[str] = set()
        self._local = threading.local()

    # -- per-system hooks ------------------------------------------------------

    def map_job(self, board: str, item: dict) -> Optional[dict]:  # pragma: no cover - abstract
        raise NotImplementedError

    def fetch_board(self, board: str) -> Optional[list]:  # pragma: no cover - abstract
        raise NotImplementedError

    def enrich(self, board: str, item: dict, job: dict) -> dict:
        return job

    # -- shared ----------------------------------------------------------------

    @property
    def http(self):
        """One session per worker thread (requests.Session isn't thread-safe)."""
        if not hasattr(self._local, "session"):
            self._local.session = build_session(timeout=30, total_retries=2)
        return self._local.session

    def _get_json(self, url: str, **kwargs):
        try:
            resp = self.http.get(url, timeout=30, **kwargs)
            if resp.status_code != 200:
                self.log.info("%s: GET %s -> HTTP %s", self.name, url, resp.status_code)
                return None
            return resp.json()
        except Exception as exc:  # noqa: BLE001 - one board never breaks the run
            self.log.warning("%s: GET %s failed: %s", self.name, url, exc.__class__.__name__)
            return None

    def boards(self) -> list[str]:
        if "boards" in self.config:
            return list(self.config["boards"])
        from ops.companies import active_boards
        from ops.dbconfig import session_pooler_url
        import psycopg2

        conn = psycopg2.connect(session_pooler_url(os.getenv("SUPABASE_URL")))
        try:
            boards = active_boards(conn, self.name)
        finally:
            conn.close()
        return boards[: int(self.config.get("max_boards", DEFAULT_MAX_BOARDS))]

    def _record(self, board: str, ok: bool, count: Optional[int]) -> None:
        callback = self.config.get("record_check")
        if callback is not None:
            callback(self.name, board, ok=ok, job_count=count)
            return
        from ops.companies import record_check
        from ops.dbconfig import session_pooler_url
        import psycopg2

        conn = psycopg2.connect(session_pooler_url(os.getenv("SUPABASE_URL")))
        try:
            record_check(conn, self.name, board, ok=ok, job_count=count)
        finally:
            conn.close()

    def _safe_fetch(self, board: str):
        try:
            return board, self.fetch_board(board)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("%s: board %s failed: %s", self.name, board, exc.__class__.__name__)
            return board, None

    def fetch(self) -> Iterator[NormalizedJob]:
        self.seen_boards = set()
        boards = self.boards()
        workers = int(self.config.get("concurrency", DEFAULT_CONCURRENCY))
        kept = total = 0
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            results = list(pool.map(self._safe_fetch, boards))
        for board, items in results:
            self._record(board, ok=items is not None, count=None if items is None else len(items))
            if items is None:
                continue
            self.seen_boards.add(board)
            for item in items:
                total += 1
                job = self._to_job(board, item)
                if job is not None:
                    kept += 1
                    yield job
        self.log.info("%s: %d boards fetched (%d failed), kept %d of %d jobs",
                      self.name, len(self.seen_boards), len(boards) - len(self.seen_boards), kept, total)

    def _to_job(self, board: str, item: dict) -> Optional[NormalizedJob]:
        fields = self.map_job(board, item)
        if not fields or not fields.get("title"):
            return None
        role = self._match_role(fields["title"])
        if not role:
            return None
        placement = classify_location(fields.pop("locations", []), fields.pop("workplace_hint", None),
                                      fields.pop("remote_flag", None))
        if placement is None:
            return None
        workplace, country = placement
        fields = self.enrich(board, item, fields)
        job_id = fields.pop("id")
        fields["job_posted_at"] = to_iso(fields.get("job_posted_at"))
        fields.setdefault("company_name", board)
        fields.setdefault("category_tag", "it-jobs")
        fields.setdefault("category_label", "IT Jobs")
        return NormalizedJob(source=self.name, external_id=f"{board}:{job_id}", search_role=role,
                             country_code=country, workplace_type=workplace, **fields)
