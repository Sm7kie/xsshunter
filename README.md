# XSSHunter

A context-aware XSS scanner that confirms exploitation instead of guessing.

Most scanners flag anything that looks reflected. XSSHunter instead:
1. Crawls the target to find every input point (forms, URL params)
2. Parses the response to figure out exactly *where* your input landed (HTML body, tag attribute, JS string, URL context)
3. Picks a payload built for that specific context
4. Loads the result in a real headless browser and checks whether the payload **actually executed** — not just whether it appears in the response

That last step is what keeps false positives near zero: a reflected `<script>` tag that got HTML-escaped, or landed inside a comment, never gets reported as a hit.

## Status
Early scaffold — crawler + context analyzer are functional. Execution-proof layer (Playwright) and DOM-sink scanner are next.

## Why this exists
Built as a learning/portfolio project after studying how XSStrike, Dalfox, and xss_vibes approach the problem. This is an independent implementation — no code copied from those projects — designed to try a different core idea: browser-verified execution as the ground truth for "vulnerable," rather than pattern matching on the response body.

## Legal / usage
For authorized testing only — your own apps, or targets you have explicit written permission to test (e.g. bug bounty scope). Unauthorized scanning of systems you don't own or have permission to test is illegal in most jurisdictions.

## Install
```bash
git clone https://github.com/Sm7kie/xsshunter.git
cd xsshunter
pip install -r requirements.txt
```

## Usage
```bash
python xsshunter.py --target https://example.com --i-own-this-target
```

## Architecture
```
xsshunter/
├── core/
│   ├── crawler.py       # finds input points (forms, URL params)
│   ├── context.py       # classifies where input reflects in the response
│   ├── payloads.py       # context -> payload mapping
│   ├── verifier.py       # (next) headless browser execution proof
│   └── scanner.py       # ties it all together
├── payloads/
│   └── contexts.json    # payload templates per context
├── reports/             # generated scan reports land here
├── tests/
├── xsshunter.py         # CLI entrypoint
└── requirements.txt
```
