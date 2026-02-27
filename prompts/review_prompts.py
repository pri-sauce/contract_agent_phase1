"""
prompts/review_prompts.py — All LLM prompts for contract review.

Design principles:
- System prompts define the agent's persona and rules
- Task prompts are concise and structured
- Output format is always specified explicitly (for reliable parsing)
- Low temperature tasks use strict format enforcement
"""

# ------------------------------------------------------------------
# System Prompts
# ------------------------------------------------------------------

SYSTEM_CONTRACT_REVIEWER = """You are an expert contract lawyer and legal analyst with 20+ years of experience reviewing commercial contracts. 

Your role is to:
- Identify legal risks in contract clauses with precision
- Flag deviations from standard market practice
- Suggest specific redlines and improvements
- Give clear risk ratings with solid reasoning

Rules you always follow:
- Be specific, not generic. Name the exact problem in the clause.
- Risk ratings: HIGH (could cause significant financial/legal harm), MEDIUM (needs negotiation), LOW (minor issue or standard concern)
- If a clause is balanced and fair, say so — don't manufacture risks
- Format your output exactly as requested — it will be parsed programmatically
"""

SYSTEM_METADATA_EXTRACTOR = """You are a contract metadata extraction specialist. 
Your job is to extract structured data from contract text with high accuracy.
Always respond in the exact JSON format requested. Nothing else."""

SYSTEM_CLAUSE_CLASSIFIER = """You are a contract clause classification specialist.
Classify contract clauses into their correct legal category.
Respond only with the classification label and a one-line reason."""


# ------------------------------------------------------------------
# Task Prompts
# ------------------------------------------------------------------

def prompt_extract_metadata(contract_text: str) -> str:
    """Extract key contract metadata from the full text."""
    # Use first 3000 chars — metadata is usually in the header
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
    """Classify a single clause into a legal category."""
    heading_hint = f"Clause heading: {clause_heading}\n" if clause_heading else ""
    return f"""{heading_hint}Clause text:
{clause_text[:500]}

Classify this clause. Choose the single best category from:
definitions, term_termination, payment, confidentiality, intellectual_property,
limitation_of_liability, indemnification, warranties, dispute_resolution,
force_majeure, assignment, non_compete, data_privacy, notices, entire_agreement,
amendment, representations, covenants, general

Respond in this exact format:
CATEGORY: <category>
REASON: <one sentence why>"""


def prompt_review_clause(
    clause_text: str,
    clause_type: str,
    clause_heading: str = "",
    playbook_context: str = "",
) -> str:
    """
    Full risk review of a single clause.
    playbook_context: relevant playbook rules retrieved from knowledge base (Phase 2).
    """
    heading = f"**{clause_heading}**\n" if clause_heading else ""
    playbook_section = ""
    if playbook_context:
        playbook_section = f"""
Our company's playbook for {clause_type} clauses:
{playbook_context}
---"""

    return f"""Review this {clause_type} clause for legal risks and issues.
{playbook_section}

Clause to review:
{heading}{clause_text}

Provide your review in this EXACT format (do not deviate):

RISK_LEVEL: HIGH | MEDIUM | LOW | ACCEPTABLE
ISSUES:
- [Issue 1]: [Specific problem and why it matters]
- [Issue 2]: [Specific problem and why it matters]
(list all issues, or write "None" if acceptable)

REDLINE_SUGGESTION:
[Specific suggested replacement language, or "No change needed"]

REASONING:
[2-3 sentence explanation of your overall assessment]"""


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
