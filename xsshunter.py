"""
XSSHunter CLI.

Usage:
    python xsshunter.py --target https://example.com --i-own-this-target
    python xsshunter.py --target https://example.com --i-own-this-target -o report.md -v
"""
import sys
import click

from core.scanner import Scanner
from core.report import render_markdown


@click.command()
@click.option("--target", required=True, help="Target base URL, e.g. https://example.com")
@click.option("--i-own-this-target", is_flag=True, default=False,
              help="Required confirmation that you have authorization to test this target.")
@click.option("--max-pages", default=50, show_default=True, help="Max pages to crawl.")
@click.option("-o", "--output", default=None, help="Write markdown report to this file.")
@click.option("-v", "--verbose", is_flag=True, default=False, help="Verbose scan progress.")
def main(target, i_own_this_target, max_pages, output, verbose):
    if not i_own_this_target:
        click.echo(
            "\nRefusing to scan without authorization confirmation.\n"
            "Pass --i-own-this-target only if you own this target or have\n"
            "explicit written permission to test it (e.g. bug bounty scope,\n"
            "your own local test lab like DVWA/Juice Shop).\n",
            err=True,
        )
        sys.exit(1)

    click.echo(f"[*] Starting scan of {target}\n")
    scanner = Scanner(target, max_pages=max_pages, verbose=verbose)
    report = scanner.run()

    click.echo(f"\n[*] Done. {len(report.findings)} confirmed finding(s) "
               f"out of {report.input_points_tested} input point(s) tested.\n")

    markdown = render_markdown(report)
    if output:
        with open(output, "w") as f:
            f.write(markdown)
        click.echo(f"[*] Report written to {output}")
    else:
        click.echo(markdown)


if __name__ == "__main__":
    main()
