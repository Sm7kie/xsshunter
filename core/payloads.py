"""
Payload engine.

Loads context -> payload mappings and hands back candidates for a given
Context enum value. All payloads set `window.__xsshunter_hit = true`
instead of alert()/confirm() — that global flag is what verifier.py
checks for via Playwright, which is far more reliable than screen-scraping
for a dialog box and works headlessly.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from core.context import Context

_PAYLOAD_FILE = Path(__file__).parent.parent / "payloads" / "contexts.json"

# Contexts that are structurally incapable of executing JS on their own
# and aren't worth generating candidate payloads for.
_NON_EXECUTABLE = {Context.COMMENT, Context.ENCODED, Context.NOT_REFLECTED}


def _load() -> Dict[str, List[str]]:
    with open(_PAYLOAD_FILE) as f:
        return json.load(f)


_PAYLOADS = _load()


def candidates_for(context: Context) -> List[str]:
    """Return payload strings worth trying for a given reflection context."""
    if context in _NON_EXECUTABLE:
        return []
    return _PAYLOADS.get(context.value, [])
