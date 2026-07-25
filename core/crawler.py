"""
Crawler: discovers input points on a target site.

An "input point" is anywhere user-controlled data flows into the page:
  - URL query parameters
  - HTML form fields (GET or POST)

We keep this deliberately simple and same-origin only. No JS-rendered
route discovery yet (that would require a headless browser pass, which
belongs in verifier.py's territory later).
"""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field
from typing import List, Set

import requests
from bs4 import BeautifulSoup


@dataclass
class InputPoint:
    """A single place where attacker-controlled input reaches the app."""
    url: str                  # page where this input point was found
    method: str                # GET or POST
    param: str                  # parameter name
    action: str                 # submission URL (for forms) or same as url
    source: str                 # "url_param" or "form"

    def __repr__(self) -> str:
        return f"<InputPoint {self.method} {self.action}?{self.param}>"


@dataclass
class CrawlResult:
    visited: Set[str] = field(default_factory=set)
    input_points: List[InputPoint] = field(default_factory=list)


class Crawler:
    def __init__(self, base_url: str, max_pages: int = 50, timeout: int = 10):
        self.base_url = base_url
        self.origin = urllib.parse.urlparse(base_url).netloc
        self.max_pages = max_pages
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "XSSHunter/0.1 (authorized-testing-tool)"
        })

    def _same_origin(self, url: str) -> bool:
        return urllib.parse.urlparse(url).netloc == self.origin

    def _extract_links(self, html: str, page_url: str) -> Set[str]:
        soup = BeautifulSoup(html, "lxml")
        links = set()
        for a in soup.find_all("a", href=True):
            full = urllib.parse.urljoin(page_url, a["href"])
            full, _ = urllib.parse.urldefrag(full)  # drop #fragments
            if self._same_origin(full):
                links.add(full)
        return links

    def _extract_url_params(self, url: str) -> List[InputPoint]:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        points = []
        for param in qs:
            points.append(InputPoint(
                url=url, method="GET", param=param, action=url, source="url_param"
            ))
        return points

    def _extract_forms(self, html: str, page_url: str) -> List[InputPoint]:
        soup = BeautifulSoup(html, "lxml")
        points = []
        for form in soup.find_all("form"):
            action = urllib.parse.urljoin(page_url, form.get("action", page_url))
            method = form.get("method", "get").upper()
            for field_tag in form.find_all(["input", "textarea", "select"]):
                name = field_tag.get("name")
                if not name:
                    continue
                points.append(InputPoint(
                    url=page_url, method=method, param=name,
                    action=action, source="form"
                ))
        return points

    def crawl(self) -> CrawlResult:
        result = CrawlResult()
        queue = [self.base_url]

        while queue and len(result.visited) < self.max_pages:
            url = queue.pop(0)
            if url in result.visited:
                continue
            result.visited.add(url)

            try:
                resp = self.session.get(url, timeout=self.timeout)
            except requests.RequestException:
                continue

            if "text/html" not in resp.headers.get("Content-Type", ""):
                continue

            result.input_points.extend(self._extract_url_params(url))
            result.input_points.extend(self._extract_forms(resp.text, url))

            for link in self._extract_links(resp.text, url):
                if link not in result.visited:
                    queue.append(link)

        return result
