

# """
# utils/report_exporter.py — Export review reports to files.
# Supports: JSON (machine-readable) and Markdown (human-readable / PDF-ready).
# """

# import json
# import re
# from pathlib import Path
# from loguru import logger


# class ReportExporter:

#     # ------------------------------------------------------------------
#     # JSON Export
#     # ------------------------------------------------------------------

#     def export_json(self, report, output_path: Path) -> Path:
#         """Export full report as JSON."""
#         data = {
#             "filename":          report.filename,
#             "reviewed_at":       report.reviewed_at,
#             "overall_risk":      report.overall_risk,
#             "recommendation":    report.recommendation,
#             "metadata":          report.metadata,
#             "summary": {
#                 "total_clauses": report.total_clauses,
#                 "high_risk":     report.high_risk_count,
#                 "medium_risk":   report.medium_risk_count,
#                 "low_risk":      report.low_risk_count,
#                 "acceptable":    report.acceptable_count,
#             },
#             "executive_summary": report.executive_summary,
#             "clause_reviews": [
#                 {
#                     "clause_id":        r.clause_id,
#                     "number":           r.number,
#                     "heading":          r.heading,
#                     "clause_type":      r.clause_type,
#                     "risk_level":       r.risk_level,
#                     "issues":           r.issues,
#                     "redline_suggestion": r.redline_suggestion,
#                     "reasoning":        r.reasoning,
#                     "original_text":    r.original_text[:500],
#                 }
#                 for r in report.clause_reviews
#             ],
#         }
#         output_path.write_text(
#             json.dumps(data, indent=2, ensure_ascii=False),
#             encoding="utf-8",
#         )
#         logger.info(f"JSON report saved: {output_path}")
#         return output_path

#     # ------------------------------------------------------------------
#     # Markdown Export
#     # ------------------------------------------------------------------

#     def export_markdown(self, report, output_path: Path) -> Path:
#         """Export report as clean, PDF-ready Markdown."""
#         lines = []
#         risk_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(report.overall_risk, "⚪")

#         # Header
#         lines += [
#             "# Contract Review Report",
#             "",
#             f"**File:** {report.filename}  ",
#             f"**Reviewed:** {report.reviewed_at[:19].replace('T', ' ')}  ",
#             f"**Overall Risk:** {risk_emoji} {report.overall_risk}  ",
#             f"**Recommendation:** {report.recommendation}",
#             "",
#         ]

#         # Contract details table
#         m = report.metadata
#         lines += [
#             "## Contract Details",
#             "",
#             "| Field | Value |",
#             "|-------|-------|",
#             f"| Type | {m.get('contract_type', 'Unknown')} |",
#             f"| Parties | {', '.join(m.get('parties', []))} |",
#             f"| Effective Date | {m.get('effective_date', 'N/A')} |",
#             f"| Expiration Date | {m.get('expiration_date', 'N/A')} |",
#             f"| Governing Law | {m.get('governing_law', 'N/A')} |",
#             f"| Auto-Renewal | {m.get('auto_renewal', 'N/A')} |",
#             "",
#         ]

#         # Risk summary table
#         lines += [
#             "## Risk Summary",
#             "",
#             "| Risk Level | Count |",
#             "|------------|-------|",
#             f"| 🔴 HIGH | {report.high_risk_count} |",
#             f"| 🟡 MEDIUM | {report.medium_risk_count} |",
#             f"| 🔵 LOW | {report.low_risk_count} |",
#             f"| ✅ ACCEPTABLE | {report.acceptable_count} |",
#             f"| **Total** | **{report.total_clauses}** |",
#             "",
#         ]

#         # Executive summary — strip LLM bold header if present
#         summary = re.sub(r"^\*\*Executive Summary\*\*\s*", "", report.executive_summary or "", flags=re.IGNORECASE).strip()
#         if summary:
#             lines += ["## Executive Summary", "", summary, ""]

#         # Clauses grouped by risk
#         high   = [r for r in report.clause_reviews if r.risk_level == "HIGH"]
#         medium = [r for r in report.clause_reviews if r.risk_level == "MEDIUM"]
#         low    = [r for r in report.clause_reviews if r.risk_level == "LOW"]
#         ok     = [r for r in report.clause_reviews if r.risk_level == "ACCEPTABLE"]

#         if high:
#             lines += ["## 🔴 High Risk Clauses", ""]
#             for r in high:
#                 lines += self._format_clause(r)

#         if medium:
#             lines += ["## 🟡 Medium Risk Clauses", ""]
#             for r in medium:
#                 lines += self._format_clause(r)

#         if low:
#             lines += ["## 🔵 Low Risk Clauses", ""]
#             for r in low:
#                 lines += self._format_clause(r, compact=True)

#         if ok:
#             lines += ["## ✅ Acceptable Clauses", ""]
#             for r in ok:
#                 lines += self._format_clause(r, compact=True)

#         output_path.write_text("\n".join(lines), encoding="utf-8")
#         logger.info(f"Markdown report saved: {output_path}")
#         return output_path

#     # ------------------------------------------------------------------
#     # Clause Formatter
#     # ------------------------------------------------------------------

#     def _format_clause(self, review, compact: bool = False) -> list[str]:
#         """Format one clause review into clean markdown lines."""
#         EMOJI = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵", "ACCEPTABLE": "✅"}
#         emoji   = EMOJI.get(review.risk_level, "⚪")
#         heading = review.heading or review.clause_type or review.clause_id
#         number  = f"{review.number} " if review.number else ""
#         esc_tag = " *(risk escalated)*" if getattr(review, "escalated", False) else ""

#         lines = [f"### {emoji} {number}{heading}{esc_tag}", ""]

#         if compact:
#             lines += [
#                 f"**Risk:** {review.risk_level} | **Type:** {review.clause_type}",
#                 "",
#             ]
#             if review.issues:
#                 lines += [f"_{self._clean(review.issues[0])}_", ""]
#             lines += ["---", ""]
#             return lines

#         lines += [
#             f"**Risk Level:** {review.risk_level}",
#             f"**Clause Type:** {review.clause_type}",
#             "",
#         ]

#         # Issues + evidence
#         if review.issues:
#             lines += ["**Issues Found:**", ""]
#             evidence = getattr(review, "evidence_quotes", [])
#             for i, issue in enumerate(review.issues):
#                 ev = self._clean_evidence(evidence[i] if i < len(evidence) else "")
#                 lines += [
#                     f"**Issue {i+1}:** {self._clean(issue)}",
#                     "",
#                     f"> **Evidence:** {ev}",
#                     "",
#                 ]

#         # Redlines — skip junk entries where replace/with is None/empty/dash
#         redlines = getattr(review, "redlines", [])
#         good_redlines = [
#             rd for rd in redlines
#             if self._is_real(rd.get("replace", ""))
#             and self._is_real(rd.get("with", ""))
#         ]
#         if good_redlines:
#             lines += ["**Precise Redlines:**", ""]
#             for j, rd in enumerate(good_redlines, 1):
#                 lines += [
#                     f"**Redline {j}:**",
#                     "",
#                     f"~~{self._clean_part(rd['replace'])}~~",
#                     "",
#                     f"→ {self._clean_part(rd['with'])}",
#                     "",
#                 ]
#         elif review.redline_suggestion:
#             rl = self._clean(review.redline_suggestion)
#             if rl:
#                 lines += ["**Suggested Redline:**", "", f"> {rl}", ""]

#         # Analysis
#         if review.reasoning:
#             r = self._clean(review.reasoning)
#             if r:
#                 lines += ["**Analysis:**", "", r, ""]

#         lines += ["---", ""]
#         return lines

#     # ------------------------------------------------------------------
#     # Cleaning Helpers
#     # ------------------------------------------------------------------

#     def _clean(self, text: str) -> str:
#         """Remove LLM artifacts: stray **, PDF hyphen line-breaks, excess newlines."""
#         if not text:
#             return ""
#         text = re.sub(r"^\s*\*\*\s*", "", text)       # leading **
#         text = re.sub(r"\s*\*\*\s*$", "", text)       # trailing **
#         text = re.sub(r"-[ \t]*\n[ \t]*", "", text)   # PDF hyphen break e.g. "man-\nagement"
#         text = re.sub(r"\n{3,}", "\n\n", text)        # excess blank lines
#         return text.strip()

#     def _clean_evidence(self, ev: str) -> str:
#         """
#         Normalise an evidence string.
#         - Returns N/A for empty / None / dash values
#         - Cuts off IMPACT: leakage (LLM sometimes continues into next field)
#         """
#         if not ev:
#             return "N/A"
#         ev = ev.strip()
#         if ev.lower() in ("none", "none.", "n/a", "-", "") or ev.lower().startswith("none ("):
#             return "N/A"
#         # Cut anything after IMPACT: — that's a different field bleeding in
#         ev = re.split(r"\s*IMPACT\s*:", ev, maxsplit=1)[0]
#         ev = re.sub(r"-[ \t]*\n[ \t]*", "", ev)   # PDF hyphen break inside evidence
#         ev = ev.rstrip(" -\n").strip()
#         return ev or "N/A"

#     def _clean_part(self, text: str) -> str:
#         """Clean a redline REPLACE or WITH value."""
#         text = re.sub(r"\*\*", "", text)
#         text = re.sub(r'"\s*$', "", text)
#         text = re.sub(r"-[ \t]*\n[ \t]*", "", text)
#         return text.strip()

#     def _is_real(self, text: str) -> bool:
#         """Return True if a redline part is meaningful (not None/empty/dash)."""
#         return text.strip().lower() not in ("", "none", "-", "n/a")


# # Singleton
# exporter = ReportExporter()


"""
utils/report_exporter.py - Export review reports to files.
Supports: JSON (machine-readable) and Markdown (human-readable / PDF-ready).
"""

import json
import re
from pathlib import Path
from loguru import logger

# Emoji constants — defined as unicode escapes to avoid Windows encoding issues
E_HIGH   = "\U0001f534"  # red circle
E_MEDIUM = "\U0001f7e1"  # yellow circle
E_LOW    = "\U0001f535"  # blue circle
E_OK     = "\u2705"      # green check
E_GREY   = "\u26aa"      # grey circle
E_PIN    = "\U0001f4cc"  # pushpin
E_X      = "\u274c"      # red X


class ReportExporter:

    # ------------------------------------------------------------------
    # JSON Export
    # ------------------------------------------------------------------

    def export_json(self, report, output_path: Path) -> Path:
        data = {
            "filename":          report.filename,
            "reviewed_at":       report.reviewed_at,
            "overall_risk":      report.overall_risk,
            "recommendation":    report.recommendation,
            "metadata":          report.metadata,
            "summary": {
                "total_clauses": report.total_clauses,
                "high_risk":     report.high_risk_count,
                "medium_risk":   report.medium_risk_count,
                "low_risk":      report.low_risk_count,
                "acceptable":    report.acceptable_count,
            },
            "executive_summary": report.executive_summary,
            "clause_reviews": [
                {
                    "clause_id":          r.clause_id,
                    "number":             r.number,
                    "heading":            r.heading,
                    "clause_type":        r.clause_type,
                    "risk_level":         r.risk_level,
                    "page_num":           getattr(r, "page_num", None),
                    "issues":             r.issues,
                    "evidence_quotes":    getattr(r, "evidence_quotes", []),
                    "redlines":           getattr(r, "redlines", []),
                    "redline_suggestion": r.redline_suggestion,
                    "reasoning":          r.reasoning,
                    "original_text":      r.original_text[:500],
                }
                for r in report.clause_reviews
            ],
        }
        output_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"JSON report saved: {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # Markdown Export
    # ------------------------------------------------------------------

    def export_markdown(self, report, output_path: Path) -> Path:
        lines = []
        m = report.metadata
        RISK_EMOJI = {"HIGH": E_HIGH, "MEDIUM": E_MEDIUM, "LOW": E_LOW}
        risk_icon = RISK_EMOJI.get(report.overall_risk, E_GREY)

        def cmeta(val):
            """Normalise metadata: None / 'null' / 'none' all become N/A."""
            if val is None:
                return "N/A"
            s = str(val).strip()
            return "N/A" if s.lower() in ("null", "none", "") else s

        # Header
        lines += [
            "# Contract Review Report", "",
            f"**File:** {report.filename}  ",
            f"**Reviewed:** {report.reviewed_at[:19].replace('T', ' ')}  ",
            f"**Overall Risk:** {risk_icon} {report.overall_risk}  ",
            f"**Recommendation:** {report.recommendation}",
            "",
        ]

        # Contract Details
        lines += [
            "## Contract Details", "",
            "| Field | Value |",
            "|-------|-------|",
            f"| Type | {cmeta(m.get('contract_type'))} |",
            f"| Parties | {', '.join(m.get('parties', [])) or 'N/A'} |",
            f"| Effective Date | {cmeta(m.get('effective_date'))} |",
            f"| Expiration Date | {cmeta(m.get('expiration_date'))} |",
            f"| Governing Law | {cmeta(m.get('governing_law'))} |",
            f"| Auto-Renewal | {cmeta(m.get('auto_renewal'))} |",
            "",
        ]

        # Risk Summary
        lines += [
            "## Risk Summary", "",
            "| Risk Level | Count |",
            "|------------|-------|",
            f"| {E_HIGH} HIGH | {report.high_risk_count} |",
            f"| {E_MEDIUM} MEDIUM | {report.medium_risk_count} |",
            f"| {E_LOW} LOW | {report.low_risk_count} |",
            f"| {E_OK} ACCEPTABLE | {report.acceptable_count} |",
            f"| **Total** | **{report.total_clauses}** |",
            "",
        ]

        # Executive Summary — strip LLM-generated bold header if present
        summary = re.sub(
            r"^\*\*Executive Summary\*\*\s*", "",
            report.executive_summary or "",
            flags=re.IGNORECASE,
        ).strip()
        if summary:
            lines += ["## Executive Summary", "", summary, ""]

        # Clauses grouped by risk level
        SECTIONS = [
            ("HIGH",       f"## {E_HIGH} High Risk Clauses",    False),
            ("MEDIUM",     f"## {E_MEDIUM} Medium Risk Clauses", False),
            ("LOW",        f"## {E_LOW} Low Risk Clauses",       True),
            ("ACCEPTABLE", f"## {E_OK} Acceptable Clauses",      True),
        ]
        for level, sec_heading, compact in SECTIONS:
            revs = [r for r in report.clause_reviews if r.risk_level == level]
            if not revs:
                continue
            lines += [sec_heading, ""]
            for r in revs:
                lines += self._format_clause(r, compact=compact)

        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Markdown report saved: {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # Clause Formatter
    # ------------------------------------------------------------------

    def _format_clause(self, review, compact=False):
        CE = {"HIGH": E_HIGH, "MEDIUM": E_MEDIUM, "LOW": E_LOW, "ACCEPTABLE": E_OK}
        emoji = CE.get(review.risk_level, E_GREY)

        # Clean heading — truncate signature-block / sentence-length artifacts
        heading = self._clean(review.heading or review.clause_type or review.clause_id)
        if len(heading) > 72:
            heading = heading[:69] + "..."
        number  = f"{review.number} " if review.number else ""
        esc_tag = " *(risk escalated)*" if getattr(review, "escalated", False) else ""
        page    = getattr(review, "page_num", None)
        page_ok = page and str(page).strip() not in ("0", "None", "null", "")

        lines = [f"### {emoji} {number}{heading}{esc_tag}", ""]

        # ── Compact view (LOW / ACCEPTABLE) ─────────────────────────────
        if compact:
            if page_ok:
                lines += [f"**Location:** Page {page}  "]
            lines += [f"**Risk:** {review.risk_level} | **Type:** {review.clause_type}", ""]
            if review.issues:
                lines += [f"_{self._clean(review.issues[0])}_", ""]
            lines += ["---", ""]
            return lines

        # ── Full view (HIGH / MEDIUM) ────────────────────────────────────
        lines += [f"**Risk Level:** {review.risk_level}"]
        lines += [f"**Clause Type:** {review.clause_type}"]
        if page_ok:
            lines += [f"**Location:** Page {page}"]
        lines += [""]

        # Issues + Evidence
        if review.issues:
            lines += ["**Issues Found:**", ""]
            evidence = getattr(review, "evidence_quotes", [])

            for i, issue in enumerate(review.issues):
                clean_issue = self._clean(issue)
                ev_raw = evidence[i] if i < len(evidence) else ""
                ev = self._clean_evidence(ev_raw)

                # Bold the short problem label (before the dash), keep detail plain
                if " — " in clean_issue:
                    label, detail = clean_issue.split(" — ", 1)
                    issue_line = f"**{label.strip()}** — {detail.strip()}"
                elif " - " in clean_issue:
                    label, detail = clean_issue.split(" - ", 1)
                    issue_line = f"**{label.strip()}** - {detail.strip()}"
                else:
                    issue_line = f"**{clean_issue}**"

                lines += [f"**Issue {i+1}:** {issue_line}", ""]

                if ev != "N/A":
                    line_ref = self._find_line_ref(ev, getattr(review, "original_text", ""))
                    loc_parts = []
                    if page_ok:  loc_parts.append(f"Page {page}")
                    if line_ref: loc_parts.append(f"Line ~{line_ref}")
                    loc = f" *({', '.join(loc_parts)})*" if loc_parts else ""
                    lines += [
                        f'> {E_PIN} **Evidence{loc}:** "{ev}"',
                        "",
                    ]
                else:
                    lines += [
                        f"> {E_PIN} **Evidence:** N/A — no verbatim quote found in this clause",
                        "",
                    ]

        # Suggested Changes (Redlines)
        redlines = getattr(review, "redlines", [])
        good = [
            rd for rd in redlines
            if self._is_real(rd.get("replace", "")) and self._is_real(rd.get("with", ""))
        ]
        if good:
            lines += ["**Suggested Changes:**", ""]
            for j, rd in enumerate(good, 1):
                old_text  = self._clean_part(rd.get("replace", ""))
                new_text  = self._clean_part(rd.get("with", ""))
                full_sent = self._find_sentence(old_text, getattr(review, "original_text", ""))

                lines += [f"**Change {j} of {len(good)}:**", ""]

                # Show the full sentence so the change is self-explanatory
                if full_sent and full_sent.lower().strip() != old_text.lower().strip():
                    lines += [
                        "> **Contract context** — full sentence where this language appears:",
                        f'> *"{full_sent}"*',
                        "",
                    ]

                lines += [
                    "| | |",
                    "|---|---|",
                    f"| {E_X} **Current language** | {old_text} |",
                    f"| {E_OK} **Recommended change** | {new_text} |",
                    "",
                    f'> **Why this change:** The phrase *"{old_text}"* makes this obligation one-sided. '
                    f'Replacing it with *"{new_text}"* makes the obligation mutual so both parties are equally protected.',
                    "",
                ]
        elif review.redline_suggestion:
            rl = self._clean(review.redline_suggestion)
            if rl:
                lines += ["**Suggested Change:**", "", f"> {rl}", ""]

        # Overall Assessment
        if review.reasoning:
            r = self._clean(review.reasoning)
            if r:
                lines += ["**Overall Assessment:**", "", r, ""]

        lines += ["---", ""]
        return lines

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_line_ref(self, evidence: str, original_text: str) -> int:
        """Return approximate line number of evidence quote within clause text."""
        if not evidence or not original_text:
            return 0
        key = evidence[:40].lower().strip()
        for i, line in enumerate(original_text.split("\n"), 1):
            if key in line.lower():
                return i
        return 0

    def _find_sentence(self, fragment: str, original_text: str) -> str:
        """
        Find and return the full sentence in original_text that contains fragment.
        Used to give context around redlines so they read self-explanatorily.
        """
        if not fragment or not original_text:
            return ""
        flat = re.sub(r"-[ \t]*\n[ \t]*", "", original_text)
        flat = re.sub(r"\n", " ", flat)
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", flat)
        frag_lower = fragment.lower().strip()
        for sent in sentences:
            if frag_lower in sent.lower():
                sent = sent.strip()
                if len(sent) > 220:
                    idx = sent.lower().find(frag_lower)
                    s = max(0, idx - 70)
                    e = min(len(sent), idx + len(fragment) + 70)
                    sent = ("..." if s > 0 else "") + sent[s:e] + ("..." if e < len(sent) else "")
                return sent
        return ""

    def _clean(self, text: str) -> str:
        """Strip LLM artifacts: stray **, PDF hyphen line-breaks, excess newlines."""
        if not text:
            return ""
        text = re.sub(r"^\s*\*\*\s*", "", text)
        text = re.sub(r"\s*\*\*\s*$", "", text)
        text = re.sub(r"-[ \t]*\n[ \t]*", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _clean_evidence(self, ev: str) -> str:
        """
        Normalise evidence string:
        - All None / empty / dash variants → N/A
        - Cut IMPACT: leakage (LLM bleeds next field in)
        - Fix unbalanced quotes from LLM truncation (e.g. 'only against us"')
        """
        if not ev:
            return "N/A"
        ev = ev.strip()
        if ev.lower() in ("none", "none.", "n/a", "-", "") or ev.lower().startswith("none ("):
            return "N/A"
        ev = re.split(r"\s*IMPACT\s*:", ev, maxsplit=1)[0]
        ev = re.sub(r"-[ \t]*\n[ \t]*", "", ev)
        ev = ev.rstrip(" -\n").strip()
        # Fix lone trailing quote  e.g.  only against us"
        if ev.endswith('"') and ev.count('"') % 2 != 0:
            ev = ev[:-1].strip()
        # Fix lone leading quote
        if ev.startswith('"') and ev.count('"') % 2 != 0:
            ev = ev[1:].strip()
        return ev or "N/A"

    def _clean_part(self, text: str) -> str:
        """Clean a redline REPLACE or WITH value."""
        text = re.sub(r"\*\*", "", text)
        text = re.sub(r'"\s*$', "", text)
        text = re.sub(r"-[ \t]*\n[ \t]*", "", text)
        return text.strip()

    def _is_real(self, text: str) -> bool:
        """True if text is meaningful — not None / empty / dash / n/a."""
        return text.strip().lower() not in ("", "none", "-", "n/a")


# Singleton
exporter = ReportExporter()