import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.context import analyze, Context

MARKER = "<XSSHUNTER_9f8a>"

cases = [
    (f'<p>Hello {MARKER}, welcome</p>', Context.HTML_TEXT),
    (f'<input type="text" value="{MARKER}">', Context.HTML_ATTRIBUTE),
    (f'<input type=text value={MARKER}>', Context.HTML_ATTRIBUTE_NOQUOTE),
    (f'<a href={MARKER}>link</a>', Context.URL_CONTEXT),
    (f'<script>var x = "{MARKER}";</script>', Context.JS_STRING),
    (f'<script>var x = {MARKER};</script>', Context.JS_CODE),
    (f'<!-- {MARKER} -->', Context.COMMENT),
    (f'<p>{MARKER.replace("<", "&lt;").replace(">", "&gt;")}</p>', Context.ENCODED),
    ('<p>nothing here</p>', Context.NOT_REFLECTED),
]

passed = 0
for body, expected in cases:
    results = analyze(body, MARKER)
    got = results[0].context
    status = "PASS" if got == expected else "FAIL"
    if got == expected:
        passed += 1
    print(f"[{status}] expected={expected.value:25s} got={got.value:25s}")

print(f"\n{passed}/{len(cases)} passed")
