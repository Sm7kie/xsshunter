"""
Context analyzer.

Given a response body and a unique marker string we injected, figure out
*where* that marker landed. This determines which payload family can
possibly execute there — injecting a <script> tag into a JS string
context is pointless; you need to break out of the string first.

Contexts we detect, roughly in order of "how hard to escape":
  HTML_TEXT        -> marker sits in the page body, outside any tag
  HTML_ATTRIBUTE    -> marker sits inside an attribute value, e.g. value="MARKER"
  HTML_ATTRIBUTE_NOQUOTE -> inside an unquoted attribute value
  JS_STRING        -> marker sits inside a JS string literal in a <script> block
  JS_CODE          -> marker sits directly in JS code (rare, high severity)
  URL_CONTEXT       -> marker sits inside an href/src style URL
  COMMENT          -> marker landed inside an HTML comment (usually dead end)
  NOT_REFLECTED     -> marker didn't come back at all (encoded, stripped, filtered)
  ENCODED           -> marker came back but HTML-escaped (safe, but worth noting)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List


class Context(Enum):
    HTML_TEXT = "html_text"
    HTML_ATTRIBUTE = "html_attribute"
    HTML_ATTRIBUTE_NOQUOTE = "html_attribute_noquote"
    JS_STRING = "js_string"
    JS_CODE = "js_code"
    URL_CONTEXT = "url_context"
    COMMENT = "comment"
    ENCODED = "encoded"
    NOT_REFLECTED = "not_reflected"


@dataclass
class ContextMatch:
    context: Context
    snippet: str      # surrounding text for the report
    position: int


def _find_all(haystack: str, needle: str) -> List[int]:
    positions = []
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + 1
    return positions


def analyze(body: str, marker: str) -> List[ContextMatch]:
    """Return every context in which `marker` was reflected in `body`."""
    matches: List[ContextMatch] = []

    raw_positions = _find_all(body, marker)
    escaped = marker.replace("<", "&lt;").replace(">", "&gt;")
    escaped_positions = _find_all(body, escaped) if escaped != marker else []

    if not raw_positions and not escaped_positions:
        matches.append(ContextMatch(Context.NOT_REFLECTED, "", -1))
        return matches

    for pos in escaped_positions:
        snippet = body[max(0, pos - 30):pos + 30]
        matches.append(ContextMatch(Context.ENCODED, snippet, pos))

    for pos in raw_positions:
        window_start = max(0, pos - 200)
        before = body[window_start:pos]
        after = body[pos:pos + 200]
        snippet = body[max(0, pos - 30):pos + 30]

        ctx = _classify(before, after)
        matches.append(ContextMatch(ctx, snippet, pos))

    return matches


def _classify(before: str, after: str) -> Context:
    # Inside an HTML comment?
    last_comment_open = before.rfind("<!--")
    last_comment_close = before.rfind("-->")
    if last_comment_open > last_comment_close:
        return Context.COMMENT

    # Inside a <script> block -> check if we're in a JS string
    last_script_open = before.lower().rfind("<script")
    last_script_close = before.lower().rfind("</script>")
    if last_script_open > last_script_close:
        # crude but useful: count unescaped quotes since script start to see
        # if the marker sits inside an open string literal
        script_body = before[last_script_open:]
        single = script_body.count("'") - script_body.count("\\'")
        double = script_body.count('"') - script_body.count('\\"')
        if single % 2 == 1 or double % 2 == 1:
            return Context.JS_STRING
        return Context.JS_CODE

    # Inside a tag (between < and the next >)?
    last_tag_open = before.rfind("<")
    last_tag_close = before.rfind(">")
    if last_tag_open > last_tag_close:
        # we're inside a tag, e.g. <input value=MARKER ...>
        tag_fragment = before[last_tag_open:]

        # is it inside an attribute value?
        attr_match = re.search(r'=\s*"([^"]*)$', tag_fragment)
        if attr_match:
            return Context.HTML_ATTRIBUTE
        attr_match_sq = re.search(r"=\s*'([^']*)$", tag_fragment)
        if attr_match_sq:
            return Context.HTML_ATTRIBUTE
        attr_match_uq = re.search(r'=\s*[^\s"\'>]*$', tag_fragment)
        if attr_match_uq:
            # could be a URL-bearing attribute (href/src)
            if re.search(r'(href|src|action)\s*=\s*[^\s"\'>]*$',
                         tag_fragment, re.IGNORECASE):
                return Context.URL_CONTEXT
            return Context.HTML_ATTRIBUTE_NOQUOTE

    return Context.HTML_TEXT
