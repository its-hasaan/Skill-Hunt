"""
robots.txt for the career-page crawler.

Reading robots.txt is required: RobotsPolicy.from_response() returns None
when it can't be read (network error, 5xx, a bot-challenge HTML page), and
the crawler then skips the site. 404/410 mean the site has no rules.
"""
from __future__ import annotations

from typing import Optional
from urllib.robotparser import RobotFileParser

USER_AGENT_TOKEN = "JobwiseBot"


class RobotsPolicy:
    def __init__(self, parser: Optional[RobotFileParser]):
        self._parser = parser  # None = no rules

    @classmethod
    def from_response(cls, status: Optional[int], text: str) -> Optional["RobotsPolicy"]:
        if status in (404, 410):
            return cls(None)
        if status != 200:
            return None
        if "<html" in (text or "")[:500].lower():
            return None  # a challenge or error page served in place of robots.txt
        parser = RobotFileParser()
        parser.parse((text or "").splitlines())
        return cls(parser)

    def allowed(self, url: str) -> bool:
        return True if self._parser is None else self._parser.can_fetch(USER_AGENT_TOKEN, url)
