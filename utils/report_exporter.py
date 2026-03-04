# """
# utils/report_exporter.py - Export review reports to files.
# Supports: JSON (machine-readable) and Markdown (human-readable / PDF-ready).
# """

# import json
# import re
# from pathlib import Path
# from loguru import logger

# # Emoji constants — defined as unicode escapes to avoid Windows encoding issues
# E_HIGH   = "\U0001f534"  # red circle
# E_MEDIUM = "\U0001f7e1"  # yellow circle
# E_LOW    = "\U0001f535"  # blue circle
# E_OK     = "\u2705"      # green check
# E_GREY   = "\u26aa"      # grey circle
# E_PIN    = "\U0001f4cc"  # pushpin
# E_X      = "\u274c"      # red X


# class ReportExporter:

#     # ------------------------------------------------------------------
#     # JSON Export
#     # ------------------------------------------------------------------

#     def export_json(self, report, output_path: Path) -> Path:
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
#                     "clause_id":          r.clause_id,
#                     "number":             r.number,
#                     "heading":            r.heading,
#                     "clause_type":        r.clause_type,
#                     "risk_level":         r.risk_level,
#                     "page_num":           getattr(r, "page_num", None),
#                     "issues":             r.issues,
#                     "evidence_quotes":    getattr(r, "evidence_quotes", []),
#                     "redlines":           getattr(r, "redlines", []),
#                     "new_clauses":        getattr(r, "new_clauses", []),
#                     "redline_suggestion": r.redline_suggestion,
#                     "reasoning":          r.reasoning,
#                     "original_text":      r.original_text[:500],
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
#         lines = []
#         m = report.metadata
#         RISK_EMOJI = {"HIGH": E_HIGH, "MEDIUM": E_MEDIUM, "LOW": E_LOW}
#         risk_icon = RISK_EMOJI.get(report.overall_risk, E_GREY)

#         def cmeta(val):
#             """Normalise metadata: None / 'null' / 'none' all become N/A."""
#             if val is None:
#                 return "N/A"
#             s = str(val).strip()
#             return "N/A" if s.lower() in ("null", "none", "") else s

#         # Header
#         lines += [
#             "# Contract Review Report", "",
#             f"**File:** {report.filename}  ",
#             f"**Reviewed:** {report.reviewed_at[:19].replace('T', ' ')}  ",
#             f"**Overall Risk:** {risk_icon} {report.overall_risk}  ",
#             f"**Recommendation:** {report.recommendation}",
#             "",
#         ]

#         # Contract Details
#         lines += [
#             "## Contract Details", "",
#             "| Field | Value |",
#             "|-------|-------|",
#             f"| Type | {cmeta(m.get('contract_type'))} |",
#             f"| Parties | {', '.join(m.get('parties', [])) or 'N/A'} |",
#             f"| Effective Date | {cmeta(m.get('effective_date'))} |",
#             f"| Expiration Date | {cmeta(m.get('expiration_date'))} |",
#             f"| Governing Law | {cmeta(m.get('governing_law'))} |",
#             f"| Auto-Renewal | {cmeta(m.get('auto_renewal'))} |",
#             "",
#         ]

#         # Risk Summary
#         lines += [
#             "## Risk Summary", "",
#             "| Risk Level | Count |",
#             "|------------|-------|",
#             f"| {E_HIGH} HIGH | {report.high_risk_count} |",
#             f"| {E_MEDIUM} MEDIUM | {report.medium_risk_count} |",
#             f"| {E_LOW} LOW | {report.low_risk_count} |",
#             f"| {E_OK} ACCEPTABLE | {report.acceptable_count} |",
#             f"| **Total** | **{report.total_clauses}** |",
#             "",
#         ]

#         # Executive Summary — strip LLM-generated bold header if present
#         summary = re.sub(
#             r"^\*\*Executive Summary\*\*\s*", "",
#             report.executive_summary or "",
#             flags=re.IGNORECASE,
#         ).strip()
#         if summary:
#             lines += ["## Executive Summary", "", summary, ""]

#         # Clauses grouped by risk level
#         SECTIONS = [
#             ("HIGH",       f"## {E_HIGH} High Risk Clauses",    False),
#             ("MEDIUM",     f"## {E_MEDIUM} Medium Risk Clauses", False),
#             ("LOW",        f"## {E_LOW} Low Risk Clauses",       True),
#             ("ACCEPTABLE", f"## {E_OK} Acceptable Clauses",      True),
#         ]
#         for level, sec_heading, compact in SECTIONS:
#             revs = [r for r in report.clause_reviews if r.risk_level == level]
#             if not revs:
#                 continue
#             lines += [sec_heading, ""]
#             for r in revs:
#                 lines += self._format_clause(r, compact=compact)

#         output_path.write_text("\n".join(lines), encoding="utf-8")
#         logger.info(f"Markdown report saved: {output_path}")
#         return output_path

#     # ------------------------------------------------------------------
#     # Clause Formatter
#     # ------------------------------------------------------------------

#     def _format_clause(self, review, compact=False):
#         CE = {"HIGH": E_HIGH, "MEDIUM": E_MEDIUM, "LOW": E_LOW, "ACCEPTABLE": E_OK}
#         emoji = CE.get(review.risk_level, E_GREY)

#         # Clean heading — truncate signature-block / sentence-length artifacts
#         heading = self._clean(review.heading or review.clause_type or review.clause_id)
#         if len(heading) > 72:
#             heading = heading[:69] + "..."
#         number  = f"{review.number} " if review.number else ""
#         esc_tag = " *(risk escalated)*" if getattr(review, "escalated", False) else ""
#         page    = getattr(review, "page_num", None)
#         page_ok = page and str(page).strip() not in ("0", "None", "null", "")

#         lines = [f"### {emoji} {number}{heading}{esc_tag}", ""]

#         # ── Compact view (LOW / ACCEPTABLE) ─────────────────────────────
#         if compact:
#             if page_ok:
#                 lines += [f"**Location:** Page {page}  "]
#             lines += [f"**Risk:** {review.risk_level} | **Type:** {review.clause_type}", ""]
#             if review.issues:
#                 lines += [f"_{self._clean(review.issues[0])}_", ""]
#             lines += ["---", ""]
#             return lines

#         # ── Full view (HIGH / MEDIUM) ────────────────────────────────────
#         lines += [f"**Risk Level:** {review.risk_level}"]
#         lines += [f"**Clause Type:** {review.clause_type}"]
#         if page_ok:
#             lines += [f"**Location:** Page {page}"]
#         lines += [""]

#         # Issues + Evidence
#         if review.issues:
#             lines += ["**Issues Found:**", ""]
#             evidence = getattr(review, "evidence_quotes", [])

#             for i, issue in enumerate(review.issues):
#                 clean_issue = self._clean(issue)
#                 ev_raw = evidence[i] if i < len(evidence) else ""
#                 ev = self._clean_evidence(ev_raw)

#                 # Bold the short problem label (before the dash), keep detail plain
#                 if " — " in clean_issue:
#                     label, detail = clean_issue.split(" — ", 1)
#                     issue_line = f"**{label.strip()}** — {detail.strip()}"
#                 elif " - " in clean_issue:
#                     label, detail = clean_issue.split(" - ", 1)
#                     issue_line = f"**{label.strip()}** - {detail.strip()}"
#                 else:
#                     issue_line = f"**{clean_issue}**"

#                 lines += [f"**Issue {i+1}:** {issue_line}", ""]

#                 if ev != "N/A":
#                     line_ref = self._find_line_ref(ev, getattr(review, "original_text", ""))
#                     loc_parts = []
#                     if page_ok:  loc_parts.append(f"Page {page}")
#                     if line_ref: loc_parts.append(f"Line ~{line_ref}")
#                     loc = f" *({', '.join(loc_parts)})*" if loc_parts else ""
#                     lines += [
#                         f'> {E_PIN} **Evidence{loc}:** "{ev}"',
#                         "",
#                     ]
#                 else:
#                     lines += [
#                         f"> {E_PIN} **Evidence:** N/A — no verbatim quote found in this clause",
#                         "",
#                     ]

#         # Suggested Changes (Redlines)
#         redlines = getattr(review, "redlines", [])
#         good = [
#             rd for rd in redlines
#             if self._is_real(rd.get("replace", "")) and self._is_real(rd.get("with", ""))
#         ]
#         if good:
#             lines += ["**Suggested Changes:**", ""]
#             for j, rd in enumerate(good, 1):
#                 old_text  = self._clean_part(rd.get("replace", ""))
#                 new_text  = self._clean_part(rd.get("with", ""))
#                 full_sent = self._find_sentence(old_text, getattr(review, "original_text", ""))

#                 lines += [f"**Change {j} of {len(good)}:**", ""]

#                 # Show the full sentence so the change is self-explanatory
#                 if full_sent and full_sent.lower().strip() != old_text.lower().strip():
#                     lines += [
#                         "> **Contract context** — full sentence where this language appears:",
#                         f'> *"{full_sent}"*',
#                         "",
#                     ]

#                 lines += [
#                     "| | |",
#                     "|---|---|",
#                     f"| {E_X} **Current language** | {old_text} |",
#                     f"| {E_OK} **Recommended change** | {new_text} |",
#                     "",
#                     f'> **Why this change:** The phrase *"{old_text}"* makes this obligation one-sided. '
#                     f'Replacing it with *"{new_text}"* makes the obligation mutual so both parties are equally protected.',
#                     "",
#                 ]
#         elif review.redline_suggestion:
#             rl = self._clean(review.redline_suggestion)
#             if rl:
#                 lines += ["**Suggested Change:**", "", f"> {rl}", ""]

#         # Proposed New Clauses
#         new_clauses = getattr(review, "new_clauses", [])
#         if new_clauses:
#             lines += ["**Proposed New Clauses:**", ""]
#             lines += [
#                 "> These clauses do not exist in the current contract.",
#                 "> They should be **added** to address the missing obligations identified above.",
#                 "",
#             ]
#             for nc in new_clauses:
#                 title  = nc.get("title", "New Clause")
#                 reason = nc.get("reason", "")
#                 text   = nc.get("text", "")
#                 if not text:
#                     continue
#                 lines += [
#                     f"**✏ Proposed: {title}**",
#                     "",
#                 ]
#                 if reason:
#                     lines += [f"> **Why needed:** {reason}", ""]
#                 lines += [
#                     "```",
#                     text,
#                     "```",
#                     "",
#                 ]

#         # Overall Assessment
#         if review.reasoning:
#             r = self._clean(review.reasoning)
#             if r:
#                 lines += ["**Overall Assessment:**", "", r, ""]

#         lines += ["---", ""]
#         return lines

#     # ------------------------------------------------------------------
#     # Helpers
#     # ------------------------------------------------------------------

#     def _find_line_ref(self, evidence: str, original_text: str) -> int:
#         """Return approximate line number of evidence quote within clause text."""
#         if not evidence or not original_text:
#             return 0
#         key = evidence[:40].lower().strip()
#         for i, line in enumerate(original_text.split("\n"), 1):
#             if key in line.lower():
#                 return i
#         return 0

#     def _find_sentence(self, fragment: str, original_text: str) -> str:
#         """
#         Find and return the full sentence in original_text that contains fragment.
#         Used to give context around redlines so they read self-explanatorily.
#         """
#         if not fragment or not original_text:
#             return ""
#         flat = re.sub(r"-[ \t]*\n[ \t]*", "", original_text)
#         flat = re.sub(r"\n", " ", flat)
#         sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", flat)
#         frag_lower = fragment.lower().strip()
#         for sent in sentences:
#             if frag_lower in sent.lower():
#                 sent = sent.strip()
#                 if len(sent) > 220:
#                     idx = sent.lower().find(frag_lower)
#                     s = max(0, idx - 70)
#                     e = min(len(sent), idx + len(fragment) + 70)
#                     sent = ("..." if s > 0 else "") + sent[s:e] + ("..." if e < len(sent) else "")
#                 return sent
#         return ""

#     def _clean(self, text: str) -> str:
#         """Strip LLM artifacts: stray **, PDF hyphen line-breaks, excess newlines."""
#         if not text:
#             return ""
#         text = re.sub(r"^\s*\*\*\s*", "", text)
#         text = re.sub(r"\s*\*\*\s*$", "", text)
#         text = re.sub(r"-[ \t]*\n[ \t]*", "", text)
#         text = re.sub(r"\n{3,}", "\n\n", text)
#         return text.strip()

#     def _clean_evidence(self, ev: str) -> str:
#         """
#         Normalise evidence string:
#         - All None / empty / dash variants → N/A
#         - Cut IMPACT: leakage (LLM bleeds next field in)
#         - Fix unbalanced quotes from LLM truncation (e.g. 'only against us"')
#         """
#         if not ev:
#             return "N/A"
#         ev = ev.strip()
#         if ev.lower() in ("none", "none.", "n/a", "-", "") or ev.lower().startswith("none ("):
#             return "N/A"
#         ev = re.split(r"\s*IMPACT\s*:", ev, maxsplit=1)[0]
#         ev = re.sub(r"-[ \t]*\n[ \t]*", "", ev)
#         ev = ev.rstrip(" -\n").strip()
#         # Fix lone trailing quote  e.g.  only against us"
#         if ev.endswith('"') and ev.count('"') % 2 != 0:
#             ev = ev[:-1].strip()
#         # Fix lone leading quote
#         if ev.startswith('"') and ev.count('"') % 2 != 0:
#             ev = ev[1:].strip()
#         return ev or "N/A"

#     def _clean_part(self, text: str) -> str:
#         """Clean a redline REPLACE or WITH value."""
#         text = re.sub(r"\*\*", "", text)
#         text = re.sub(r'"\s*$', "", text)
#         text = re.sub(r"-[ \t]*\n[ \t]*", "", text)
#         return text.strip()

#     def _is_real(self, text: str) -> bool:
#         """True if text is meaningful — not None / empty / dash / n/a."""
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
                    "new_clauses":        getattr(r, "new_clauses", []),
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
        # Strip bold header like **Executive Summary** or **Executive Summary: Company NDA**
        summary = re.sub(
            r"^\*\*Executive Summary[^*]*\*\*\s*", "",
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

                # Strip any ** the LLM already added to avoid double-bold
                clean_issue = re.sub(r"^\*\*(.+?)\*\*\s*[—-]?\s*", r"\1 — ", clean_issue, count=1) if re.match(r"^\*\*", clean_issue) else clean_issue
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
                    if page_ok:                    loc_parts.append(f"Page {page}")
                    if line_ref and line_ref > 0:  loc_parts.append(f"Line ~{line_ref}")
                    loc = f" *({', '.join(loc_parts)})*" if loc_parts else " *(location unavailable)*"
                    lines += [
                        f"\n> {E_PIN} **Evidence{loc}:**",
                        f'> *"{ev}"*',
                        "",
                    ]
                else:
                    lines += [
                        f"\n> {E_PIN} **Evidence:** N/A — no direct quote found in this clause",
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

                # Pull the matching issue description for this redline (same index)
                issues_list = review.issues if review.issues else []
                why_text = ""
                if j - 1 < len(issues_list):
                    raw_why = self._clean(issues_list[j - 1])
                    raw_why = re.sub(r"^\*\*(.+?)\*\*\s*[—-]?\s*", r"\1: ", raw_why, count=1)
                    if " — " in raw_why:
                        why_text = raw_why.split(" — ", 1)[1].strip()
                    elif " - " in raw_why:
                        why_text = raw_why.split(" - ", 1)[1].strip()
                    elif ": " in raw_why:
                        why_text = raw_why.split(": ", 1)[1].strip()
                    else:
                        why_text = raw_why
                if not why_text:
                    why_text = "This change addresses the issue identified above."

                lines += [
                    "| | |",
                    "|---|---|",
                    f"| {E_X} **Current language** | {old_text} |",
                    f"| {E_OK} **Recommended change** | {new_text} |",
                    "",
                    f"> **Why:** {why_text}",
                    "",
                ]
        elif review.redline_suggestion:
            rl = self._clean(review.redline_suggestion)
            if rl:
                lines += ["**Suggested Change:**", "", f"> {rl}", ""]

        # Proposed New Clauses
        new_clauses = getattr(review, "new_clauses", [])
        if new_clauses:
            lines += ["**Proposed New Clauses:**", ""]
            lines += [
                "> These clauses do not exist in the current contract.",
                "> They should be **added** to address the missing obligations identified above.",
                "",
            ]
            for nc in new_clauses:
                title  = nc.get("title", "New Clause")
                reason = nc.get("reason", "")
                text   = nc.get("text", "")
                if not text:
                    continue
                lines += [
                    f"**✏ Proposed: {title}**",
                    "",
                ]
                if reason:
                    lines += [f"> **Why needed:** {reason}", ""]
                lines += [
                    "```",
                    text,
                    "```",
                    "",
                ]

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