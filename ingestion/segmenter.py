"""
ingestion/segmenter.py — Clause Segmentation Pipeline
Breaks a contract into individual clauses for per-clause analysis.

Strategy: Rule-based first (fast), LLM-assisted for ambiguous sections.
This is the most critical component — bad segmentation = bad review quality.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger

from ingestion.parser import ParsedDocument


# ------------------------------------------------------------------
# Clause Data Model
# ------------------------------------------------------------------

@dataclass
class Clause:
    """
    A single extracted clause from a contract.
    """
    clause_id: str              # e.g. "clause_003"
    number: str                 # e.g. "3.2" or "Article IV" or ""
    heading: str                # e.g. "Limitation of Liability"
    text: str                   # Full clause text
    clause_type: str = ""       # Classified type (filled in review pipeline)
    risk_level: str = ""        # HIGH / MEDIUM / LOW (filled in review pipeline)
    page_hint: int = 0          # Approximate page number
    parent_clause: str = ""     # Parent clause number if nested
    metadata: dict = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        """Heading + body for display and LLM prompts."""
        if self.heading:
            return f"{self.number} {self.heading}\n{self.text}".strip()
        return f"{self.number}\n{self.text}".strip() if self.number else self.text

    def __len__(self):
        return len(self.text)


# ------------------------------------------------------------------
# Clause Patterns (Rule-Based Detection)
# ------------------------------------------------------------------

# These patterns cover the most common contract numbering styles
CLAUSE_HEADER_PATTERNS = [
    # Numbered: 1. , 1.1 , 1.1.1 , 12.3.4
    r"^(\d{1,2}(?:\.\d{1,2}){0,3})\s*[.)]\s+([A-Z][^\n]{2,80})$",
    # Article: ARTICLE I , Article 1 , ARTICLE ONE
    r"^(ARTICLE\s+(?:[IVX]+|\d+))\s*[.:\-]?\s*([A-Z][^\n]{0,80})$",
    # Section: SECTION 1 , Section 2.3
    r"^(SECTION\s+\d+(?:\.\d+)?)\s*[.:\-]?\s*([A-Z][^\n]{0,80})$",
    # Lettered: A. , (a) , A)
    r"^([A-Z]\.|[A-Z]\)|[(][a-z][)])\s+([A-Z][^\n]{2,80})$",
    # ALL CAPS heading (common in NDAs, employment contracts)
    r"^([A-Z][A-Z\s]{4,50}[A-Z])\s*$",
    # Recitals / Whereas
    r"^(WHEREAS|RECITALS?|BACKGROUND|PREAMBLE)\b",
    # Definitions section entries
    r"^\"([A-Z][a-zA-Z\s]+)\"\s+(?:means|shall mean|refers to)",
]

COMPILED_PATTERNS = [re.compile(p, re.MULTILINE) for p in CLAUSE_HEADER_PATTERNS]

# Known clause type keywords for quick pre-classification
CLAUSE_TYPE_KEYWORDS = {
    "definitions": ["definition", "definitions", "defined terms", "means", "shall mean"],
    "term_termination": ["term", "termination", "duration", "expire", "expiration", "cancel", "cancellation"],
    "payment": ["payment", "fees", "compensation", "invoice", "billing", "price", "cost"],
    "confidentiality": ["confidential", "nda", "non-disclosure", "proprietary", "trade secret"],
    "intellectual_property": ["intellectual property", "ip", "copyright", "patent", "trademark", "ownership", "license", "work for hire"],
    "limitation_of_liability": ["limitation of liability", "limit of liability", "liability cap", "not liable", "exclude liability"],
    "indemnification": ["indemnif", "defend", "hold harmless"],
    "warranties": ["warrant", "warranty", "representation", "represent", "guarantee"],
    "dispute_resolution": ["dispute", "arbitration", "mediation", "litigation", "jurisdiction", "governing law"],
    "force_majeure": ["force majeure", "act of god", "beyond control"],
    "assignment": ["assign", "transfer", "novation", "subcontract"],
    "non_compete": ["non-compete", "noncompete", "competition", "competing", "solicit", "non-solicit"],
    "data_privacy": ["data", "privacy", "gdpr", "personal information", "data protection"],
    "notices": ["notice", "notification", "communicate", "written notice"],
    "entire_agreement": ["entire agreement", "merger clause", "integration clause", "supersede"],
    "amendment": ["amend", "amendment", "modify", "modification", "change"],
}


class ClauseSegmenter:
    """
    Segments a parsed contract into individual clauses.
    
    Approach:
    1. Rule-based pattern matching (fast, handles 80% of cases)
    2. Line-by-line boundary detection
    3. Post-processing to merge orphaned lines
    4. Quick keyword-based pre-classification
    """

    def segment(self, doc: ParsedDocument) -> list[Clause]:
        """
        Main entry. Returns list of Clause objects ordered as they appear.
        """
        logger.info(f"Segmenting '{doc.filename}' ({doc.word_count} words)")

        text = doc.raw_text
        lines = text.split("\n")

        # Step 1: Find clause boundaries
        boundaries = self._find_boundaries(lines)

        # Step 2: Extract clause blocks between boundaries
        clauses = self._extract_clauses(lines, boundaries)

        # Step 3: Pre-classify clause types (keyword-based, fast)
        clauses = self._pre_classify(clauses)

        # Step 4: Filter noise (very short fragments that aren't real clauses)
        clauses = [c for c in clauses if len(c.text.strip()) > 50]

        logger.success(f"Segmented into {len(clauses)} clauses")
        return clauses

    # ------------------------------------------------------------------
    # Boundary Detection
    # ------------------------------------------------------------------

    def _find_boundaries(self, lines: list[str]) -> list[tuple[int, str, str]]:
        """
        Returns list of (line_index, clause_number, clause_heading) tuples
        marking where each new clause starts.
        """
        boundaries = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            match_result = self._is_clause_header(stripped)
            if match_result:
                number, heading = match_result
                boundaries.append((i, number, heading))

        return boundaries

    def _is_clause_header(self, line: str) -> Optional[tuple[str, str]]:
        """
        Check if a line is a clause header.
        Returns (number, heading) if yes, None if no.
        """
        for pattern in COMPILED_PATTERNS:
            match = pattern.match(line)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    return groups[0].strip(), groups[1].strip()
                elif len(groups) == 1:
                    return groups[0].strip(), ""
                else:
                    return line.strip(), ""

        # ALL CAPS line that looks like a heading (no pattern matched above)
        if (line.isupper() and 3 <= len(line.split()) <= 8
                and not line.startswith("WHEREAS")
                and line[0].isalpha()):
            return "", line.strip()

        return None

    # ------------------------------------------------------------------
    # Clause Extraction
    # ------------------------------------------------------------------

    def _extract_clauses(
        self,
        lines: list[str],
        boundaries: list[tuple[int, str, str]]
    ) -> list[Clause]:
        """Build Clause objects from boundary markers."""
        clauses = []

        if not boundaries:
            # No structure detected — treat whole document as one block
            # This happens with very old/malformatted contracts
            logger.warning("No clause boundaries detected. Falling back to paragraph chunking.")
            return self._paragraph_fallback(lines)

        for idx, (line_idx, number, heading) in enumerate(boundaries):
            # Determine end of this clause
            if idx + 1 < len(boundaries):
                end_idx = boundaries[idx + 1][0]
            else:
                end_idx = len(lines)

            # Collect body lines (skip the header line itself)
            body_lines = lines[line_idx + 1:end_idx]
            body = "\n".join(body_lines).strip()

            # If heading was blank, try to grab it from the first content line
            if not heading and body:
                first_line = body.split("\n")[0].strip()
                if len(first_line) < 100:
                    heading = first_line

            clause = Clause(
                clause_id=f"clause_{idx + 1:03d}",
                number=number,
                heading=heading,
                text=body,
                page_hint=self._estimate_page(line_idx, len(lines)),
            )
            clauses.append(clause)

        return clauses

    def _paragraph_fallback(self, lines: list[str]) -> list[Clause]:
        """
        Fallback: split by double newlines (paragraph boundaries).
        Used when no structured clause headers are found.
        """
        full_text = "\n".join(lines)
        paragraphs = re.split(r"\n{2,}", full_text)
        clauses = []

        for idx, para in enumerate(paragraphs):
            para = para.strip()
            if len(para) > 50:
                clauses.append(Clause(
                    clause_id=f"clause_{idx + 1:03d}",
                    number="",
                    heading="",
                    text=para,
                    page_hint=0,
                ))

        return clauses

    # ------------------------------------------------------------------
    # Pre-Classification (Keyword-Based)
    # ------------------------------------------------------------------

    def _pre_classify(self, clauses: list[Clause]) -> list[Clause]:
        """
        Quick keyword-based clause type labeling.
        This is a first pass only — the LLM review pipeline will refine it.
        """
        for clause in clauses:
            search_text = (clause.heading + " " + clause.text).lower()
            clause.clause_type = self._detect_type(search_text)

        return clauses

    def _detect_type(self, text: str) -> str:
        """Match text against keyword dictionary. Returns best match."""
        scores = {}
        for clause_type, keywords in CLAUSE_TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[clause_type] = score

        if not scores:
            return "general"

        return max(scores, key=scores.get)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _estimate_page(self, line_idx: int, total_lines: int) -> int:
        """Rough page estimate based on line position."""
        lines_per_page = 45  # Approximate
        return max(1, line_idx // lines_per_page + 1)

    def get_clause_summary(self, clauses: list[Clause]) -> dict:
        """Returns a summary of what was found — useful for logging."""
        type_counts = {}
        for c in clauses:
            type_counts[c.clause_type] = type_counts.get(c.clause_type, 0) + 1

        return {
            "total_clauses": len(clauses),
            "clause_types": type_counts,
            "avg_clause_length": sum(len(c.text) for c in clauses) // max(len(clauses), 1),
        }


# Singleton
segmenter = ClauseSegmenter()
