"""
Scanner: orchestrates the full pipeline.

  crawl -> for each input point:
             inject marker -> detect context -> pick payloads ->
             inject each payload -> verify execution in real browser
           -> collect confirmed findings
"""
from __future__ import annotations

import uuid
import urllib.parse
from dataclasses import dataclass, field
from typing import List

import requests

from core.crawler import Crawler, InputPoint
from core.context import analyze, Context
from core.payloads import candidates_for
from core.verifier import Verifier


@dataclass
class Finding:
    input_point: InputPoint
    context: Context
    payload: str
    proof_url: str


@dataclass
class ScanReport:
    target: str
    input_points_tested: int = 0
    findings: List[Finding] = field(default_factory=list)


def _url_with_param(base_url: str, param: str, value: str) -> str:
    parsed = urllib.parse.urlparse(base_url)
    qs = urllib.parse.parse_qs(parsed.query)
    qs[param] = value
    new_query = urllib.parse.urlencode(qs, doseq=True)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))


class Scanner:
    def __init__(self, target: str, max_pages: int = 50, verbose: bool = False):
        self.target = target
        self.max_pages = max_pages
        self.verbose = verbose
        self.session = requests.Session()

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    def run(self) -> ScanReport:
        report = ScanReport(target=self.target)

        self._log(f"[*] Crawling {self.target} ...")
        crawl_result = Crawler(self.target, max_pages=self.max_pages).crawl()
        self._log(f"[*] Found {len(crawl_result.input_points)} input points "
                   f"across {len(crawl_result.visited)} pages")

        with Verifier() as verifier:
            for point in crawl_result.input_points:
                report.input_points_tested += 1
                self._probe_input_point(point, verifier, report)

        return report

    def _probe_input_point(self, point: InputPoint, verifier: Verifier,
                            report: ScanReport):
        marker = f"xh{uuid.uuid4().hex[:8]}"

        # Step 1: send the marker alone to see where it lands.
        if point.method == "GET":
            probe_url = _url_with_param(point.action, point.param, marker)
            try:
                resp = self.session.get(probe_url, timeout=10)
            except requests.RequestException as e:
                self._log(f"    [!] request failed for {point}: {e}")
                return
        else:
            # POST forms: probe via a raw request just to see reflection;
            # actual exploitation attempt happens through the browser later.
            try:
                resp = self.session.post(point.action, data={point.param: marker}, timeout=10)
            except requests.RequestException as e:
                self._log(f"    [!] request failed for {point}: {e}")
                return

        matches = analyze(resp.text, marker)
        executable_matches = [m for m in matches if candidates_for(m.context)]

        if not executable_matches:
            self._log(f"    [-] {point.param}: no exploitable context "
                       f"({[m.context.value for m in matches]})")
            return

        self._log(f"    [~] {point.param}: candidate context(s) "
                   f"{[m.context.value for m in executable_matches]}")

        # Step 2: for each candidate context, try its payloads and verify.
        for match in executable_matches:
            for payload in candidates_for(match.context):
                if point.method == "GET":
                    attack_url = _url_with_param(point.action, point.param, payload)
                    result = verifier.verify_get(attack_url)
                    proof_url = attack_url
                else:
                    result = verifier.verify_post(point.action, {point.param: payload})
                    proof_url = point.action

                if result.executed:
                    self._log(f"    [+] CONFIRMED: {point.param} "
                              f"({match.context.value}) -> {payload!r}")
                    report.findings.append(Finding(
                        input_point=point, context=match.context,
                        payload=payload, proof_url=proof_url,
                    ))
                    # one confirmed payload per input point is enough signal;
                    # move to the next input point rather than spamming more.
                    return
                elif result.error:
                    self._log(f"    [!] verify error: {result.error}")
