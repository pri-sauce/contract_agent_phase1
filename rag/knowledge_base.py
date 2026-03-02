"""
rag/knowledge_base.py — ChromaDB Vector Store Manager

What this file does:
- Creates and manages 5 ChromaDB collections (namespaces)
- Loads your playbook.yaml into the vector store
- Provides methods to add contracts, clauses, and legal notes
- Uses Ollama's nomic-embed-text to convert text → vectors

Think of this as the "librarian" — it organizes and stores everything.
The retriever.py is the "researcher" — it searches what the librarian stored.

How ChromaDB works:
  Text → Embedding model → Vector (list of 768 numbers) → Stored in ChromaDB
  At query time: Query text → Vector → Find closest stored vectors → Return matches
"""

import yaml
import json
from pathlib import Path
from typing import Optional
from loguru import logger

import chromadb
from chromadb.config import Settings

from core.config import config


# ------------------------------------------------------------------
# Collection Names — these are like database tables
# ------------------------------------------------------------------

COLLECTION_PLAYBOOK       = "playbook"          # Your company's clause positions
COLLECTION_CLAUSE_LIBRARY = "clause_library"    # Approved clause templates
COLLECTION_CONTRACTS      = "contracts"         # Past reviewed contracts
COLLECTION_LEGAL_KB       = "legal_kb"          # Legal notes, case law summaries
COLLECTION_COUNTERPARTIES = "counterparties"    # Per-counterparty negotiation history

ALL_COLLECTIONS = [
    COLLECTION_PLAYBOOK,
    COLLECTION_CLAUSE_LIBRARY,
    COLLECTION_CONTRACTS,
    COLLECTION_LEGAL_KB,
    COLLECTION_COUNTERPARTIES,
]


class KnowledgeBase:
    """
    Manages the ChromaDB vector store.
    Handles creation, population, and maintenance of all collections.
    """

    def __init__(self):
        # ChromaDB persists to disk — survives restarts
        db_path = str(config.KNOWLEDGE_BASE_DIR / "chromadb")
        
        self.client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False),  # no phone home
        )

        # Use Ollama for embeddings via a custom embedding function
        self.embed_fn = OllamaEmbeddingFunction()

        # Initialize all collections
        self.collections = {}
        for name in ALL_COLLECTIONS:
            self.collections[name] = self.client.get_or_create_collection(
                name=name,
                embedding_function=self.embed_fn,
                metadata={"hnsw:space": "cosine"},  # cosine similarity for text
            )

        logger.info(f"Knowledge base initialized at {db_path}")

    # ------------------------------------------------------------------
    # Playbook Loading — converts playbook.yaml → ChromaDB documents
    # ------------------------------------------------------------------

    def load_playbook(self, playbook_path: Optional[Path] = None) -> int:
        """
        Reads playbook.yaml and stores each clause position as a
        searchable document in ChromaDB.

        Returns: number of entries loaded
        """
        path = playbook_path or config.PLAYBOOK_PATH

        if not path.exists():
            logger.warning(f"Playbook not found at {path}")
            return 0

        with open(path, "r") as f:
            playbook = yaml.safe_load(f)

        company = playbook.get("company_name", "Your Company")
        clauses = playbook.get("clauses", {})

        documents = []
        metadatas = []
        ids = []

        for clause_type, data in clauses.items():
            # Build a rich text document from the YAML structure
            # This is what gets embedded and searched
            doc_text = self._playbook_entry_to_text(clause_type, data, company)

            documents.append(doc_text)
            metadatas.append({
                "clause_type": clause_type,
                "source": "playbook",
                "company": company,
                "position": data.get("position", ""),
            })
            ids.append(f"playbook_{clause_type}")

        if documents:
            # upsert = insert or update if ID already exists
            self.collections[COLLECTION_PLAYBOOK].upsert(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )
            logger.success(f"Loaded {len(documents)} playbook entries into knowledge base")

        return len(documents)

    def _playbook_entry_to_text(self, clause_type: str, data: dict, company: str) -> str:
        """
        Converts a YAML playbook entry into a rich text document.
        This text is what gets embedded — more detail = better retrieval.
        """
        lines = [
            f"CLAUSE TYPE: {clause_type.replace('_', ' ').upper()}",
            f"COMPANY POSITION: {data.get('position', '')}",
        ]

        must_have = data.get("must_have", [])
        if must_have:
            lines.append("MUST HAVE:")
            for item in must_have:
                lines.append(f"  - {item}")

        reject_if = data.get("reject_if", [])
        if reject_if:
            lines.append("REJECT IF CONTRACT CONTAINS:")
            for item in reject_if:
                lines.append(f"  - {item}")

        fallback = data.get("acceptable_fallback", "")
        if fallback:
            lines.append(f"ACCEPTABLE FALLBACK: {fallback}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Clause Library — approved template clauses
    # ------------------------------------------------------------------

    def add_clause_template(
        self,
        clause_type: str,
        clause_text: str,
        label: str = "standard",       # "most_favorable" | "standard" | "fallback"
        notes: str = "",
    ):
        """
        Add an approved clause template to the library.
        These are retrieved during the drafting pipeline (Phase 3).
        """
        doc_id = f"template_{clause_type}_{label}_{hash(clause_text) % 10000}"

        self.collections[COLLECTION_CLAUSE_LIBRARY].upsert(
            documents=[clause_text],
            metadatas=[{
                "clause_type": clause_type,
                "label": label,
                "notes": notes,
                "source": "clause_library",
            }],
            ids=[doc_id],
        )
        logger.info(f"Added {label} template for {clause_type}")

    # ------------------------------------------------------------------
    # Contract Repository — stores past reviewed contracts
    # ------------------------------------------------------------------

    def add_contract_clauses(self, contract_id: str, clauses: list[dict]):
        """
        Store all clauses from a reviewed contract.
        Builds institutional memory over time.

        Each clause dict should have: text, clause_type, risk_level, heading
        """
        documents = []
        metadatas = []
        ids = []

        for i, clause in enumerate(clauses):
            documents.append(clause.get("text", ""))
            metadatas.append({
                "contract_id": contract_id,
                "clause_type": clause.get("clause_type", "general"),
                "risk_level": clause.get("risk_level", ""),
                "heading": clause.get("heading", ""),
                "source": "contract_repository",
            })
            ids.append(f"{contract_id}_clause_{i:03d}")

        if documents:
            self.collections[COLLECTION_CONTRACTS].upsert(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )
            logger.info(f"Stored {len(documents)} clauses from contract {contract_id}")

    # ------------------------------------------------------------------
    # Legal Knowledge Base — legal notes, jurisdiction rules
    # ------------------------------------------------------------------

    def add_legal_note(
        self,
        topic: str,
        content: str,
        jurisdiction: str = "general",
        source: str = "",
    ):
        """
        Add a legal note or case law summary to the knowledge base.
        Example: "California Civil Code 1668 voids liability waivers for fraud"
        """
        doc_id = f"legal_{jurisdiction}_{hash(topic) % 10000}"

        self.collections[COLLECTION_LEGAL_KB].upsert(
            documents=[f"{topic}\n\n{content}"],
            metadatas=[{
                "topic": topic,
                "jurisdiction": jurisdiction,
                "source": source,
                "collection": "legal_kb",
            }],
            ids=[doc_id],
        )

    # ------------------------------------------------------------------
    # Stats & Maintenance
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Returns how many documents are in each collection."""
        return {
            name: self.collections[name].count()
            for name in ALL_COLLECTIONS
        }

    def is_populated(self) -> bool:
        """Check if the knowledge base has any data at all."""
        return self.collections[COLLECTION_PLAYBOOK].count() > 0

    def reset_collection(self, collection_name: str):
        """Wipe and recreate a collection. Use carefully."""
        self.client.delete_collection(collection_name)
        self.collections[collection_name] = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embed_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.warning(f"Reset collection: {collection_name}")


# ------------------------------------------------------------------
# Custom Ollama Embedding Function for ChromaDB
# ------------------------------------------------------------------

class OllamaEmbeddingFunction:
    """
    Bridges ChromaDB and Ollama for local embeddings.

    ChromaDB expects an embedding function with a specific interface.
    This class wraps Ollama's embedding endpoint to match that interface.

    Model: nomic-embed-text — 768-dimensional embeddings, fast on Apple Silicon

    Note: ChromaDB >= 0.6 requires a name() method on custom embedding functions.
    """

    def __init__(self):
        import ollama
        self.client = ollama.Client(host=config.OLLAMA_BASE_URL)
        self.model = config.EMBEDDING_MODEL

    def name(self) -> str:
        """
        Required by ChromaDB >= 0.6 to identify the embedding function.
        Used to validate consistency when reopening existing collections.
        Must return "default" so ChromaDB skips conflict validation on
        collections that were created without a named embedding function.
        """
        return "default"

    def _embed_one(self, text: str) -> list[float]:
        """
        Embed a single string via Ollama. Returns a 768-dim float vector.

        Handles both old Ollama API (client.embeddings(prompt=str))
        and new API (client.embed(input=str)) with automatic fallback.
        """
        # Ensure text is always a plain string — defensive against ChromaDB
        # passing a list when we expect a scalar
        if isinstance(text, list):
            text = text[0] if text else ""
        text = str(text).strip()

        try:
            # Try newer Ollama API first (ollama-python >= 0.3)
            try:
                response = self.client.embed(model=self.model, input=text)
                # embed() returns EmbedResponse with .embeddings (list of vectors)
                return response.embeddings[0]
            except AttributeError:
                pass

            # Fall back to older API (ollama-python < 0.3)
            response = self.client.embeddings(model=self.model, prompt=text)
            return response.embedding

        except Exception as e:
            logger.error(f"Embedding failed for text: {e}")
            return [0.0] * 768  # zero vector — better than crashing

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of strings. Returns list of vectors."""
        return [self._embed_one(t) for t in texts]

    def __call__(self, input: list[str]) -> list[list[float]]:
        """ChromaDB legacy interface — called with a list of strings."""
        if isinstance(input, str):
            input = [input]
        return self._embed(input)

    def embed_documents(self, input: list[str]) -> list[list[float]]:
        """
        ChromaDB >= 0.6 indexing interface.
        Called when storing documents into a collection.
        """
        if isinstance(input, str):
            input = [input]
        return self._embed(input)

    def embed_query(self, input) -> list[float]:
        """
        ChromaDB >= 0.6 search interface.
        Called at query time. Input may be a string OR a list (ChromaDB bug) —
        we handle both defensively.
        """
        if isinstance(input, list):
            input = input[0] if input else ""
        return self._embed_one(str(input))


# Singleton
knowledge_base = KnowledgeBase()
