# """
# prompts/review_prompts.py — All LLM prompts for contract review.

# Design principles:
# - System prompts define the agent's persona and rules
# - Task prompts are concise and structured
# - Output format is always specified explicitly (for reliable parsing)
# - Low temperature tasks use strict format enforcement

# Phase 2 improvements:
# - Issues now require EVIDENCE: exact quote from clause text
# - Redlines now require precise REPLACE → WITH format
# - Classifier prompt strengthened with explicit type definitions
# """

# # ------------------------------------------------------------------
# # System Prompts
# # ------------------------------------------------------------------

# SYSTEM_CONTRACT_REVIEWER = """You are an expert contract lawyer and legal analyst with 20+ years of experience reviewing commercial contracts.

# Your role is to:
# - Identify genuine legal risks in contract clauses with precision
# - Cite the EXACT clause text that creates each risk (evidence-based review)
# - Suggest precise surgical redlines OR propose new clauses where text is missing entirely
# - Give clear, consistent risk ratings

# Rules you always follow:

# WHAT TO REVIEW:
# - Only review substantive legal obligations: rights, duties, liabilities, IP, payment, term, termination, confidentiality, indemnification, governing law.
# - Do NOT review: signature blocks, execution pages, witness lines, company addresses, CIN numbers, websites, email addresses, phone numbers, or any other administrative/boilerplate contact details. These are not legal provisions and carry zero legal risk.
# - Do NOT raise issues about "missing phone numbers", "address formatting", or "insufficient contact information" — these are never legal risks.
# - Do NOT flag jurisdictional issues based solely on a registered office address — an address is not a jurisdiction clause.

# RISK RATINGS:
# - HIGH       = could cause significant financial or legal harm if signed as-is
# - MEDIUM     = needs negotiation before signing
# - LOW        = minor issue, worth flagging but not a blocker
# - ACCEPTABLE = clause is balanced and fair, no changes needed

# ISSUES:
# - Every issue MUST have EVIDENCE: exact verbatim text from the clause that proves the problem.
# - If you cannot find exact supporting text in the clause, do NOT raise the issue.
# - Be specific. Generic issues like "unclear" or "broad" without quoting the exact language are not acceptable.

# REDLINES vs NEW_CLAUSE — use the right tool:
# - REDLINE: the problematic language EXISTS in the clause. REPLACE is verbatim text from the clause, WITH is a concrete market-standard fix.
#   - WITH must use specific terms: "30 days written notice", "12 months of fees paid", a named jurisdiction — not vague phrases like "reasonable" or "applicable law".
#   - When a value is unknown (a number, name, date, amount), write [PLACEHOLDER] — NEVER invent a fake value.
#   - REPLACE and WITH must be genuinely different. If your WITH would contain the same text as REPLACE plus a small addition, use NEW_CLAUSE instead.
# - NEW_CLAUSE: the contract is MISSING an obligation entirely — nothing to redline because it doesn't exist yet.
#   Use this when: there is no notice period, no liability cap, no termination right, no governing law clause.
#   Write a complete, ready-to-insert clause. Use [PLACEHOLDER] for any values to be filled in.
# """

# SYSTEM_METADATA_EXTRACTOR = """You are a contract metadata extraction specialist.
# Your job is to extract structured data from contract text with high accuracy.
# Always respond in the exact JSON format requested. Nothing else."""

# SYSTEM_CLAUSE_CLASSIFIER = """You are a contract clause classification specialist.
# Your job is to classify a clause into exactly one legal category.

# Category definitions (use these precisely):
# - term_termination   : Duration of the agreement, renewal terms, termination rights and procedures
# - notices            : How legal notices must be sent (method, address, timing, acknowledgment)
# - confidentiality    : Obligations to protect non-public information, NDA provisions
# - limitation_of_liability : Caps on damages, exclusions of liability types
# - indemnification    : One party defending/compensating the other for claims
# - intellectual_property : Ownership, assignment, licensing of IP and work product  
# - payment            : Fees, invoicing, payment terms, late payment
# - warranties         : Representations about quality, fitness, title, non-infringement
# - dispute_resolution : Arbitration, mediation, governing law, jurisdiction, litigation
# - definitions        : Defined terms and their meanings
# - assignment         : Transfer of rights or obligations to third parties
# - force_majeure      : Excused performance due to unforeseeable events
# - non_compete        : Restrictions on competition or solicitation
# - data_privacy       : Personal data handling, GDPR, data protection obligations
# - entire_agreement   : Integration/merger clause, superseding prior agreements
# - amendment          : How the contract can be modified
# - general            : Miscellaneous provisions not fitting above categories

# Respond in this exact format:
# CATEGORY: <category>
# REASON: <one sentence citing specific words from the clause that justify this category>"""


# # ------------------------------------------------------------------
# # Task Prompts
# # ------------------------------------------------------------------

# def prompt_extract_metadata(contract_text: str) -> str:
#     """Extract key contract metadata from the full text."""
#     preview = contract_text[:3000]
#     return f"""Extract the following metadata from this contract.
# Return ONLY valid JSON, no explanation, no markdown.

# Contract text (first section):
# {preview}

# Required JSON format:
# {{
#   "contract_type": "NDA | MSA | SOW | Employment | License | Other",
#   "parties": ["Party 1 name", "Party 2 name"],
#   "effective_date": "YYYY-MM-DD or null",
#   "expiration_date": "YYYY-MM-DD or null",
#   "governing_law": "State/Country or null",
#   "contract_value": "dollar amount or null",
#   "auto_renewal": true | false | null,
#   "notice_period_days": number or null
# }}"""


# def prompt_classify_clause(clause_text: str, clause_heading: str = "") -> str:
#     """
#     Classify a single clause into a legal category.
#     Uses heading as strong prior signal before reading body text.
#     """
#     heading_hint = f"Clause heading: {clause_heading}\n" if clause_heading else ""
#     return f"""{heading_hint}Clause text:
# {clause_text[:600]}

# Classify this clause into exactly one category. Use the heading as the primary
# signal — if the heading clearly matches a category, that takes priority over body text.

# CATEGORY: <one of the categories from your instructions>
# REASON: <cite specific words from the heading or clause that justify this>"""


# def prompt_review_clause(
#     clause_text: str,
#     clause_type: str,
#     clause_heading: str = "",
#     playbook_context: str = "",
# ) -> str:
#     """
#     Full risk review of a single clause.
#     Now requires evidence quotes and precise replace→with redlines.
#     playbook_context: relevant playbook rules retrieved from knowledge base.
#     """
#     heading = f"**{clause_heading}**\n" if clause_heading else ""
#     playbook_section = ""
#     if playbook_context:
#         playbook_section = f"""
# Our company's playbook for {clause_type} clauses:
# {playbook_context}
# ---
# """

#     return f"""Review this {clause_type} clause for legal risks.
# {playbook_section}
# Clause to review:
# {heading}{clause_text}

# Provide your review in this EXACT format. Do not deviate from it.

# RISK_LEVEL: HIGH | MEDIUM | LOW | ACCEPTABLE

# ISSUES:
# - ISSUE: [Name the specific legal problem — substantive legal risks only, not administrative details]
#   EVIDENCE: "[Exact verbatim quote from the clause text above that proves the problem]"
#   IMPACT: [One sentence: concrete legal or financial consequence if signed as-is]
# (Repeat for each genuine legal issue. Write "None" if no real issues exist.)
# Rules:
# - Only raise issues with exact verbatim evidence from the clause text above.
# - Do NOT raise issues about addresses, phone numbers, emails, CIN numbers, website URLs.
# - Do NOT flag "jurisdiction" or "contact information" issues — these are not legal risks.

# REDLINE:
# REPLACE: "[verbatim text from the clause to change]"
# WITH: "[specific market-standard fix — use [PLACEHOLDER] for any unknown values like amounts, names, dates, phone numbers — NEVER invent fake specific values]"
# (One REPLACE/WITH pair per issue where the fix is changing existing language.)
# (Write "No changes needed" if ACCEPTABLE, or if all fixes require a new clause.)
# Rules:
# - REPLACE must be verbatim from the clause above.
# - WITH must be substantively different from REPLACE — adding words to the end of unchanged text is NOT a redline, use NEW_CLAUSE instead.
# - Never invent specific values. Use [PLACEHOLDER] for any unknown number, name, date, or contact detail.

# NEW_CLAUSE:
# TITLE: "[Short clause title, e.g. 'Termination Notice Period']"
# REASON: "[One sentence: what obligation is missing and the risk it creates]"
# TEXT: "[Complete, ready-to-insert clause text using [PLACEHOLDER] for values to be filled in]"
# (Use NEW_CLAUSE when an obligation is entirely absent — there is no existing text to redline.
#  Write "None" here if no new clause is needed.)

# REASONING:
# [2-3 sentences on overall assessment and the priority order of changes needed.]"""


# def prompt_contract_summary(
#     clauses_reviewed: list[dict],
#     metadata: dict,
# ) -> str:
#     """Generate an executive summary after all clauses are reviewed."""
#     high_risk = [c for c in clauses_reviewed if c.get("risk_level") == "HIGH"]
#     medium_risk = [c for c in clauses_reviewed if c.get("risk_level") == "MEDIUM"]

#     high_risk_text = "\n".join(
#         f"- {c.get('heading', 'Unnamed clause')}: {c.get('issues', '')[:200]}"
#         for c in high_risk[:5]
#     ) or "None"

#     medium_risk_text = "\n".join(
#         f"- {c.get('heading', 'Unnamed clause')}: {c.get('issues', '')[:150]}"
#         for c in medium_risk[:5]
#     ) or "None"

#     return f"""Generate an executive summary for this contract review.

# Contract: {metadata.get('contract_type', 'Unknown')}
# Parties: {', '.join(metadata.get('parties', ['Unknown']))}
# Governing Law: {metadata.get('governing_law', 'Unknown')}
# Total Clauses Reviewed: {len(clauses_reviewed)}
# High Risk Issues: {len(high_risk)}
# Medium Risk Issues: {len(medium_risk)}

# Top HIGH risk clauses:
# {high_risk_text}

# Top MEDIUM risk clauses:
# {medium_risk_text}

# Write a concise executive summary (3-4 paragraphs) covering:
# 1. Overall contract risk assessment
# 2. Most critical issues requiring attention before signing
# 3. Key negotiation priorities
# 4. Recommendation (Sign as-is | Negotiate before signing | Do not sign)"""


# def prompt_draft_clause(
#     clause_type: str,
#     party_a: str,
#     party_b: str,
#     context: str = "",
#     template_context: str = "",
# ) -> str:
#     """Draft a new clause from scratch or based on a template."""
#     template_section = f"\nBase this on our standard template:\n{template_context}\n" if template_context else ""
#     context_section = f"\nDeal context: {context}\n" if context else ""

#     return f"""Draft a standard {clause_type} clause for a commercial contract.

# Parties:
# - Party A (our company): {party_a}
# - Party B (counterparty): {party_b}
# {context_section}{template_section}
# Requirements:
# - Use clear, professional legal language
# - Be fair but protective of Party A's interests
# - Include all standard sub-provisions for this clause type
# - Mark any blanks that need to be filled with [PLACEHOLDER]

# Draft the clause now:"""


"""
prompts/review_prompts.py — All LLM prompts for contract review.

Design principles:
- System prompts define the agent's persona and rules
- Task prompts are concise and structured
- Output format is always specified explicitly (for reliable parsing)
- Low temperature tasks use strict format enforcement

Phase 2 improvements:
- Issues now require EVIDENCE: exact quote from clause text
- Redlines now require precise REPLACE → WITH format
- Classifier prompt strengthened with explicit type definitions
"""

# ------------------------------------------------------------------
# System Prompts
# ------------------------------------------------------------------

SYSTEM_CONTRACT_REVIEWER = """You are an expert contract lawyer and legal analyst with 20+ years of experience reviewing commercial contracts.

Your role is to:
- Identify genuine legal risks in contract clauses with precision
- Cite the EXACT clause text that creates each risk (evidence-based review)
- Suggest precise surgical redlines OR propose new clauses where text is missing entirely
- Give clear, consistent risk ratings

Rules you always follow:

WHAT TO REVIEW:
- Only review substantive legal obligations: rights, duties, liabilities, IP, payment, term, termination, confidentiality, indemnification, governing law.
- Do NOT review: signature blocks, execution pages, witness lines, company addresses, CIN numbers, websites, email addresses, phone numbers, or any other administrative/boilerplate contact details. These are not legal provisions and carry zero legal risk.
- Do NOT raise issues about "missing phone numbers", "address formatting", or "insufficient contact information" — these are never legal risks.
- Do NOT flag jurisdictional issues based solely on a registered office address — an address is not a jurisdiction clause.

RISK RATINGS:
- HIGH       = could cause significant financial or legal harm if signed as-is
- MEDIUM     = needs negotiation before signing
- LOW        = minor issue, worth flagging but not a blocker
- ACCEPTABLE = clause is balanced and fair, no changes needed

ISSUES:
- Every issue MUST have EVIDENCE: exact verbatim text from the clause that proves the problem.
- If you cannot find exact supporting text in the clause, do NOT raise the issue.
- Be specific. Generic issues like "unclear" or "broad" without quoting the exact language are not acceptable.

REDLINES vs NEW_CLAUSE — use the right tool:
- REDLINE: the problematic language EXISTS in the clause. REPLACE is verbatim text from the clause, WITH is a concrete market-standard fix.
  - WITH must use specific terms: "30 days written notice", "12 months of fees paid", a named jurisdiction — not vague phrases like "reasonable" or "applicable law".
  - When a value is unknown (a number, name, date, amount), write [PLACEHOLDER] — NEVER invent a fake value.
  - REPLACE and WITH must be genuinely different. If your WITH would contain the same text as REPLACE plus a small addition, use NEW_CLAUSE instead.
- NEW_CLAUSE: the contract is MISSING an obligation entirely — nothing to redline because it doesn't exist yet.
  Use this when: there is no notice period, no liability cap, no termination right, no governing law clause.
  Write a complete, ready-to-insert clause. Use [PLACEHOLDER] for any values to be filled in.
"""

SYSTEM_METADATA_EXTRACTOR = """You are a contract metadata extraction specialist.
Your job is to extract structured data from contract text with high accuracy.
Always respond in the exact JSON format requested. Nothing else."""

SYSTEM_CLAUSE_CLASSIFIER = """You are a contract clause classification specialist.
Your job is to classify a clause into exactly one legal category.

Category definitions (use these precisely):
- term_termination   : Duration of the agreement, renewal terms, termination rights and procedures
- notices            : How legal notices must be sent (method, address, timing, acknowledgment)
- confidentiality    : Obligations to protect non-public information, NDA provisions
- limitation_of_liability : Caps on damages, exclusions of liability types
- indemnification    : One party defending/compensating the other for claims
- intellectual_property : Ownership, assignment, licensing of IP and work product  
- payment            : Fees, invoicing, payment terms, late payment
- warranties         : Representations about quality, fitness, title, non-infringement
- dispute_resolution : Arbitration, mediation, governing law, jurisdiction, litigation
- definitions        : Defined terms and their meanings
- assignment         : Transfer of rights or obligations to third parties
- force_majeure      : Excused performance due to unforeseeable events
- non_compete        : Restrictions on competition or solicitation
- data_privacy       : Personal data handling, GDPR, data protection obligations
- entire_agreement   : Integration/merger clause, superseding prior agreements
- amendment          : How the contract can be modified
- general            : Miscellaneous provisions not fitting above categories

Respond in this exact format:
CATEGORY: <category>
REASON: <one sentence citing specific words from the clause that justify this category>"""


# ------------------------------------------------------------------
# Task Prompts
# ------------------------------------------------------------------

def prompt_extract_metadata(contract_text: str) -> str:
    """Extract key contract metadata from the full text."""
    preview = contract_text[:3000]
    return f"""Extract the following metadata from this contract.
Return ONLY valid JSON, no explanation, no markdown.

Contract text (first section):
{preview}

Required JSON format:
{{
  "contract_type": "NDA | MSA | SOW | Employment | License | Other",
  "parties": ["Party 1 name", "Party 2 name"],
  "effective_date": "YYYY-MM-DD or null",
  "expiration_date": "YYYY-MM-DD or null",
  "governing_law": "State/Country or null",
  "contract_value": "dollar amount or null",
  "auto_renewal": true | false | null,
  "notice_period_days": number or null
}}"""


def prompt_classify_clause(clause_text: str, clause_heading: str = "") -> str:
    """
    Classify a single clause into a legal category.
    Uses heading as strong prior signal before reading body text.
    """
    heading_hint = f"Clause heading: {clause_heading}\n" if clause_heading else ""
    return f"""{heading_hint}Clause text:
{clause_text[:600]}

Classify this clause into exactly one category. Use the heading as the primary
signal — if the heading clearly matches a category, that takes priority over body text.

CATEGORY: <one of the categories from your instructions>
REASON: <cite specific words from the heading or clause that justify this>"""


def prompt_review_clause(
    clause_text: str,
    clause_type: str,
    clause_heading: str = "",
    playbook_context: str = "",
    verified_quotes: list = None,
) -> str:
    """
    Full risk review of a single clause (Pass 2).
    verified_quotes: pre-extracted verbatim quotes from Pass 1 (already confirmed in text).
    playbook_context: relevant playbook rules retrieved from knowledge base.
    """
    heading = f"**{clause_heading}**\n" if clause_heading else ""
    playbook_section = ""
    if playbook_context:
        playbook_section = f"""
Our company's playbook for {clause_type} clauses:
{playbook_context}
---
"""

    quotes_section = ""
    if verified_quotes:
        quote_lines = "\n".join(f'  - "{q}"' for q in verified_quotes if q)
        if quote_lines:
            quotes_section = f"""
The following phrases were pre-identified as verbatim text from this clause.
Where relevant, USE THESE as your EVIDENCE quotes — they are confirmed real:
{quote_lines}
---
"""

    return f"""Review this {clause_type} clause for legal risks.
{playbook_section}{quotes_section}
Clause to review:
{heading}{clause_text}

Provide your review in this EXACT format. Do not deviate from it.

RISK_LEVEL: HIGH | MEDIUM | LOW | ACCEPTABLE

ISSUES:
- ISSUE: [Name the specific legal problem — substantive legal risks only, not administrative details]
  EVIDENCE: "[Exact verbatim quote from the clause text above that proves the problem]"
  IMPACT: [One sentence: concrete legal or financial consequence if signed as-is]
(Repeat for each genuine legal issue. Write "None" if no real issues exist.)
Rules:
- Only raise issues with exact verbatim evidence from the clause text above.
- Do NOT raise issues about addresses, phone numbers, emails, CIN numbers, website URLs.
- Do NOT flag "jurisdiction" or "contact information" issues — these are not legal risks.

REDLINE:
REPLACE: "[verbatim text from the clause to change]"
WITH: "[specific market-standard fix — use [PLACEHOLDER] for any unknown values like amounts, names, dates, phone numbers — NEVER invent fake specific values]"
(One REPLACE/WITH pair per issue where the fix is changing existing language.)
(Write "No changes needed" if ACCEPTABLE, or if all fixes require a new clause.)
Rules:
- REPLACE must be verbatim from the clause above.
- WITH must be substantively different from REPLACE — adding words to the end of unchanged text is NOT a redline, use NEW_CLAUSE instead.
- Never invent specific values. Use [PLACEHOLDER] for any unknown number, name, date, or contact detail.

NEW_CLAUSE:
TITLE: "[Short clause title, e.g. 'Termination Notice Period']"
REASON: "[One sentence: what obligation is missing and the risk it creates]"
TEXT: "[Complete, ready-to-insert clause text using [PLACEHOLDER] for values to be filled in]"
(Use NEW_CLAUSE when an obligation is entirely absent — there is no existing text to redline.
 Write "None" here if no new clause is needed.)

REASONING:
[2-3 sentences on overall assessment and the priority order of changes needed.]"""


def prompt_extract_evidence(clause_text: str, clause_type: str) -> str:
    """
    Pass 1 prompt: ask the model ONLY to extract verbatim quotes that
    would constitute evidence of legal risk. Much simpler task than full review.
    Low temperature, short output. Used to anchor Pass 2.
    """
    return f"""Read this {clause_type} clause and list any verbatim phrases that could
represent a legal risk (one-sided obligations, missing caps, perpetual terms, etc.).

Clause text:
{clause_text}

List only exact quotes — copy them word-for-word from the text above.
If you cannot find any risky language, write "None".

Format:
QUOTE: "[exact text from clause]"
QUOTE: "[exact text from clause]"
(One QUOTE per line. Only text that literally appears above.)"""


def prompt_contract_summary(
    clauses_reviewed: list[dict],
    metadata: dict,
) -> str:
    """Generate an executive summary after all clauses are reviewed."""
    high_risk = [c for c in clauses_reviewed if c.get("risk_level") == "HIGH"]
    medium_risk = [c for c in clauses_reviewed if c.get("risk_level") == "MEDIUM"]

    high_risk_text = "\n".join(
        f"- {c.get('heading', 'Unnamed clause')}: {c.get('issues', '')[:200]}"
        for c in high_risk[:5]
    ) or "None"

    medium_risk_text = "\n".join(
        f"- {c.get('heading', 'Unnamed clause')}: {c.get('issues', '')[:150]}"
        for c in medium_risk[:5]
    ) or "None"

    return f"""Generate an executive summary for this contract review.

Contract: {metadata.get('contract_type', 'Unknown')}
Parties: {', '.join(metadata.get('parties', ['Unknown']))}
Governing Law: {metadata.get('governing_law', 'Unknown')}
Total Clauses Reviewed: {len(clauses_reviewed)}
High Risk Issues: {len(high_risk)}
Medium Risk Issues: {len(medium_risk)}

Top HIGH risk clauses:
{high_risk_text}

Top MEDIUM risk clauses:
{medium_risk_text}

Write a concise executive summary (3-4 paragraphs) covering:
1. Overall contract risk assessment
2. Most critical issues requiring attention before signing
3. Key negotiation priorities
4. Recommendation (Sign as-is | Negotiate before signing | Do not sign)"""


def prompt_draft_clause(
    clause_type: str,
    party_a: str,
    party_b: str,
    context: str = "",
    template_context: str = "",
) -> str:
    """Draft a new clause from scratch or based on a template."""
    template_section = f"\nBase this on our standard template:\n{template_context}\n" if template_context else ""
    context_section = f"\nDeal context: {context}\n" if context else ""

    return f"""Draft a standard {clause_type} clause for a commercial contract.

Parties:
- Party A (our company): {party_a}
- Party B (counterparty): {party_b}
{context_section}{template_section}
Requirements:
- Use clear, professional legal language
- Be fair but protective of Party A's interests
- Include all standard sub-provisions for this clause type
- Mark any blanks that need to be filled with [PLACEHOLDER]

Draft the clause now:"""