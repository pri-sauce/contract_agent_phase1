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
- Identify legal risks in contract clauses with precision
- Cite the EXACT clause text that creates each risk (evidence-based review)
- Suggest precise surgical redlines — not narrative advice
- Give clear, consistent risk ratings

Rules you always follow:
- Be specific, not generic. Name the exact problem in the clause.
- Risk ratings:
    HIGH       = could cause significant financial/legal harm if signed as-is
    MEDIUM     = needs negotiation before signing
    LOW        = minor issue, worth flagging but not a blocker
    ACCEPTABLE = clause is balanced and fair, no changes needed
- Every EVIDENCE quote MUST be text that literally appears in the clause above.
  Never write "None" as evidence. If you cannot find exact supporting text, do not raise the issue.
- Redlines must be surgical: exact text to remove → exact replacement text.
  Never suggest vague replacements like "reasonable amount" or "applicable law" alone.
  Use market-standard language: fee-based caps, specific notice periods, named jurisdictions.
- Do not manufacture risks. Boilerplate integration clauses, standard purpose statements,
  and typical recitals are ACCEPTABLE — do not flag them as HIGH or MEDIUM.
- Signature blocks, execution pages, and witness sections are not clauses — do not review them.
- Format your output exactly as requested — it will be parsed programmatically.
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
) -> str:
    """
    Full risk review of a single clause.
    Now requires evidence quotes and precise replace→with redlines.
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

    return f"""Review this {clause_type} clause for legal risks.
{playbook_section}
Clause to review:
{heading}{clause_text}

Provide your review in this EXACT format. Do not deviate from it.

RISK_LEVEL: HIGH | MEDIUM | LOW | ACCEPTABLE

ISSUES:
- ISSUE: [Name the specific legal problem]
  EVIDENCE: "[Exact verbatim quote from the clause text above — must appear word-for-word in the clause]"
  IMPACT: [One sentence on the concrete consequence if signed as-is]
(Repeat for each issue. Write "None" under ISSUES if no real issues exist.)
Important: Only raise an issue if you can quote exact supporting text. No "None" evidence.

REDLINE:
REPLACE: "[exact current clause text to remove — must be verbatim from clause]"
WITH: "[specific market-standard replacement — use concrete terms like '12 months of fees', '30 days written notice', not vague phrases like 'reasonable amount' or 'applicable law']"
(One REPLACE/WITH pair per issue. Write "No changes needed" if ACCEPTABLE.)
Critical redline rules:
- REPLACE and WITH must be DIFFERENT — never copy the same text into both fields
- If you cannot think of a concrete improvement, write "No changes needed" instead
- REPLACE must be text that literally appears in the clause above
- WITH must be a specific, actionable fix — not a restatement of the same text

REASONING:
[2-3 sentences on your overall assessment and priority of changes.]"""


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