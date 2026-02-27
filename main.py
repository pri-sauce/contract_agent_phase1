"""
main.py — Contract Agent CLI
The main entry point for Phase 1.

Usage:
  python main.py check          → Verify Ollama connection and models
  python main.py review <file>  → Review a contract file
  python main.py demo           → Run a demo with a sample contract
"""

import sys  
from pathlib import Path

# ---------------------------------------------------------------
# IMPORTANT: Add project root to sys.path FIRST.
# This fixes "No module named 'core'" on Windows, macOS, and Linux
# regardless of what directory you run the script from.
# ---------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from loguru import logger

# Configure logging — use absolute path so it works from any directory
logger.remove()
logger.add(sys.stderr, level="WARNING")
(PROJECT_ROOT / "data").mkdir(exist_ok=True)
logger.add(str(PROJECT_ROOT / "data" / "agent.log"), level="DEBUG", rotation="10 MB")

app = typer.Typer(
    name="contract-agent",
    help="Local Contract Review & Analysis Agent",
    add_completion=False,
)
console = Console()


# ------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------

@app.command()
def check():
    """Verify Ollama connection and required models are available."""
    console.print(Panel("System Check", expand=False))

    from core.llm import llm

    if llm.check_connection():
        console.print("[bold green]System ready. All models available.[/bold green]")
        console.print("\n[dim]Running quick test...[/dim]")
        response = llm.fast_generate(
            "Reply with exactly: SYSTEM OK",
            system="You are a test system. Follow instructions exactly."
        )
        console.print(f"[dim]Model response: {response.strip()[:50]}[/dim]")
        console.print("[green]LLM generation working.[/green]")
    else:
        console.print("[bold red]System check failed. See above for details.[/bold red]")
        console.print("\n[yellow]Fix steps:[/yellow]")
        console.print("1. Make sure Ollama is running: ollama serve")
        console.print("2. Pull required models: ollama pull llama3.2:3b")
        raise typer.Exit(1)


@app.command()
def review(
    file: Path = typer.Argument(..., help="Path to contract file (PDF, DOCX, or TXT)"),
    output_dir: Path = typer.Option(None, "--output", "-o", help="Output directory for report"),
    format: str = typer.Option("markdown", "--format", "-f", help="Output format: markdown | json | both"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed clause text"),
):
    """
    Review a contract file and generate a risk report.

    Examples:
        python main.py review contracts/vendor_agreement.pdf
        python main.py review contracts/nda.docx --format both
    """
    if not file.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)

    from core.review_pipeline import review_pipeline
    from utils.report_exporter import exporter

    report = review_pipeline.review_file(file)

    if output_dir is None:
        output_dir = PROJECT_ROOT / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = file.stem
    timestamp = report.reviewed_at[:10]
    base_name = f"{stem}_review_{timestamp}"

    saved_files = []
    if format in ("markdown", "both"):
        md_path = output_dir / f"{base_name}.md"
        exporter.export_markdown(report, md_path)
        saved_files.append(md_path)

    if format in ("json", "both"):
        json_path = output_dir / f"{base_name}.json"
        exporter.export_json(report, json_path)
        saved_files.append(json_path)

    console.print()
    _print_report_summary(report, verbose)

    console.print(f"\n[bold]Reports saved to:[/bold]")
    for f in saved_files:
        console.print(f"  [cyan]{f}[/cyan]")


@app.command()
def demo():
    """Run a demo review using a built-in sample NDA contract."""
    console.print(Panel("Demo Mode - Sample NDA Review", expand=False))

    sample_contract = _create_sample_nda()
    demo_path = PROJECT_ROOT / "data" / "uploads" / "sample_nda_demo.txt"
    demo_path.parent.mkdir(parents=True, exist_ok=True)
    demo_path.write_text(sample_contract, encoding="utf-8")

    console.print(f"[dim]Created sample NDA at {demo_path}[/dim]\n")

    from core.review_pipeline import review_pipeline
    from utils.report_exporter import exporter

    report = review_pipeline.review_file(demo_path)

    output_dir = PROJECT_ROOT / "data" / "processed"
    output_dir.mkdir(exist_ok=True)
    md_path = output_dir / "sample_nda_review.md"
    exporter.export_markdown(report, md_path)

    console.print()
    _print_report_summary(report, verbose=True)
    console.print(f"\n[bold]Full report saved to:[/bold] [cyan]{md_path}[/cyan]")


# ------------------------------------------------------------------
# Display Helpers
# ------------------------------------------------------------------

def _print_report_summary(report, verbose: bool = False):
    risk_color = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "green"}.get(report.overall_risk, "white")

    console.print(Panel(
        f"[bold {risk_color}]{report.overall_risk} RISK[/bold {risk_color}]  |  "
        f"Recommendation: [bold]{report.recommendation}[/bold]",
        title=f"{report.filename}",
        expand=False,
    ))

    table = Table(show_header=True, header_style="bold")
    table.add_column("Risk Level")
    table.add_column("Count", justify="right")
    table.add_row("HIGH",       str(report.high_risk_count))
    table.add_row("MEDIUM",     str(report.medium_risk_count))
    table.add_row("LOW",        str(report.low_risk_count))
    table.add_row("ACCEPTABLE", str(report.acceptable_count))
    console.print(table)

    high_risk = [r for r in report.clause_reviews if r.risk_level == "HIGH"]
    if high_risk:
        console.print("\n[bold red]High Risk Clauses:[/bold red]")
        for r in high_risk:
            heading = r.heading or r.clause_type or r.clause_id
            console.print(f"  - [bold]{heading}[/bold]")
            for issue in r.issues[:2]:
                console.print(f"    [dim]{issue[:120]}[/dim]")

    if report.executive_summary:
        console.print(f"\n[bold]Executive Summary:[/bold]")
        console.print(report.executive_summary[:600] + ("..." if len(report.executive_summary) > 600 else ""))


def _create_sample_nda() -> str:
    return """MUTUAL NON-DISCLOSURE AGREEMENT

This Mutual Non-Disclosure Agreement ("Agreement") is entered into as of January 1, 2025,
between Acme Corporation, a Delaware corporation ("Company"), and Vendor Inc.,
a California corporation ("Vendor").

1. PURPOSE
The parties wish to explore a potential business relationship and may disclose confidential
information to each other for the purpose of evaluating such relationship ("Purpose").

2. CONFIDENTIAL INFORMATION
"Confidential Information" means any and all information disclosed by either party to the other,
in any form whatsoever, including but not limited to technical, financial, business, and
operational information.

3. OBLIGATIONS
Each party agrees to hold the other party's Confidential Information in strict confidence
and not to disclose it to any third party without prior written consent. This obligation
shall be perpetual and survive termination of this Agreement indefinitely.

4. PERMITTED DISCLOSURES
Notwithstanding the foregoing, the receiving party may disclose Confidential Information
to its employees who have a need to know, provided such employees are bound by
confidentiality obligations no less restrictive than those contained herein.

5. INTELLECTUAL PROPERTY
Any ideas, inventions, or improvements conceived by Vendor during the term of this
Agreement that relate in any way to Company's business shall be the exclusive property
of Company, whether or not developed using Company's Confidential Information.
Vendor hereby assigns all rights, title, and interest in such developments to Company.

6. LIMITATION OF LIABILITY
IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY INDIRECT, INCIDENTAL, OR
CONSEQUENTIAL DAMAGES. COMPANY'S TOTAL LIABILITY SHALL BE UNLIMITED.
VENDOR'S TOTAL LIABILITY SHALL NOT EXCEED ONE HUNDRED DOLLARS ($100).

7. TERM
This Agreement shall commence on the Effective Date and continue for a period of
ten (10) years, automatically renewing for successive one-year periods unless
terminated by either party upon one (1) day written notice.

8. GOVERNING LAW
This Agreement shall be governed by the laws of the Cayman Islands, and any disputes
shall be resolved exclusively by arbitration in the Cayman Islands.

9. ENTIRE AGREEMENT
This Agreement constitutes the entire agreement between the parties with respect to
its subject matter and supersedes all prior agreements.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the date first written above.

ACME CORPORATION                    VENDOR INC.

By: _______________________         By: _______________________
Name:                               Name:
Title:                              Title:
Date:                               Date:
"""


# ------------------------------------------------------------------
# Entry Point
# ------------------------------------------------------------------

if __name__ == "__main__":
    app()
