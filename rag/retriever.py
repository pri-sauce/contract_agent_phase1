"""
rag/retriever.py — Knowledge Base Retriever

What this file does:
- Takes a clause and searches ChromaDB for relevant context
- Searches multiple collections simultaneously (playbook + legal KB)
- Formats retrieved results into clean text for LLM prompts
- Handles cases where nothing relevant is found gracefully

Think of this as the "researcher" who goes to the library (knowledge_base.py)
and pulls the right documents before the LLM "lawyer" reviews a clause.

The flow per clause:
  clause_type="limitation_of_liability"
       ↓
  retriever.get_context_for_clause(clause)
       ↓
  searches: playbook collection + legal_kb collection
       ↓
  returns formatted string like:
    "COMPANY POSITION: Cap must be mutual at 12 months fees...
     REJECT IF: Uncapped liability, cap below 3 months...
     LEGAL NOTE: CA Civil Code 1668 voids waivers for fraud"
       ↓
  injected into LLM prompt as playbook_context
"""

from loguru import logger
from typing import Optional

from rag.knowledge_base import knowledge_base, COLLECTION_PLAYBOOK, COLLECTION_LEGAL_KB, COLLECTION_CONTRACTS


class Retriever:
    """
    Retrieves relevant context from the knowledge base for a given clause.
    """

    def __init__(self):
        self.kb = knowledge_base

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------

    def get_context_for_clause(
        self,
        clause_type: str,
        clause_text: str,
        governing_law: Optional[str] = None,
        n_results: int = 3,
    ) -> str:
        """
        Main method called by the review pipeline for each clause.

        Returns a formatted string ready to inject into the LLM prompt.
        Returns empty string if knowledge base has no relevant content.
        """
        if not self.kb.is_populated():
            logger.debug("Knowledge base empty — skipping RAG retrieval")
            return ""

        sections = []

        # 1. Get playbook position for this clause type
        playbook_context = self._get_playbook_context(clause_type, clause_text)
        if playbook_context:
            sections.append(playbook_context)

        # 2. Get jurisdiction-specific legal notes if we know governing law
        if governing_law:
            legal_context = self._get_legal_context(clause_type, governing_law)
            if legal_context:
                sections.append(legal_context)

        # 3. Get similar clauses from past contracts (institutional memory)
        past_context = self._get_past_clause_context(clause_type, clause_text)
        if past_context:
            sections.append(past_context)

        if not sections:
            return ""

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Playbook Retrieval
    # ------------------------------------------------------------------

    def _query_collection(self, collection_name: str, query_text: str,
                          n_results: int = 2, where: dict = None) -> dict:
        """
        Central query method. Pre-computes embedding ourselves and passes it
        via query_embeddings= to bypass ChromaDB's embedding function dispatch,
        which has inconsistent interfaces across versions.

        This avoids ALL embed_query / __call__ / interface mismatch issues.
        """
        # Get the embedding directly from Ollama
        vector = self.kb.embed_fn._embed_one(query_text)

        # query_embeddings expects list[list[float]]
        kwargs = {
            "query_embeddings": [vector],
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where

        return self.kb.collections[collection_name].query(**kwargs)

    def _get_playbook_context(self, clause_type: str, clause_text: str) -> str:
        """
        Retrieves company playbook position for this clause type.

        Strategy: search by clause_type metadata first (exact match),
        fall back to semantic search without filter if no match found.
        """
        try:
            # First try exact clause_type match — most reliable
            results = self._query_collection(
                COLLECTION_PLAYBOOK, clause_text, n_results=2,
                where={"clause_type": clause_type},
            )

            if results["documents"] and results["documents"][0]:
                return self._format_playbook_result(results["documents"][0])

            # Fallback: semantic search without type filter
            results = self._query_collection(
                COLLECTION_PLAYBOOK, clause_text, n_results=2,
            )

            if results["documents"] and results["documents"][0]:
                distances = results.get("distances", [[]])[0]
                if distances and distances[0] < 0.5:
                    return self._format_playbook_result(results["documents"][0])

        except Exception as e:
            logger.warning(f"Playbook retrieval failed: {e}")

        return ""

    def _format_playbook_result(self, docs: list[str]) -> str:
        """Wraps playbook docs in a clear header for the LLM."""
        if not docs:
            return ""

        content = "\n---\n".join(docs)
        return f"=== YOUR COMPANY'S PLAYBOOK POSITION ===\n{content}\n=== END PLAYBOOK ==="

    # ------------------------------------------------------------------
    # Legal Knowledge Base Retrieval
    # ------------------------------------------------------------------

    def _get_legal_context(self, clause_type: str, governing_law: str) -> str:
        """
        Retrieves jurisdiction-specific legal notes.
        Example: if governing_law="California", retrieves CA-specific rules.
        """
        try:
            query = f"{clause_type} {governing_law} law requirements"


            # Also check "general" jurisdiction notes

            docs = []
            if results["documents"] and results["documents"][0]:
                docs.extend(results["documents"][0])
            if general_results["documents"] and general_results["documents"][0]:
                docs.extend(general_results["documents"][0])

            if docs:
                content = "\n".join(docs[:2])
                return f"=== LEGAL NOTES ({governing_law}) ===\n{content}\n=== END LEGAL NOTES ==="

        except Exception as e:
            logger.warning(f"Legal KB retrieval failed: {e}")

        return ""

    # ------------------------------------------------------------------
    # Past Contract Retrieval (Institutional Memory)
    # ------------------------------------------------------------------

    def _get_past_clause_context(self, clause_type: str, clause_text: str) -> str:
        """
        Finds similar clauses from past reviewed contracts.
        Over time this builds institutional memory — the agent learns
        from every contract that passes through the system.
        """
        try:
            # Only search if we have enough history
            if self.kb.collections[COLLECTION_CONTRACTS].count() < 5:
                return ""  # not enough history yet

            results = self._query_collection(
                COLLECTION_CONTRACTS, clause_text, n_results=2,
                where={"clause_type": clause_type},
            )

            if not results["documents"] or not results["documents"][0]:
                return ""

            docs = results["documents"][0]
            metas = results["metadatas"][0] if results["metadatas"] else []
            distances = results["distances"][0] if results["distances"] else []

            # Only use close matches
            good_matches = [
                (doc, meta) for doc, meta, dist
                in zip(docs, metas, distances)
                if dist < 0.3  # very close match
            ]

            if not good_matches:
                return ""

            lines = ["=== SIMILAR CLAUSES FROM PAST CONTRACTS ==="]
            for doc, meta in good_matches[:2]:
                risk = meta.get("risk_level", "unknown")
                contract = meta.get("contract_id", "unknown")
                lines.append(f"[{contract} | Risk: {risk}]\n{doc[:300]}")

            lines.append("=== END PAST CONTRACTS ===")
            return "\n".join(lines)

        except Exception as e:
            logger.warning(f"Past contract retrieval failed: {e}")

        return ""

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_playbook_for_type(self, clause_type: str) -> str:
        """
        Direct playbook lookup by clause type.
        Used by the drafting pipeline (Phase 3) to get approved language.
        """
        try:
            results = self.kb.collections[COLLECTION_PLAYBOOK].get(
                ids=[f"playbook_{clause_type}"],
            )
            if results["documents"]:
                return results["documents"][0]
        except Exception:
            pass
        return ""


# Singleton
retriever = Retriever()
