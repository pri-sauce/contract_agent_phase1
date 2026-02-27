"""
core/review_pipeline.py — Contract Review Pipeline
The main orchestration logic for Phase 1.

Flow:
  ParsedDocument → Clauses → Metadata → Per-clause review → Summary Report
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from typing import Optional

from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from core.llm import llm
from core.config import config
from ingestion.parser import parser, ParsedDocument
from ingestion.segmenter import segmenter, Clause
from prompts.review_prompts import (
    SYSTEM_CONTRACT_REVIEWER,
    SYSTEM_METADATA_EXTRACTOR,
    prompt_extract_metadata,
    prompt_classify_clause,
    prompt_review_clause,
    prompt_contract_summary,
)

console = Console()


# ------------------------------------------------------------------
# Output Data Models
# ------------------------------------------------------------------

@dataclass
class ClauseReview:
    """Review result for a single clause."""
    clause_id: str
    number: str
    heading: str
    clause_type: str
    risk_level: str         # HIGH | MEDIUM | LOW | ACCEPTABLE
    issues: list[str] = field(default_factory=list)
    redline_suggestion: str = ""
    reasoning: str = ""
    original_text: str = ""


@dataclass
class ContractReviewReport:
    """Complete review report for a contract."""
    filename: str
    reviewed_at: str
    metadata: dict
    total_clauses: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    acceptable_count: int
    clause_reviews: list[ClauseReview] = field(default_factory=list)
    executive_summary: str = ""
    recommendation: str = ""   # Sign | Negotiate | Do Not Sign

    @property
    def overall_risk(self) -> str:
        if self.high_risk_count > 0:
            return "HIGH"
        elif self.medium_risk_count > 2:
            return "MEDIUM"
        else:
            return "LOW"


# ------------------------------------------------------------------
# Review Pipeline
# ------------------------------------------------------------------

class ReviewPipeline:
    """
    Orchestrates the full contract review process.
    Phase 1: Parses → Segments → Reviews each clause → Generates report
    Phase 2 addition: Will inject RAG context into each clause review
    """

    def review_file(self, file_path: str | Path) -> ContractReviewReport:
        """
        Full pipeline: file path → complete review report.
        This is the main entry point.
        """
        path = Path(file_path)
        console.print(f"\n[bold cyan]📄 Contract Review Agent[/bold cyan]")
        console.print(f"[dim]File: {path.name}[/dim]\n")

        # Step 1: Parse document
        with console.status("[bold]Parsing document...[/bold]"):
            doc = parser.parse(path)
            console.print(f"[green]✓[/green] Parsed: {doc.word_count} words, {len(doc.pages)} pages")

        # Step 2: Segment into clauses
        with console.status("[bold]Segmenting clauses...[/bold]"):
            clauses = segmenter.segment(doc)
            summary = segmenter.get_clause_summary(clauses)
            console.print(f"[green]✓[/green] Found {summary['total_clauses']} clauses")

        # Step 3: Extract metadata
        with console.status("[bold]Extracting contract metadata...[/bold]"):
            metadata = self._extract_metadata(doc)
            console.print(f"[green]✓[/green] Metadata: {metadata.get('contract_type', 'Unknown')} | "
                         f"Parties: {', '.join(metadata.get('parties', ['Unknown']))}")

        # Step 4: Review each clause
        console.print(f"\n[bold]Reviewing {len(clauses)} clauses...[/bold]")
        clause_reviews = self._review_all_clauses(clauses)

        # Step 5: Generate executive summary
        with console.status("[bold]Generating executive summary...[/bold]"):
            reviews_as_dicts = [
                {
                    "heading": r.heading or r.clause_type,
                    "risk_level": r.risk_level,
                    "issues": " | ".join(r.issues),
                }
                for r in clause_reviews
            ]
            exec_summary = self._generate_summary(reviews_as_dicts, metadata)

        # Step 6: Assemble report
        report = self._assemble_report(
            filename=path.name,
            metadata=metadata,
            clause_reviews=clause_reviews,
            executive_summary=exec_summary,
        )

        console.print(f"\n[bold green]✅ Review Complete[/bold green]")
        console.print(f"Overall Risk: [bold {'red' if report.overall_risk == 'HIGH' else 'yellow' if report.overall_risk == 'MEDIUM' else 'green'}]{report.overall_risk}[/bold]")
        console.print(f"High: {report.high_risk_count} | Medium: {report.medium_risk_count} | Low: {report.low_risk_count} | Acceptable: {report.acceptable_count}")

        return report

    # ------------------------------------------------------------------
    # Step 3: Metadata Extraction
    # ------------------------------------------------------------------

    def _extract_metadata(self, doc: ParsedDocument) -> dict:
        """Extract structured metadata from contract text."""
        prompt = prompt_extract_metadata(doc.raw_text)

        try:
            response = llm.generate(
                prompt=prompt,
                system=SYSTEM_METADATA_EXTRACTOR,
                model=config.FAST_MODEL,
                temperature=0.0,
                max_tokens=512,
            )
            # Parse JSON response
            metadata = self._parse_json_response(response)
            return metadata or {}

        except Exception as e:
            logger.warning(f"Metadata extraction failed: {e}. Using defaults.")
            return {
                "contract_type": doc.metadata.get("title", "Unknown"),
                "parties": [],
                "effective_date": None,
                "expiration_date": None,
                "governing_law": None,
            }

    # ------------------------------------------------------------------
    # Step 4: Clause Review
    # ------------------------------------------------------------------

    def _review_all_clauses(self, clauses: list[Clause]) -> list[ClauseReview]:
        """Review all clauses, showing progress."""
        reviews = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task("Reviewing clauses...", total=len(clauses))

            for clause in clauses:
                progress.update(task, description=f"[cyan]{clause.heading or clause.clause_type or 'clause'}[/cyan]")

                review = self._review_single_clause(clause)
                reviews.append(review)

                # Show risk level inline
                color = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "blue", "ACCEPTABLE": "green"}.get(review.risk_level, "white")
                progress.console.print(
                    f"  [{color}]{review.risk_level}[/{color}] — "
                    f"{review.heading or review.clause_type or clause.clause_id}"
                )

                progress.advance(task)

        return reviews

    def _review_single_clause(self, clause: Clause) -> ClauseReview:
        """Review one clause. Returns ClauseReview with risk assessment."""
        try:
            # Build the review prompt
            # Note: In Phase 2, we'll inject RAG playbook context here
            prompt = prompt_review_clause(
                clause_text=clause.text,
                clause_type=clause.clause_type,
                clause_heading=clause.heading,
                playbook_context="",  # Phase 2: will come from vector search
            )

            response = llm.generate(
                prompt=prompt,
                system=SYSTEM_CONTRACT_REVIEWER,
                temperature=0.1,
                max_tokens=1024,
            )

            return self._parse_review_response(response, clause)

        except Exception as e:
            logger.error(f"Failed to review clause {clause.clause_id}: {e}")
            return ClauseReview(
                clause_id=clause.clause_id,
                number=clause.number,
                heading=clause.heading,
                clause_type=clause.clause_type,
                risk_level="LOW",
                issues=[f"Review failed: {str(e)}"],
                original_text=clause.text,
            )

    # ------------------------------------------------------------------
    # Step 5: Summary Generation
    # ------------------------------------------------------------------

    def _generate_summary(self, reviews: list[dict], metadata: dict) -> str:
        """Generate executive summary from all clause reviews."""
        prompt = prompt_contract_summary(reviews, metadata)
        try:
            return llm.generate(
                prompt=prompt,
                system=SYSTEM_CONTRACT_REVIEWER,
                temperature=0.2,
                max_tokens=1024,
            )
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return "Summary generation failed. Please review individual clause results."

    # ------------------------------------------------------------------
    # Report Assembly
    # ------------------------------------------------------------------

    def _assemble_report(
        self,
        filename: str,
        metadata: dict,
        clause_reviews: list[ClauseReview],
        executive_summary: str,
    ) -> ContractReviewReport:
        """Count risks and assemble the final report object."""
        counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "ACCEPTABLE": 0}
        for review in clause_reviews:
            level = review.risk_level.upper()
            if level in counts:
                counts[level] += 1

        # Extract recommendation from summary
        recommendation = "Negotiate before signing"  # Default
        if "do not sign" in executive_summary.lower():
            recommendation = "Do not sign"
        elif "sign as-is" in executive_summary.lower() or "sign as is" in executive_summary.lower():
            recommendation = "Sign as-is"

        return ContractReviewReport(
            filename=filename,
            reviewed_at=datetime.now().isoformat(),
            metadata=metadata,
            total_clauses=len(clause_reviews),
            high_risk_count=counts["HIGH"],
            medium_risk_count=counts["MEDIUM"],
            low_risk_count=counts["LOW"],
            acceptable_count=counts["ACCEPTABLE"],
            clause_reviews=clause_reviews,
            executive_summary=executive_summary,
            recommendation=recommendation,
        )

    # ------------------------------------------------------------------
    # Response Parsers
    # ------------------------------------------------------------------

    def _parse_review_response(self, response: str, clause: Clause) -> ClauseReview:
        """Parse the structured LLM review response."""
        risk_level = "LOW"
        issues = []
        redline = ""
        reasoning = ""

        # Extract RISK_LEVEL
        risk_match = re.search(r"RISK_LEVEL:\s*(HIGH|MEDIUM|LOW|ACCEPTABLE)", response, re.IGNORECASE)
        if risk_match:
            risk_level = risk_match.group(1).upper()

        # Extract ISSUES block
        issues_match = re.search(r"ISSUES:\s*(.*?)(?=REDLINE_SUGGESTION:|REASONING:|$)", response, re.DOTALL)
        if issues_match:
            issues_text = issues_match.group(1).strip()
            if issues_text.lower() != "none":
                # Parse bullet points
                issue_lines = re.findall(r"[-•]\s*(.+?)(?=\n[-•]|\Z)", issues_text, re.DOTALL)
                issues = [i.strip() for i in issue_lines if i.strip()]
                if not issues and issues_text:
                    issues = [issues_text[:300]]

        # Extract REDLINE_SUGGESTION
        redline_match = re.search(r"REDLINE_SUGGESTION:\s*(.*?)(?=REASONING:|$)", response, re.DOTALL)
        if redline_match:
            redline = redline_match.group(1).strip()
            if redline.lower() == "no change needed":
                redline = ""

        # Extract REASONING
        reasoning_match = re.search(r"REASONING:\s*(.*?)$", response, re.DOTALL)
        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()

        return ClauseReview(
            clause_id=clause.clause_id,
            number=clause.number,
            heading=clause.heading,
            clause_type=clause.clause_type,
            risk_level=risk_level,
            issues=issues,
            redline_suggestion=redline,
            reasoning=reasoning,
            original_text=clause.text,
        )

    def _parse_json_response(self, response: str) -> Optional[dict]:
        """Safely parse JSON from LLM response."""
        # Strip markdown fences if present
        clean = re.sub(r"```(?:json)?", "", response).replace("```", "").strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            # Try to extract JSON object from response
            json_match = re.search(r"\{.*\}", clean, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except Exception:
                    pass
        return None


# Singleton
review_pipeline = ReviewPipeline()
