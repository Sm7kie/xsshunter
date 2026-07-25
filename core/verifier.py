"""
Verifier: proves a payload actually executed, using a real headless browser.

This is the core differentiator. Every other stage in this tool produces
*candidates* - "this payload's context matches, it might work." This stage
loads the real injected page in Chromium and checks whether our JS flag
(window.__xsshunter_hit) actually got set. If it didn't, it's not reported,
no matter how promising the context looked.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

FLAG = "__xsshunter_hit"


@dataclass
class VerificationResult:
    executed: bool
    error: Optional[str] = None
    final_url: Optional[str] = None


class Verifier:
    def __init__(self, timeout_ms: int = 5000, headless: bool = True):
        self.timeout_ms = timeout_ms
        self.headless = headless
        self._playwright = None
        self._browser = None

    def __enter__(self):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        return self

    def __exit__(self, *exc):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def verify_get(self, url: str) -> VerificationResult:
        """Load a GET URL (payload already embedded in query string) and
        check whether the payload flag fired."""
        page = self._browser.new_page()
        try:
            # Reset the flag before navigation via an init script, since a
            # fresh page context has no state anyway - this just makes the
            # intent explicit and guards against about:blank caching odd cases.
            page.add_init_script(f"window.{FLAG} = false;")
            try:
                page.goto(url, timeout=self.timeout_ms, wait_until="load")
            except PWTimeout:
                return VerificationResult(executed=False, error="page load timeout")

            # give async handlers (onerror, onload, etc.) a brief moment
            page.wait_for_timeout(500)

            hit = page.evaluate(f"window.{FLAG} === true")
            return VerificationResult(executed=bool(hit), final_url=page.url)
        except Exception as e:
            return VerificationResult(executed=False, error=str(e))
        finally:
            page.close()

    def verify_post(self, url: str, form_data: dict) -> VerificationResult:
        """Submit a form via POST and check the resulting page for the flag.
        Uses page.evaluate to submit via fetch so we can inspect the response
        in the same browser context (needed for the JS to actually execute
        if the app reflects it into the response)."""
        page = self._browser.new_page()
        try:
            page.add_init_script(f"window.{FLAG} = false;")
            page.goto(url, timeout=self.timeout_ms, wait_until="load")

            form_selector = "form"
            if page.query_selector(form_selector) is None:
                return VerificationResult(executed=False, error="form not found on page")

            for name, value in form_data.items():
                field = page.query_selector(f'[name="{name}"]')
                if field:
                    field.fill(value)

            with page.expect_navigation(timeout=self.timeout_ms):
                page.click('button[type=submit], input[type=submit]')

            page.wait_for_timeout(500)
            hit = page.evaluate(f"window.{FLAG} === true")
            return VerificationResult(executed=bool(hit), final_url=page.url)
        except Exception as e:
            return VerificationResult(executed=False, error=str(e))
        finally:
            page.close()
