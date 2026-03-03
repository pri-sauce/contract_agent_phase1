# # """
# # utils/report_exporter.py — Export review reports to readable formats.
# # Supports: JSON (full data), Markdown (human-readable), plain text.
# # """

# # import json
# # from pathlib import Path
# # from datetime import datetime
# # from loguru import logger


# # class ReportExporter:

# #     def export_json(self, report, output_path: Path) -> Path:
# #         """Export full report as JSON (machine-readable, for CLM database)."""
# #         data = {
# #             "filename": report.filename,
# #             "reviewed_at": report.reviewed_at,
# #             "overall_risk": report.overall_risk,
# #             "recommendation": report.recommendation,
# #             "metadata": report.metadata,
# #             "summary": {
# #                 "total_clauses": report.total_clauses,
# #                 "high_risk": report.high_risk_count,
# #                 "medium_risk": report.medium_risk_count,
# #                 "low_risk": report.low_risk_count,
# #                 "acceptable": report.acceptable_count,
# #             },
# #             "executive_summary": report.executive_summary,
# #             "clause_reviews": [
# #                 {
# #                     "clause_id": r.clause_id,
# #                     "number": r.number,
# #                     "heading": r.heading,
# #                     "clause_type": r.clause_type,
# #                     "risk_level": r.risk_level,
# #                     "issues": r.issues,
# #                     "redline_suggestion": r.redline_suggestion,
# #                     "reasoning": r.reasoning,
# #                     "original_text": r.original_text[:500],  # Truncate for storage
# #                 }
# #                 for r in report.clause_reviews
# #             ],
# #         }

# #         output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
# #         logger.info(f"JSON report saved: {output_path}")
# #         return output_path

# #     def export_markdown(self, report, output_path: Path) -> Path:
# #         """Export report as clean Markdown — the main human-readable format."""
# #         lines = []

# #         # Header
# #         risk_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(report.overall_risk, "⚪")
# #         lines += [
# #             f"# Contract Review Report",
# #             f"**File:** {report.filename}",
# #             f"**Reviewed:** {report.reviewed_at[:19].replace('T', ' ')}",
# #             f"**Overall Risk:** {risk_emoji} {report.overall_risk}",
# #             f"**Recommendation:** {report.recommendation}",
# #             "",
# #         ]

# #         # Metadata
# #         m = report.metadata
# #         lines += [
# #             "## Contract Details",
# #             f"| Field | Value |",
# #             f"|-------|-------|",
# #             f"| Type | {m.get('contract_type', 'Unknown')} |",
# #             f"| Parties | {', '.join(m.get('parties', []))} |",
# #             f"| Effective Date | {m.get('effective_date', 'N/A')} |",
# #             f"| Expiration Date | {m.get('expiration_date', 'N/A')} |",
# #             f"| Governing Law | {m.get('governing_law', 'N/A')} |",
# #             f"| Auto-Renewal | {m.get('auto_renewal', 'N/A')} |",
# #             "",
# #         ]

# #         # Risk Summary
# #         lines += [
# #             "## Risk Summary",
# #             f"| Risk Level | Count |",
# #             f"|------------|-------|",
# #             f"| 🔴 HIGH | {report.high_risk_count} |",
# #             f"| 🟡 MEDIUM | {report.medium_risk_count} |",
# #             f"| 🔵 LOW | {report.low_risk_count} |",
# #             f"| ✅ ACCEPTABLE | {report.acceptable_count} |",
# #             f"| **Total** | **{report.total_clauses}** |",
# #             "",
# #         ]

# #         # Executive Summary
# #         lines += [
# #             "## Executive Summary",
# #             report.executive_summary,
# #             "",
# #         ]

# #         # High Risk Clauses first
# #         high_risk = [r for r in report.clause_reviews if r.risk_level == "HIGH"]
# #         if high_risk:
# #             lines += ["## 🔴 High Risk Clauses", ""]
# #             for r in high_risk:
# #                 lines += self._format_clause_review(r)

# #         # Medium Risk
# #         medium_risk = [r for r in report.clause_reviews if r.risk_level == "MEDIUM"]
# #         if medium_risk:
# #             lines += ["## 🟡 Medium Risk Clauses", ""]
# #             for r in medium_risk:
# #                 lines += self._format_clause_review(r)

# #         # Low + Acceptable (collapsed)
# #         other = [r for r in report.clause_reviews if r.risk_level in ("LOW", "ACCEPTABLE")]
# #         if other:
# #             lines += ["## Other Clauses", ""]
# #             for r in other:
# #                 lines += self._format_clause_review(r, compact=True)

# #         content = "\n".join(lines)
# #         output_path.write_text(content, encoding="utf-8")
# #         logger.info(f"Markdown report saved: {output_path}")
# #         return output_path

# #     def _format_clause_review(self, review, compact: bool = False) -> list[str]:
# #         """Format a single clause review as markdown."""
# #         risk_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵", "ACCEPTABLE": "✅"}.get(review.risk_level, "⚪")
# #         heading = review.heading or review.clause_type or review.clause_id
# #         number = f"{review.number} " if review.number else ""

# #         escalated_tag = " *(risk escalated for consistency)*" if getattr(review, "escalated", False) else ""

# #         lines = [f"### {risk_emoji} {number}{heading}{escalated_tag}", ""]

# #         if compact:
# #             lines += [f"**Risk:** {review.risk_level} | **Type:** {review.clause_type}", ""]
# #             if review.issues:
# #                 lines += [f"_{review.issues[0]}_", ""]
# #             return lines

# #         lines += [
# #             f"**Risk Level:** {review.risk_level}  ",
# #             f"**Clause Type:** {review.clause_type}",
# #             "",
# #         ]

# #         # Issues with evidence quotes
# #         if review.issues:
# #             lines += ["**Issues Found:**", ""]
# #             evidence = getattr(review, "evidence_quotes", [])
# #             for i, issue in enumerate(review.issues):
# #                 lines += [f"**Issue {i+1}:** {issue}"]
# #                 if i < len(evidence) and evidence[i]:
# #                     ev_quote = evidence[i]
# #                     lines += [f"> **Evidence:** *'{ev_quote}'*"]
# #                 lines += [""]

# #         # Precise redlines (REPLACE → WITH)
# #         redlines = getattr(review, "redlines", [])
# #         if redlines:
# #             lines += ["**Precise Redlines:**", ""]
# #             for j, rd in enumerate(redlines, 1):
# #                 lines += [
# #                     f"**Redline {j}:**",
# #                     f"~~{rd.get('replace', '')}~~",
# #                     f"→ `{rd.get('with', '')}`",
# #                     "",
# #                 ]
# #         elif review.redline_suggestion:
# #             lines += [
# #                 "**Suggested Redline:**",
# #                 f"> {review.redline_suggestion}",
# #                 "",
# #             ]

# #         if review.reasoning:
# #             lines += [
# #                 "**Analysis:**",
# #                 review.reasoning,
# #                 "",
# #             ]

# #         lines += ["---", ""]
# #         return lines


# # # Singleton
# # exporter = ReportExporter()



# """
# utils/report_exporter.py — Export review reports to readable formats.
# Supports: JSON (full data), Markdown (human-readable), plain text.
# """

# import json
# from pathlib import Path
# from datetime import datetime
# from loguru import logger


# class ReportExporter:

#     def export_json(self, report, output_path: Path) -> Path:
#         """Export full report as JSON (machine-readable, for CLM database)."""
#         data = {
#             "filename": report.filename,
#             "reviewed_at": report.reviewed_at,
#             "overall_risk": report.overall_risk,
#             "recommendation": report.recommendation,
#             "metadata": report.metadata,
#             "summary": {
#                 "total_clauses": report.total_clauses,
#                 "high_risk": report.high_risk_count,
#                 "medium_risk": report.medium_risk_count,
#                 "low_risk": report.low_risk_count,
#                 "acceptable": report.acceptable_count,
#             },
#             "executive_summary": report.executive_summary,
#             "clause_reviews": [
#                 {
#                     "clause_id": r.clause_id,
#                     "number": r.number,
#                     "heading": r.heading,
#                     "clause_type": r.clause_type,
#                     "risk_level": r.risk_level,
#                     "issues": r.issues,
#                     "redline_suggestion": r.redline_suggestion,
#                     "reasoning": r.reasoning,
#                     "original_text": r.original_text[:500],  # Truncate for storage
#                 }
#                 for r in report.clause_reviews
#             ],
#         }

#         output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
#         logger.info(f"JSON report saved: {output_path}")
#         return output_path

#     def export_markdown(self, report, output_path: Path) -> Path:
#         """Export report as clean Markdown — the main human-readable format."""
#         lines = []

#         # Header
#         risk_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(report.overall_risk, "⚪")
#         lines += [
#             f"# Contract Review Report",
#             f"**File:** {report.filename}",
#             f"**Reviewed:** {report.reviewed_at[:19].replace('T', ' ')}",
#             f"**Overall Risk:** {risk_emoji} {report.overall_risk}",
#             f"**Recommendation:** {report.recommendation}",
#             "",
#         ]

#         # Metadata
#         m = report.metadata
#         lines += [
#             "## Contract Details",
#             f"| Field | Value |",
#             f"|-------|-------|",
#             f"| Type | {m.get('contract_type', 'Unknown')} |",
#             f"| Parties | {', '.join(m.get('parties', []))} |",
#             f"| Effective Date | {m.get('effective_date', 'N/A')} |",
#             f"| Expiration Date | {m.get('expiration_date', 'N/A')} |",
#             f"| Governing Law | {m.get('governing_law', 'N/A')} |",
#             f"| Auto-Renewal | {m.get('auto_renewal', 'N/A')} |",
#             "",
#         ]

#         # Risk Summary
#         lines += [
#             "## Risk Summary",
#             f"| Risk Level | Count |",
#             f"|------------|-------|",
#             f"| 🔴 HIGH | {report.high_risk_count} |",
#             f"| 🟡 MEDIUM | {report.medium_risk_count} |",
#             f"| 🔵 LOW | {report.low_risk_count} |",
#             f"| ✅ ACCEPTABLE | {report.acceptable_count} |",
#             f"| **Total** | **{report.total_clauses}** |",
#             "",
#         ]

#         # Executive Summary
#         lines += [
#             "## Executive Summary",
#             report.executive_summary,
#             "",
#         ]

#         # High Risk Clauses first
#         high_risk = [r for r in report.clause_reviews if r.risk_level == "HIGH"]
#         if high_risk:
#             lines += ["## 🔴 High Risk Clauses", ""]
#             for r in high_risk:
#                 lines += self._format_clause_review(r)

#         # Medium Risk
#         medium_risk = [r for r in report.clause_reviews if r.risk_level == "MEDIUM"]
#         if medium_risk:
#             lines += ["## 🟡 Medium Risk Clauses", ""]
#             for r in medium_risk:
#                 lines += self._format_clause_review(r)

#         # Low + Acceptable (collapsed)
#         other = [r for r in report.clause_reviews if r.risk_level in ("LOW", "ACCEPTABLE")]
#         if other:
#             lines += ["## Other Clauses", ""]
#             for r in other:
#                 lines += self._format_clause_review(r, compact=True)

#         content = "\n".join(lines)
#         output_path.write_text(content, encoding="utf-8")
#         logger.info(f"Markdown report saved: {output_path}")
#         return output_path

#     def _format_clause_review(self, review, compact: bool = False) -> list[str]:
#         """Format a single clause review as markdown."""
#         risk_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵", "ACCEPTABLE": "✅"}.get(review.risk_level, "⚪")
#         heading = review.heading or review.clause_type or review.clause_id
#         number = f"{review.number} " if review.number else ""

#         escalated_tag = " *(risk escalated for consistency)*" if getattr(review, "escalated", False) else ""

#         lines = [f"### {risk_emoji} {number}{heading}{escalated_tag}", ""]

#         if compact:
#             lines += [f"**Risk:** {review.risk_level} | **Type:** {review.clause_type}", ""]
#             if review.issues:
#                 lines += [f"_{review.issues[0]}_", ""]
#             return lines

#         lines += [
#             f"**Risk Level:** {review.risk_level}  ",
#             f"**Clause Type:** {review.clause_type}",
#             "",
#         ]

#         # Issues with evidence quotes
#         if review.issues:
#             lines += ["**Issues Found:**", ""]
#             evidence = getattr(review, "evidence_quotes", [])
#             for i, issue in enumerate(review.issues):
#                 lines += [f"**Issue {i+1}:** {issue}"]
#                 if i < len(evidence) and evidence[i]:
#                     ev_quote = evidence[i]
#                     lines += [f"> **Evidence:** *'{ev_quote}'*"]
#                 lines += [""]

#         # Precise redlines (REPLACE → WITH)
#         redlines = getattr(review, "redlines", [])
#         if redlines:
#             lines += ["**Precise Redlines:**", ""]
#             for j, rd in enumerate(redlines, 1):
#                 lines += [
#                     f"**Redline {j}:**",
#                     f"~~{rd.get('replace', '')}~~",
#                     f"→ `{rd.get('with', '')}`",
#                     "",
#                 ]
#         elif review.redline_suggestion:
#             lines += [
#                 "**Suggested Redline:**",
#                 f"> {review.redline_suggestion}",
#                 "",
#             ]

#         if review.reasoning:
#             lines += [
#                 "**Analysis:**",
#                 review.reasoning,
#                 "",
#             ]

#         lines += ["---", ""]
#         return lines


# # Singleton
# exporter = ReportExporter()

"""
utils/report_exporter.py — Export review reports to files.
Supports: JSON (machine-readable) and Markdown (human-readable / PDF-ready).
"""

import json
import re
from pathlib import Path
from loguru import logger


class ReportExporter:

    # ------------------------------------------------------------------
    # JSON Export
    # ------------------------------------------------------------------

    def export_json(self, report, output_path: Path) -> Path:
        """Export full report as JSON."""
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
                    "clause_id":        r.clause_id,
                    "number":           r.number,
                    "heading":          r.heading,
                    "clause_type":      r.clause_type,
                    "risk_level":       r.risk_level,
                    "issues":           r.issues,
                    "redline_suggestion": r.redline_suggestion,
                    "reasoning":        r.reasoning,
                    "original_text":    r.original_text[:500],
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
        """Export report as clean, PDF-ready Markdown."""
        lines = []
        risk_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(report.overall_risk, "⚪")

        # Header
        lines += [
            "# Contract Review Report",
            "",
            f"**File:** {report.filename}  ",
            f"**Reviewed:** {report.reviewed_at[:19].replace('T', ' ')}  ",
            f"**Overall Risk:** {risk_emoji} {report.overall_risk}  ",
            f"**Recommendation:** {report.recommendation}",
            "",
        ]

        # Contract details table
        m = report.metadata
        lines += [
            "## Contract Details",
            "",
            "| Field | Value |",
            "|-------|-------|",
            f"| Type | {m.get('contract_type', 'Unknown')} |",
            f"| Parties | {', '.join(m.get('parties', []))} |",
            f"| Effective Date | {m.get('effective_date', 'N/A')} |",
            f"| Expiration Date | {m.get('expiration_date', 'N/A')} |",
            f"| Governing Law | {m.get('governing_law', 'N/A')} |",
            f"| Auto-Renewal | {m.get('auto_renewal', 'N/A')} |",
            "",
        ]

        # Risk summary table
        lines += [
            "## Risk Summary",
            "",
            "| Risk Level | Count |",
            "|------------|-------|",
            f"| 🔴 HIGH | {report.high_risk_count} |",
            f"| 🟡 MEDIUM | {report.medium_risk_count} |",
            f"| 🔵 LOW | {report.low_risk_count} |",
            f"| ✅ ACCEPTABLE | {report.acceptable_count} |",
            f"| **Total** | **{report.total_clauses}** |",
            "",
        ]

        # Executive summary — strip LLM bold header if present
        summary = re.sub(r"^\*\*Executive Summary\*\*\s*", "", report.executive_summary or "", flags=re.IGNORECASE).strip()
        if summary:
            lines += ["## Executive Summary", "", summary, ""]

        # Clauses grouped by risk
        high   = [r for r in report.clause_reviews if r.risk_level == "HIGH"]
        medium = [r for r in report.clause_reviews if r.risk_level == "MEDIUM"]
        low    = [r for r in report.clause_reviews if r.risk_level == "LOW"]
        ok     = [r for r in report.clause_reviews if r.risk_level == "ACCEPTABLE"]

        if high:
            lines += ["## 🔴 High Risk Clauses", ""]
            for r in high:
                lines += self._format_clause(r)

        if medium:
            lines += ["## 🟡 Medium Risk Clauses", ""]
            for r in medium:
                lines += self._format_clause(r)

        if low:
            lines += ["## 🔵 Low Risk Clauses", ""]
            for r in low:
                lines += self._format_clause(r, compact=True)

        if ok:
            lines += ["## ✅ Acceptable Clauses", ""]
            for r in ok:
                lines += self._format_clause(r, compact=True)

        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Markdown report saved: {output_path}")
        return output_path

    # ------------------------------------------------------------------
    # Clause Formatter
    # ------------------------------------------------------------------

    def _format_clause(self, review, compact: bool = False) -> list[str]:
        """Format one clause review into clean markdown lines."""
        EMOJI = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵", "ACCEPTABLE": "✅"}
        emoji   = EMOJI.get(review.risk_level, "⚪")
        heading = review.heading or review.clause_type or review.clause_id
        number  = f"{review.number} " if review.number else ""
        esc_tag = " *(risk escalated)*" if getattr(review, "escalated", False) else ""

        lines = [f"### {emoji} {number}{heading}{esc_tag}", ""]

        if compact:
            lines += [
                f"**Risk:** {review.risk_level} | **Type:** {review.clause_type}",
                "",
            ]
            if review.issues:
                lines += [f"_{self._clean(review.issues[0])}_", ""]
            lines += ["---", ""]
            return lines

        lines += [
            f"**Risk Level:** {review.risk_level}",
            f"**Clause Type:** {review.clause_type}",
            "",
        ]

        # Issues + evidence
        if review.issues:
            lines += ["**Issues Found:**", ""]
            evidence = getattr(review, "evidence_quotes", [])
            for i, issue in enumerate(review.issues):
                ev = self._clean_evidence(evidence[i] if i < len(evidence) else "")
                lines += [
                    f"**Issue {i+1}:** {self._clean(issue)}",
                    "",
                    f"> **Evidence:** {ev}",
                    "",
                ]

        # Redlines — skip junk entries where replace/with is None/empty/dash
        redlines = getattr(review, "redlines", [])
        good_redlines = [
            rd for rd in redlines
            if self._is_real(rd.get("replace", ""))
            and self._is_real(rd.get("with", ""))
        ]
        if good_redlines:
            lines += ["**Precise Redlines:**", ""]
            for j, rd in enumerate(good_redlines, 1):
                lines += [
                    f"**Redline {j}:**",
                    "",
                    f"~~{self._clean_part(rd['replace'])}~~",
                    "",
                    f"→ {self._clean_part(rd['with'])}",
                    "",
                ]
        elif review.redline_suggestion:
            rl = self._clean(review.redline_suggestion)
            if rl:
                lines += ["**Suggested Redline:**", "", f"> {rl}", ""]

        # Analysis
        if review.reasoning:
            r = self._clean(review.reasoning)
            if r:
                lines += ["**Analysis:**", "", r, ""]

        lines += ["---", ""]
        return lines

    # ------------------------------------------------------------------
    # Cleaning Helpers
    # ------------------------------------------------------------------

    def _clean(self, text: str) -> str:
        """Remove LLM artifacts: stray **, PDF hyphen line-breaks, excess newlines."""
        if not text:
            return ""
        text = re.sub(r"^\s*\*\*\s*", "", text)       # leading **
        text = re.sub(r"\s*\*\*\s*$", "", text)       # trailing **
        text = re.sub(r"-[ \t]*\n[ \t]*", "", text)   # PDF hyphen break e.g. "man-\nagement"
        text = re.sub(r"\n{3,}", "\n\n", text)        # excess blank lines
        return text.strip()

    def _clean_evidence(self, ev: str) -> str:
        """
        Normalise an evidence string.
        - Returns N/A for empty / None / dash values
        - Cuts off IMPACT: leakage (LLM sometimes continues into next field)
        """
        if not ev:
            return "N/A"
        ev = ev.strip()
        if ev.lower() in ("none", "none.", "n/a", "-", "") or ev.lower().startswith("none ("):
            return "N/A"
        # Cut anything after IMPACT: — that's a different field bleeding in
        ev = re.split(r"\s*IMPACT\s*:", ev, maxsplit=1)[0]
        ev = re.sub(r"-[ \t]*\n[ \t]*", "", ev)   # PDF hyphen break inside evidence
        ev = ev.rstrip(" -\n").strip()
        return ev or "N/A"

    def _clean_part(self, text: str) -> str:
        """Clean a redline REPLACE or WITH value."""
        text = re.sub(r"\*\*", "", text)
        text = re.sub(r'"\s*$', "", text)
        text = re.sub(r"-[ \t]*\n[ \t]*", "", text)
        return text.strip()

    def _is_real(self, text: str) -> bool:
        """Return True if a redline part is meaningful (not None/empty/dash)."""
        return text.strip().lower() not in ("", "none", "-", "n/a")


# Singleton
exporter = ReportExporter()