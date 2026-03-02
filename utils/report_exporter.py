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

#         output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
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
utils/report_exporter.py — Export review reports to readable formats.
Supports: JSON (full data), Markdown (human-readable), plain text.
"""

import json
from pathlib import Path
from datetime import datetime
from loguru import logger


class ReportExporter:

    def export_json(self, report, output_path: Path) -> Path:
        """Export full report as JSON (machine-readable, for CLM database)."""
        data = {
            "filename": report.filename,
            "reviewed_at": report.reviewed_at,
            "overall_risk": report.overall_risk,
            "recommendation": report.recommendation,
            "metadata": report.metadata,
            "summary": {
                "total_clauses": report.total_clauses,
                "high_risk": report.high_risk_count,
                "medium_risk": report.medium_risk_count,
                "low_risk": report.low_risk_count,
                "acceptable": report.acceptable_count,
            },
            "executive_summary": report.executive_summary,
            "clause_reviews": [
                {
                    "clause_id": r.clause_id,
                    "number": r.number,
                    "heading": r.heading,
                    "clause_type": r.clause_type,
                    "risk_level": r.risk_level,
                    "issues": r.issues,
                    "redline_suggestion": r.redline_suggestion,
                    "reasoning": r.reasoning,
                    "original_text": r.original_text[:500],  # Truncate for storage
                }
                for r in report.clause_reviews
            ],
        }

        output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"JSON report saved: {output_path}")
        return output_path

    def export_markdown(self, report, output_path: Path) -> Path:
        """Export report as clean Markdown — the main human-readable format."""
        lines = []

        # Header
        risk_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(report.overall_risk, "⚪")
        lines += [
            f"# Contract Review Report",
            f"**File:** {report.filename}",
            f"**Reviewed:** {report.reviewed_at[:19].replace('T', ' ')}",
            f"**Overall Risk:** {risk_emoji} {report.overall_risk}",
            f"**Recommendation:** {report.recommendation}",
            "",
        ]

        # Metadata
        m = report.metadata
        lines += [
            "## Contract Details",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| Type | {m.get('contract_type', 'Unknown')} |",
            f"| Parties | {', '.join(m.get('parties', []))} |",
            f"| Effective Date | {m.get('effective_date', 'N/A')} |",
            f"| Expiration Date | {m.get('expiration_date', 'N/A')} |",
            f"| Governing Law | {m.get('governing_law', 'N/A')} |",
            f"| Auto-Renewal | {m.get('auto_renewal', 'N/A')} |",
            "",
        ]

        # Risk Summary
        lines += [
            "## Risk Summary",
            f"| Risk Level | Count |",
            f"|------------|-------|",
            f"| 🔴 HIGH | {report.high_risk_count} |",
            f"| 🟡 MEDIUM | {report.medium_risk_count} |",
            f"| 🔵 LOW | {report.low_risk_count} |",
            f"| ✅ ACCEPTABLE | {report.acceptable_count} |",
            f"| **Total** | **{report.total_clauses}** |",
            "",
        ]

        # Executive Summary
        lines += [
            "## Executive Summary",
            report.executive_summary,
            "",
        ]

        # High Risk Clauses first
        high_risk = [r for r in report.clause_reviews if r.risk_level == "HIGH"]
        if high_risk:
            lines += ["## 🔴 High Risk Clauses", ""]
            for r in high_risk:
                lines += self._format_clause_review(r)

        # Medium Risk
        medium_risk = [r for r in report.clause_reviews if r.risk_level == "MEDIUM"]
        if medium_risk:
            lines += ["## 🟡 Medium Risk Clauses", ""]
            for r in medium_risk:
                lines += self._format_clause_review(r)

        # Low + Acceptable (collapsed)
        other = [r for r in report.clause_reviews if r.risk_level in ("LOW", "ACCEPTABLE")]
        if other:
            lines += ["## Other Clauses", ""]
            for r in other:
                lines += self._format_clause_review(r, compact=True)

        content = "\n".join(lines)
        output_path.write_text(content, encoding="utf-8")
        logger.info(f"Markdown report saved: {output_path}")
        return output_path

    def _format_clause_review(self, review, compact: bool = False) -> list[str]:
        """Format a single clause review as markdown."""
        risk_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🔵", "ACCEPTABLE": "✅"}.get(review.risk_level, "⚪")
        heading = review.heading or review.clause_type or review.clause_id
        number = f"{review.number} " if review.number else ""

        escalated_tag = " *(risk escalated for consistency)*" if getattr(review, "escalated", False) else ""

        lines = [f"### {risk_emoji} {number}{heading}{escalated_tag}", ""]

        if compact:
            lines += [f"**Risk:** {review.risk_level} | **Type:** {review.clause_type}", ""]
            if review.issues:
                lines += [f"_{review.issues[0]}_", ""]
            return lines

        lines += [
            f"**Risk Level:** {review.risk_level}  ",
            f"**Clause Type:** {review.clause_type}",
            "",
        ]

        # Issues with evidence quotes
        if review.issues:
            lines += ["**Issues Found:**", ""]
            evidence = getattr(review, "evidence_quotes", [])
            for i, issue in enumerate(review.issues):
                lines += [f"**Issue {i+1}:** {issue}"]
                if i < len(evidence) and evidence[i]:
                    ev_quote = evidence[i]
                    lines += [f"> **Evidence:** *'{ev_quote}'*"]
                lines += [""]

        # Precise redlines (REPLACE → WITH)
        redlines = getattr(review, "redlines", [])
        if redlines:
            lines += ["**Precise Redlines:**", ""]
            for j, rd in enumerate(redlines, 1):
                lines += [
                    f"**Redline {j}:**",
                    f"~~{rd.get('replace', '')}~~",
                    f"→ `{rd.get('with', '')}`",
                    "",
                ]
        elif review.redline_suggestion:
            lines += [
                "**Suggested Redline:**",
                f"> {review.redline_suggestion}",
                "",
            ]

        if review.reasoning:
            lines += [
                "**Analysis:**",
                review.reasoning,
                "",
            ]

        lines += ["---", ""]
        return lines


# Singleton
exporter = ReportExporter()