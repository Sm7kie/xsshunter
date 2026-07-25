"""Generates a markdown report from a ScanReport."""
from __future__ import annotations

from datetime import datetime, timezone

from core.scanner import ScanReport


def render_markdown(report: ScanReport) -> str:
    lines = []
    lines.append(f"# XSSHunter Report\n")
    lines.append(f"**Target:** {report.target}  ")
    lines.append(f"**Scanned:** {datetime.now(timezone.utc).isoformat()}  ")
    lines.append(f"**Input points tested:** {report.input_points_tested}  ")
    lines.append(f"**Confirmed findings:** {len(report.findings)}\n")

    if not report.findings:
        lines.append("No confirmed XSS found. (Note: this tool only reports "
                      "*browser-verified* execution - it will not flag a "
                      "reflection that didn't actually run.)\n")
        return "\n".join(lines)

    for i, finding in enumerate(report.findings, 1):
        lines.append(f"## Finding {i}: {finding.input_point.param}\n")
        lines.append(f"- **Method:** {finding.input_point.method}")
        lines.append(f"- **URL/Action:** {finding.input_point.action}")
        lines.append(f"- **Parameter:** `{finding.input_point.param}`")
        lines.append(f"- **Context:** {finding.context.value}")
        lines.append(f"- **Payload:** `{finding.payload}`")
        lines.append(f"- **Proof URL:** {finding.proof_url}")
        lines.append(f"- **Severity:** High (confirmed JS execution)\n")

    return "\n".join(lines)
