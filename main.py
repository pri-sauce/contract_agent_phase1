"""
main.py — Contract Agent CLI
=============================

REVIEW COMMANDS
  python main.py rv contract.pdf              Review any contract
  python main.py rv contract.pdf -o reports/  Custom output folder
  python main.py rv contract.pdf -f both      Save markdown + JSON
  python main.py rv contract.pdf --no-store   Don't save to RAG DB
  python main.py demo                         Run built-in sample NDA

HISTORY COMMANDS
  python main.py list                         Show all reviewed contracts
  python main.py list --risk HIGH             Filter by risk level
  python main.py show acme_nda_2025           Show a past review

KNOWLEDGE BASE COMMANDS
  python main.py kb-init                      Load playbook.yaml into DB
  python main.py kb-stats                     Show DB collection sizes
  python main.py kb-reset                     Wipe and rebuild DB
  python main.py kb-add-legal <topic> <text>  Add a legal note
  python main.py kb-add-clause <type> <file>  Add approved clause template

SYSTEM
  python main.py check                        Verify Ollama + models
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from loguru import logger

logger.remove()
logger.add(sys.stderr, level="WARNING")
(PROJECT_ROOT / "data").mkdir(exist_ok=True)
logger.add(str(PROJECT_ROOT / "data" / "agent.log"), level="DEBUG", rotation="10 MB")

app = typer.Typer(
    name="contract-agent",
    help="Local Contract Review & CLM Agent — powered by Ollama + ChromaDB",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()

REVIEWS_DIR = PROJECT_ROOT / "data" / "reviews"
UPLOADS_DIR = PROJECT_ROOT / "data" / "uploads"
INDEX_PATH  = PROJECT_ROOT / "data" / "review_index.json"


# ==================================================================
# REVIEW COMMANDS
# ==================================================================

@app.command()
def rv(
    file: Path = typer.Argument(..., help="Contract file to review (PDF, DOCX, or TXT)"),
    output: Path = typer.Option(None, "--output", "-o", help="Output directory (default: data/reviews/)"),
    format: str = typer.Option("markdown", "--format", "-f", help="Output format: markdown | json | both"),
    store: bool = typer.Option(True, "--store/--no-store", help="Store clauses in RAG DB for future reviews"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Print full clause details to terminal"),
):
    """
    Review a contract file. The main command.

    \b
    Examples:
      python main.py rv vendor_nda.pdf
      python main.py rv contract.docx --format both --verbose
      python main.py rv agreement.txt -o ./my_reports --no-store
    """
    if not file.exists():
        alt = UPLOADS_DIR / file
        if alt.exists():
            file = alt
        else:
            console.print(f"[red]File not found:[/red] {file}")
            console.print(f"[dim]Tip: place contracts in {UPLOADS_DIR} and just pass the filename[/dim]")
            raise typer.Exit(1)

    _run_review(file, output_dir=output, fmt=format, store_in_rag=store, verbose=verbose)


@app.command()
def demo():
    """Run a review on the built-in sample NDA (for testing). For real contracts use: rv"""
    console.print(Panel(
        "[bold]Demo Mode[/bold] — Built-in sample NDA\n"
        "[dim]To review your own contract: python main.py rv contract.pdf[/dim]",
        expand=False,
    ))
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    demo_path = UPLOADS_DIR / "sample_nda_demo.txt"
    demo_path.write_text(_create_sample_nda(), encoding="utf-8")
    console.print(f"[dim]Sample NDA written to {demo_path}[/dim]\n")
    _run_review(demo_path, output_dir=None, fmt="markdown", store_in_rag=True, verbose=True)


# ==================================================================
# HISTORY / CLM COMMANDS
# ==================================================================

@app.command(name="list")
def list_reviews(
    risk: str = typer.Option(None, "--risk", "-r", help="Filter: HIGH | MEDIUM | LOW"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max rows to show"),
):
    """
    List all previously reviewed contracts.

    \b
    Examples:
      python main.py list
      python main.py list --risk HIGH
    """
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    index = _load_review_index()

    if not index:
        console.print("[yellow]No reviewed contracts yet.[/yellow]")
        console.print("[dim]Run: python main.py rv <file>[/dim]")
        return

    entries = list(index.values())
    if risk:
        entries = [e for e in entries if e.get("overall_risk", "").upper() == risk.upper()]
    entries = sorted(entries, key=lambda x: x.get("reviewed_at", ""), reverse=True)[:limit]

    if not entries:
        console.print(f"[yellow]No reviews with risk level: {risk}[/yellow]")
        return

    RISK_COLORS = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "blue"}
    table = Table(show_header=True, header_style="bold", show_lines=False)
    table.add_column("#",        style="dim", width=4)
    table.add_column("Contract", min_width=28)
    table.add_column("Type",     width=10)
    table.add_column("Risk",     width=8)
    table.add_column("H/M/L",   width=9)
    table.add_column("Parties",  min_width=22)
    table.add_column("Reviewed", width=12)

    for i, e in enumerate(entries, 1):
        rl = e.get("overall_risk", "?")
        c  = RISK_COLORS.get(rl, "white")
        hml = f"{e.get('high_risk_count',0)}/{e.get('medium_risk_count',0)}/{e.get('low_risk_count',0)}"
        parties = ", ".join(e.get("parties", []))[:28]
        table.add_row(
            str(i),
            e.get("filename", "?"),
            e.get("contract_type", "?"),
            f"[{c}]{rl}[/{c}]",
            hml,
            parties or "[dim]Unknown[/dim]",
            e.get("reviewed_at", "")[:10],
        )

    console.print(f"\n[bold]Reviewed Contracts[/bold] — {len(entries)} shown\n")
    console.print(table)
    console.print(f"\n[dim]To view full review: python main.py show <contract-id>[/dim]")


@app.command()
def show(
    contract_id: str = typer.Argument(..., help="Contract ID or filename stem"),
    risk_filter: str = typer.Option(None, "--risk", "-r", help="Only show clauses at this risk level"),
):
    """
    Show the full review for a previously reviewed contract.

    \b
    Examples:
      python main.py show vendor_nda
      python main.py show vendor_nda --risk HIGH
    """
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)

    matches = list(REVIEWS_DIR.glob(f"{contract_id}*.json"))
    if not matches:
        matches = [p for p in REVIEWS_DIR.glob("*.json") if contract_id.lower() in p.stem.lower()]

    if not matches:
        console.print(f"[red]No review found for:[/red] {contract_id}")
        console.print("[dim]Run 'python main.py list' to see available reviews[/dim]")
        raise typer.Exit(1)

    data = json.loads(sorted(matches)[-1].read_text(encoding="utf-8"))
    _print_full_review(data, risk_filter=risk_filter)


# ==================================================================
# Core Review Runner
# ==================================================================

def _run_review(file: Path, output_dir=None, fmt="markdown", store_in_rag=True, verbose=False):
    from core.review_pipeline import review_pipeline
    from utils.report_exporter import exporter

    report = review_pipeline.review_file(file)

    out_dir = output_dir or REVIEWS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    stem      = file.stem
    timestamp = report.reviewed_at[:10]
    base_name = f"{stem}_{timestamp}"

    saved = []
    md_path = out_dir / f"{base_name}.md"
    exporter.export_markdown(report, md_path)
    saved.append(md_path)

    if fmt in ("json", "both"):
        json_path = out_dir / f"{base_name}.json"
        exporter.export_json(report, json_path)
        saved.append(json_path)

    # Always write JSON to REVIEWS_DIR for list/show commands
    index_json = REVIEWS_DIR / f"{base_name}.json"
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    if not index_json.exists():
        exporter.export_json(report, index_json)

    if store_in_rag:
        _store_review_in_rag(report, base_name)

    _update_review_index(report, base_name, index_json)

    console.print()
    _print_report_summary(report, verbose=verbose)

    console.print(f"\n[bold]Saved:[/bold]")
    for f in saved:
        console.print(f"  [cyan]{f}[/cyan]")

    if store_in_rag:
        console.print(f"\n[dim]✓ {report.total_clauses} clauses stored in RAG DB for future reviews[/dim]")


def _store_review_in_rag(report, contract_id: str):
    try:
        from rag.knowledge_base import knowledge_base
        clauses_data = [
            {
                "text":        r.original_text,
                "clause_type": r.clause_type,
                "risk_level":  r.risk_level,
                "heading":     r.heading or "",
            }
            for r in report.clause_reviews
            if r.original_text and len(r.original_text.strip()) > 30
        ]
        if clauses_data:
            knowledge_base.add_contract_clauses(contract_id, clauses_data)
    except Exception as e:
        logger.warning(f"RAG storage failed (non-fatal): {e}")


# ==================================================================
# Review Index
# ==================================================================

def _load_review_index() -> dict:
    if INDEX_PATH.exists():
        try:
            return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _update_review_index(report, contract_id: str, json_path: Path):
    index = _load_review_index()
    index[contract_id] = {
        "contract_id":      contract_id,
        "filename":         report.filename,
        "reviewed_at":      report.reviewed_at,
        "overall_risk":     report.overall_risk,
        "recommendation":   report.recommendation,
        "contract_type":    report.metadata.get("contract_type", "Unknown"),
        "parties":          report.metadata.get("parties", []),
        "governing_law":    report.metadata.get("governing_law", ""),
        "total_clauses":    report.total_clauses,
        "high_risk_count":  report.high_risk_count,
        "medium_risk_count":report.medium_risk_count,
        "low_risk_count":   report.low_risk_count,
        "json_path":        str(json_path),
    }
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


# ==================================================================
# Display Helpers
# ==================================================================

def _print_report_summary(report, verbose=False):
    RISK_COLORS = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "green"}
    rc = RISK_COLORS.get(report.overall_risk, "white")

    console.print(Panel(
        f"[bold {rc}]{report.overall_risk} RISK[/bold {rc}]  |  "
        f"Recommendation: [bold]{report.recommendation}[/bold]",
        title=report.filename, expand=False,
    ))

    table = Table(show_header=True, header_style="bold", show_lines=False)
    table.add_column("Risk Level")
    table.add_column("Count", justify="right")
    table.add_row("[red]HIGH[/red]",           str(report.high_risk_count))
    table.add_row("[yellow]MEDIUM[/yellow]",   str(report.medium_risk_count))
    table.add_row("[blue]LOW[/blue]",          str(report.low_risk_count))
    table.add_row("[green]ACCEPTABLE[/green]", str(report.acceptable_count))
    console.print(table)

    high = [r for r in report.clause_reviews if r.risk_level == "HIGH"]
    if high:
        console.print("\n[bold red]High Risk Clauses:[/bold red]")
        for r in high:
            heading = r.heading or r.clause_type or r.clause_id
            tag = " [dim](escalated)[/dim]" if getattr(r, "escalated", False) else ""
            console.print(f"  [red]●[/red] [bold]{heading}[/bold]{tag}")
            for issue in r.issues[:2]:
                console.print(f"    [dim]{issue[:130]}[/dim]")
            redlines = getattr(r, "redlines", [])
            if redlines:
                rd = redlines[0]
                replace_txt = rd.get('replace', '')
                with_txt = rd.get('with', '')
                console.print(f"    [dim]Replace:[/dim] [red]{replace_txt[:100]}[/red]")
                console.print(f"    [dim]With:   [/dim] [green]{with_txt[:100]}[/green]")

    medium = [r for r in report.clause_reviews if r.risk_level == "MEDIUM"]
    if medium and verbose:
        console.print("\n[bold yellow]Medium Risk Clauses:[/bold yellow]")
        for r in medium:
            heading = r.heading or r.clause_type or r.clause_id
            console.print(f"  [yellow]●[/yellow] [bold]{heading}[/bold]")
            for issue in r.issues[:1]:
                console.print(f"    [dim]{issue[:130]}[/dim]")

    if report.executive_summary:
        console.print(f"\n[bold]Executive Summary:[/bold]")
        s = report.executive_summary
        console.print(s[:800] + ("..." if len(s) > 800 else ""))


def _print_full_review(data: dict, risk_filter=None):
    RISK_COLORS = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "blue", "ACCEPTABLE": "green"}
    risk = data.get("overall_risk", "?")
    rc   = RISK_COLORS.get(risk, "white")
    meta = data.get("metadata", {})

    console.print(Panel(
        f"[bold {rc}]{risk} RISK[/bold {rc}]  |  {data.get('recommendation','')}",
        title=data.get("filename", "?"),
        subtitle=f"Reviewed: {data.get('reviewed_at','')[:10]}",
        expand=False,
    ))

    t = Table(show_header=False, box=None, padding=(0,2))
    t.add_column("k", style="dim"); t.add_column("v")
    t.add_row("Type",    meta.get("contract_type","?"))
    t.add_row("Parties", ", ".join(meta.get("parties",[])))
    t.add_row("Law",     meta.get("governing_law","?"))
    console.print(t); console.print()

    reviews = data.get("clause_reviews", [])
    if risk_filter:
        reviews = [r for r in reviews if r.get("risk_level","").upper() == risk_filter.upper()]

    for r in reviews:
        rl = r.get("risk_level","?")
        rc2 = RISK_COLORS.get(rl, "white")
        heading = r.get("heading") or r.get("clause_type") or r.get("clause_id","?")
        console.print(f"[{rc2}]{'━'*60}[/{rc2}]")
        console.print(f"[bold {rc2}]{rl}[/bold {rc2}]  {heading}  [dim]({r.get('clause_type','')})[/dim]")
        for issue in r.get("issues", []):
            console.print(f"  [dim]Issue:[/dim] {issue}")
        redline = r.get("redline_suggestion","")
        if redline and redline != "No changes needed":
            console.print(f"  [dim]Redline:[/dim] {redline[:200]}")
        console.print()

    if data.get("executive_summary"):
        console.print(Panel(data["executive_summary"], title="Executive Summary", expand=False))



# ==================================================================
# DRAFTING COMMANDS
# ==================================================================

@app.command()
def df(
    overview: Path = typer.Argument(..., help="Path to the contract overview YAML file"),
    output: Path = typer.Option(None, "--output", "-o", help="Output directory (default: data/drafts/)"),
    format: str = typer.Option("txt", "--format", "-f", help="Output format: txt | md | json | all"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Print full contract to terminal after drafting"),
):
    """
    Draft a contract from an overview file.

    \b
    Workflow:
      1. Create an overview file:   python main.py new-overview my_nda.yaml
      2. Edit the overview file with your deal details
      3. Draft the contract:        python main.py df my_nda.yaml

    \b
    Examples:
      python main.py df overview.yaml
      python main.py df nda_overview.yaml --format all --verbose
      python main.py df deal.yaml -o ./contracts
    """
    if not overview.exists():
        # Check uploads dir
        alt = UPLOADS_DIR / overview
        if alt.exists():
            overview = alt
        else:
            console.print(f"[red]Overview file not found:[/red] {overview}")
            console.print(f"[dim]Create one with: python main.py new-overview {overview.stem}.yaml[/dim]")
            raise typer.Exit(1)

    from core.draft_pipeline import draft_pipeline
    from utils.draft_exporter import draft_exporter

    # Run the draft
    contract = draft_pipeline.draft_from_overview(overview)

    # Output directory
    out_dir = output or (PROJECT_ROOT / "data" / "drafts")
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = f"{overview.stem}_{contract.drafted_at[:10]}"
    saved = []

    if format in ("txt", "all"):
        p = out_dir / f"{stem}.txt"
        draft_exporter.export_txt(contract, p)
        saved.append(p)

    if format in ("md", "all"):
        p = out_dir / f"{stem}.md"
        draft_exporter.export_markdown(contract, p)
        saved.append(p)

    if format in ("json", "all"):
        p = out_dir / f"{stem}.json"
        draft_exporter.export_json(contract, p)
        saved.append(p)

    # If no format matched, default to txt
    if not saved:
        p = out_dir / f"{stem}.txt"
        draft_exporter.export_txt(contract, p)
        saved.append(p)

    # Print summary
    console.print()
    console.print(Panel(
        f"[bold green]Draft Complete[/bold green]  |  "
        f"{len(contract.clauses)} clauses  |  "
        f"{len(contract.full_text.split())} words",
        title=f"{contract.contract_type} — {contract.party_a.get('name')} ↔ {contract.party_b.get('name')}",
        expand=False,
    ))

    if contract.warnings:
        console.print(f"\n[yellow]⚠ Playbook deviations ({len(contract.warnings)}):[/yellow]")
        for w in contract.warnings[:5]:
            console.print(f"  [dim]{w}[/dim]")

    console.print(f"\n[bold]Saved:[/bold]")
    for f in saved:
        console.print(f"  [cyan]{f}[/cyan]")

    if verbose and contract.full_text:
        console.print("\n[bold]Contract Preview:[/bold]")
        preview = contract.full_text[:2000]
        console.print(preview + ("..." if len(contract.full_text) > 2000 else ""))


@app.command(name="new-overview")
def new_overview(
    filename: str = typer.Argument("overview.yaml", help="Output filename for the overview"),
    contract_type: str = typer.Option("NDA", "--type", "-t",
                                       help="Contract type: NDA | MSA | SOW | SaaS | Employment"),
):
    """
    Create a new contract overview file pre-filled for the given contract type.

    \b
    Examples:
      python main.py new-overview my_nda.yaml
      python main.py new-overview vendor_msa.yaml --type MSA
      python main.py new-overview saas_deal.yaml --type SaaS
    """
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    # Determine output path
    out_path = Path(filename)
    if not out_path.is_absolute():
        out_path = UPLOADS_DIR / filename

    if out_path.exists():
        overwrite = typer.confirm(f"{out_path} already exists. Overwrite?")
        if not overwrite:
            raise typer.Exit(0)

    # Copy the template and customise for contract type
    template_path = PROJECT_ROOT / "data" / "draft_overview_template.yaml"
    if not template_path.exists():
        console.print(f"[red]Template not found at {template_path}[/red]")
        raise typer.Exit(1)

    template_text = template_path.read_text(encoding="utf-8")

    # Patch the contract_type line
    import re as _re
    template_text = _re.sub(
        r'contract_type:.*',
        f'contract_type: "{contract_type}"',
        template_text,
    )

    # Patch which clauses are active based on type
    TYPE_CLAUSES = {
        "NDA": {
            "confidentiality": True, "purpose": True, "definitions": True,
            "term_termination": True, "permitted_disclosures": True,
            "intellectual_property": True, "limitation_of_liability": True,
            "indemnification": False, "payment": False, "governing_law": True,
            "dispute_resolution": True, "entire_agreement": True,
            "notices": True, "amendment": True, "data_privacy": False,
        },
        "MSA": {
            "confidentiality": True, "purpose": True, "definitions": True,
            "term_termination": True, "intellectual_property": True,
            "limitation_of_liability": True, "indemnification": True,
            "payment": True, "governing_law": True, "dispute_resolution": True,
            "entire_agreement": True, "notices": True, "amendment": True,
            "data_privacy": True, "permitted_disclosures": True,
        },
        "SOW": {
            "purpose": True, "definitions": True, "payment": True,
            "intellectual_property": True, "term_termination": True,
            "limitation_of_liability": True, "confidentiality": True,
            "governing_law": True, "entire_agreement": True,
            "indemnification": False, "notices": False, "amendment": True,
            "data_privacy": False, "dispute_resolution": True,
        },
        "SaaS": {
            "confidentiality": True, "purpose": True, "definitions": True,
            "term_termination": True, "intellectual_property": True,
            "limitation_of_liability": True, "indemnification": True,
            "payment": True, "governing_law": True, "dispute_resolution": True,
            "entire_agreement": True, "notices": True, "amendment": True,
            "data_privacy": True, "permitted_disclosures": True,
        },
    }

    if contract_type.upper() in TYPE_CLAUSES:
        clauses = TYPE_CLAUSES[contract_type.upper()]
        # Rebuild the clauses block in YAML
        clause_lines = ["clauses:"]
        for name, enabled in clauses.items():
            val = "true" if enabled else "false"
            padding = " " * (22 - len(name))
            comment = "  # Not typical for " + contract_type if not enabled else ""
            clause_lines.append(f"  {name}:{padding}{val}{comment}")
        new_clauses = "\n".join(clause_lines)

        # Replace old clauses block
        template_text = _re.sub(
            r"clauses:.*?(?=\n# --|\noutput:)",
            new_clauses + "\n\n",
            template_text,
            flags=_re.DOTALL,
        )

    out_path.write_text(template_text, encoding="utf-8")

    console.print(f"[green]✓ Created overview:[/green] {out_path}")
    console.print(f"\n[dim]Next steps:[/dim]")
    console.print(f"  1. Edit the file: [cyan]{out_path}[/cyan]")
    console.print(f"     → Fill in party names, purpose, governing law")
    console.print(f"     → Add special instructions for this deal")
    console.print(f"  2. Draft the contract:")
    console.print(f"     [cyan]python main.py df {out_path.name}[/cyan]")

# ==================================================================
# Knowledge Base Commands
# ==================================================================

@app.command()
def kb_init():
    """Load playbook.yaml into the knowledge base. Run once after setup."""
    console.print(Panel("Knowledge Base — Initialize", expand=False))
    from rag.knowledge_base import knowledge_base
    with console.status("[bold]Loading playbook...[/bold]"):
        n = knowledge_base.load_playbook()
    if n > 0:
        console.print(f"[green]✓ Loaded {n} playbook entries[/green]")
        for name, count in knowledge_base.get_stats().items():
            console.print(f"  [dim]{name:20s}[/dim] {count}")
    else:
        console.print("[yellow]No entries loaded. Check data/knowledge_base/playbook.yaml[/yellow]")


@app.command()
def kb_stats():
    """Show document counts for each knowledge base collection."""
    console.print(Panel("Knowledge Base — Stats", expand=False))
    from rag.knowledge_base import knowledge_base
    stats = knowledge_base.get_stats()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Collection")
    table.add_column("Documents", justify="right")
    table.add_column("Status")

    for name, count in stats.items():
        c = "green" if count > 0 else "dim"
        status = "[green]Populated[/green]" if count > 0 else "[dim]Empty[/dim]"
        table.add_row(f"[{c}]{name}[/{c}]", str(count), status)

    console.print(table)
    console.print(f"\n[dim]Contracts in review index: {len(_load_review_index())}[/dim]")


@app.command()
def kb_add_legal(
    topic: str = typer.Argument(...),
    content: str = typer.Argument(...),
    jurisdiction: str = typer.Option("general", "--jurisdiction", "-j"),
):
    """Add a legal note to the knowledge base."""
    from rag.knowledge_base import knowledge_base
    knowledge_base.add_legal_note(topic=topic, content=content, jurisdiction=jurisdiction)
    console.print(f"[green]✓ Added:[/green] {topic} [dim]({jurisdiction})[/dim]")


@app.command()
def kb_add_clause(
    clause_type: str = typer.Argument(...),
    file: Path = typer.Argument(...),
    label: str = typer.Option("standard", "--label", "-l"),
):
    """Add an approved clause template to the library."""
    if not file.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)
    from rag.knowledge_base import knowledge_base
    knowledge_base.add_clause_template(
        clause_type=clause_type,
        clause_text=file.read_text(encoding="utf-8"),
        label=label,
    )
    console.print(f"[green]✓ Added {label} template for {clause_type}[/green]")


@app.command()
def kb_reset():
    """Wipe and rebuild the knowledge base. Use if you see ChromaDB errors."""
    import shutil
    console.print(Panel("Knowledge Base — Reset", expand=False))
    db_path = PROJECT_ROOT / "data" / "knowledge_base" / "chromadb"
    if db_path.exists():
        shutil.rmtree(db_path)
        console.print(f"[yellow]Wiped: {db_path}[/yellow]")
    from rag.knowledge_base import KnowledgeBase
    n = KnowledgeBase().load_playbook()
    console.print(f"[green]✓ Rebuilt with {n} playbook entries[/green]")


# ==================================================================
# System Check
# ==================================================================

@app.command()
def check():
    """Verify Ollama is running and required models are available."""
    console.print(Panel("System Check", expand=False))
    from core.llm import llm
    if llm.check_connection():
        console.print("[green]✓ Ollama connected[/green]")
        r = llm.fast_generate("Reply with exactly: SYSTEM OK",
                               system="Follow instructions exactly.")
        console.print(f"[green]✓ LLM working[/green] [dim]({r.strip()[:30]})[/dim]")
        console.print("\n[bold green]System ready.[/bold green]")
        console.print("\n[dim]Quick start:[/dim]")
        console.print("  [cyan]python main.py rv your_contract.pdf[/cyan]")
    else:
        console.print("[red]✗ Failed[/red]")
        console.print("  1. [cyan]ollama serve[/cyan]")
        console.print("  2. [cyan]ollama pull llama3.2:3b[/cyan]")
        console.print("  3. [cyan]ollama pull nomic-embed-text[/cyan]")
        raise typer.Exit(1)


# ==================================================================
# Sample NDA
# ==================================================================

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


if __name__ == "__main__":
    app()