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

# Phase 2: RAG retriever
try:
    from rag.retriever import retriever
    RAG_ENABLED = True
except Exception as _rag_err:
    retriever = None
    RAG_ENABLED = False

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
    risk_level: str                             # HIGH | MEDIUM | LOW | ACCEPTABLE
    issues: list[str] = field(default_factory=list)
    evidence_quotes: list[str] = field(default_factory=list)   # exact text spans triggering each issue
    redline_suggestion: str = ""                # narrative summary
    redlines: list[dict] = field(default_factory=list)         # [{replace: str, with: str}, ...]
    reasoning: str = ""
    original_text: str = ""
    escalated: bool = False                     # True if risk was upgraded by contradiction resolver


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

        # Step 4.5: Resolve contradictions — same clause type cannot be HIGH and LOW
        clause_reviews = self._resolve_contradictions(clause_reviews)

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

        color = 'red' if report.overall_risk == 'HIGH' else 'yellow' if report.overall_risk == 'MEDIUM' else 'green'
        console.print(f"\n[bold green]Review Complete[/bold green]")
        console.print(f"Overall Risk: [{color}]{report.overall_risk}[/{color}]")
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

    def _review_all_clauses(self, clauses: list[Clause], governing_law: str = "") -> list[ClauseReview]:
        """Review all clauses, showing progress. Phase 2: passes governing_law to retriever."""
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

                review = self._review_single_clause(clause, governing_law=governing_law)
                reviews.append(review)

                # Show risk level inline
                color = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "blue", "ACCEPTABLE": "green"}.get(review.risk_level, "white")
                progress.console.print(
                    f"  [{color}]{review.risk_level}[/{color}] — "
                    f"{review.heading or review.clause_type or clause.clause_id}"
                )

                progress.advance(task)

        return reviews

    def _review_single_clause(self, clause: Clause, governing_law: str = "") -> ClauseReview:
        """
        Review one clause. Phase 2: retrieves playbook context from ChromaDB
        before sending to LLM — making review company-aware.
        """
        try:
            # Phase 2: retrieve relevant context from knowledge base
            playbook_context = ""
            if RAG_ENABLED and retriever is not None:
                playbook_context = retriever.get_context_for_clause(
                    clause_type=clause.clause_type,
                    clause_text=clause.text,
                    governing_law=governing_law or None,
                )

            prompt = prompt_review_clause(
                clause_text=clause.text,
                clause_type=clause.clause_type,
                clause_heading=clause.heading,
                playbook_context=playbook_context,
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
    # Contradiction Resolver
    # ------------------------------------------------------------------

    def _resolve_contradictions(self, reviews: list) -> list:
        """
        Ensures risk rating consistency across clauses of the SAME type.

        Problem: The LLM reviews each clause independently. It might rate one
        limitation_of_liability clause HIGH and another LOW even when both
        contain similarly dangerous language.

        Rules:
        - Only fires when 2+ clauses share the same clause_type
        - Only escalates by ONE level (LOW→MEDIUM or MEDIUM→HIGH, never LOW→HIGH)
        - "general" type is excluded — too broad to draw meaningful comparisons
        - Requires at least a 2-level gap to trigger (HIGH vs LOW, not HIGH vs MEDIUM)
          because MEDIUM vs HIGH is a judgment call, but HIGH vs LOW is contradictory
        """
        RISK_ORDER = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "ACCEPTABLE": 0}
        RISK_NAMES = {3: "HIGH", 2: "MEDIUM", 1: "LOW", 0: "ACCEPTABLE"}

        # Skip types that are too generic for comparison
        SKIP_TYPES = {"general", "definitions", "entire_agreement", "amendment"}

        # Count clauses per type — only compare when multiple clauses share a type
        type_counts: dict[str, int] = {}
        for r in reviews:
            type_counts[r.clause_type] = type_counts.get(r.clause_type, 0) + 1

        # Find highest risk per type (only for types with 2+ clauses)
        max_risk_per_type: dict[str, int] = {}
        for r in reviews:
            if type_counts.get(r.clause_type, 0) < 2:
                continue
            if r.clause_type in SKIP_TYPES:
                continue
            current_max = max_risk_per_type.get(r.clause_type, 0)
            this_level = RISK_ORDER.get(r.risk_level, 0)
            if this_level > current_max:
                max_risk_per_type[r.clause_type] = this_level

        # Escalate only when gap is 2+ levels (HIGH vs LOW = contradictory)
        # Never escalate by more than 1 step at a time
        for r in reviews:
            if r.clause_type not in max_risk_per_type:
                continue

            type_max = max_risk_per_type[r.clause_type]
            this_level = RISK_ORDER.get(r.risk_level, 0)
            gap = type_max - this_level

            # Only fix genuine contradictions (gap of 2+), not close judgment calls
            if gap >= 2:
                old_level = r.risk_level
                # Escalate by exactly one step, not all the way to max
                new_level = RISK_NAMES[this_level + 1]
                r.risk_level = new_level
                r.escalated = True
                r.reasoning = (
                    f"[Consistency check: escalated {old_level} → {new_level} because "
                    f"another {r.clause_type} clause in this contract was rated "
                    f"{RISK_NAMES[type_max]}. Same clause type, similar language.] "
                    + r.reasoning
                )
                logger.debug(f"Escalated {r.clause_id} ({r.clause_type}): {old_level} → {new_level}")

        return reviews

    # ------------------------------------------------------------------
    # Response Parsers
    # ------------------------------------------------------------------

    def _parse_review_response(self, response: str, clause: Clause) -> ClauseReview:
        """
        Parse the structured LLM review response.
        Now extracts: RISK_LEVEL, ISSUE/EVIDENCE/IMPACT blocks, REPLACE/WITH redlines, REASONING.
        """
        risk_level = "LOW"
        issues = []
        evidence_quotes = []
        redlines = []
        redline_summary = ""
        reasoning = ""

        # Extract RISK_LEVEL
        risk_match = re.search(r"RISK_LEVEL:\s*(HIGH|MEDIUM|LOW|ACCEPTABLE)", response, re.IGNORECASE)
        if risk_match:
            risk_level = risk_match.group(1).upper()

        # Extract ISSUES block — new format has ISSUE/EVIDENCE/IMPACT per item
        issues_block_match = re.search(r"ISSUES:\s*(.*?)(?=REDLINE:|REASONING:|$)", response, re.DOTALL)
        if issues_block_match:
            issues_text = issues_block_match.group(1).strip()
            if issues_text.lower() not in ("none", "none."):
                # Try new structured format: ISSUE: ... EVIDENCE: "..." IMPACT: ...
                issue_blocks = re.split(r"(?=- ISSUE:)", issues_text)
                for block in issue_blocks:
                    block = block.strip()
                    if not block:
                        continue

                    issue_match = re.search(r"ISSUE:\s*(.+?)(?=EVIDENCE:|IMPACT:|$)", block, re.DOTALL)
                    evidence_match = re.search(r'EVIDENCE:\s*["\']?(.+?)["\']?(?=IMPACT:|$)', block, re.DOTALL)
                    impact_match = re.search(r"IMPACT:\s*(.+?)$", block, re.DOTALL)

                    if issue_match:
                        issue_text = issue_match.group(1).strip()
                        impact_text = impact_match.group(1).strip() if impact_match else ""
                        full_issue = f"{issue_text}" + (f" — {impact_text}" if impact_text else "")
                        issues.append(full_issue)

                    if evidence_match:
                        evidence_quotes.append(evidence_match.group(1).strip())

                # Fallback: old bullet point format
                if not issues:
                    issue_lines = re.findall(r"[-•]\s*(.+?)(?=\n[-•]|\Z)", issues_text, re.DOTALL)
                    issues = [i.strip() for i in issue_lines if i.strip()]
                    if not issues and issues_text:
                        issues = [issues_text[:300]]

        # Extract REDLINE block — new format: REPLACE: "..." WITH: "..."
        redline_block_match = re.search(r"REDLINE:\s*(.*?)(?=REASONING:|$)", response, re.DOTALL)
        if redline_block_match:
            redline_text = redline_block_match.group(1).strip()
            if "no changes needed" not in redline_text.lower():
                # Parse REPLACE/WITH pairs
                pairs = re.findall(
                    r'REPLACE:\s*["\']?(.+?)["\']?\s*WITH:\s*["\']?(.+?)["\']?(?=REPLACE:|$)',
                    redline_text, re.DOTALL
                )
                for replace_text, with_text in pairs:
                    r = replace_text.strip()
                    w = with_text.strip()

                    # Drop useless redlines:
                    # 1. replace == with (LLM copied same text into both fields)
                    # 2. Either side is empty, "None", or a placeholder artifact
                    # 3. replace text doesn't actually exist in the clause
                    #    (catches hallucinated quotes)
                    JUNK = {"none", "-", "**", "no changes needed", ""}
                    if r.lower() in JUNK or w.lower() in JUNK:
                        continue
                    if r == w:
                        continue
                    # Truncate trailing markdown artifacts the LLM sometimes appends
                    w = w.rstrip("*\n").strip().rstrip('"').strip()
                    r = r.rstrip("*\n").strip().rstrip('"').strip()
                    if r and w and r != w:
                        redlines.append({"replace": r, "with": w})
                # Summary for display
                redline_summary = redline_text[:500]

        # Fallback: old REDLINE_SUGGESTION format
        if not redlines:
            old_redline_match = re.search(r"REDLINE_SUGGESTION:\s*(.*?)(?=REASONING:|$)", response, re.DOTALL)
            if old_redline_match:
                redline_summary = old_redline_match.group(1).strip()
                if redline_summary.lower() == "no change needed":
                    redline_summary = ""

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
            evidence_quotes=evidence_quotes,
            redline_suggestion=redline_summary,
            redlines=redlines,
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