"""
llm.py — Ollama connection layer
Wraps all LLM calls. Every part of the agent goes through here.
Handles: streaming, retries, model switching, error handling.
"""

import ollama
from typing import Generator, Optional
from loguru import logger
from core.config import config


class LLMClient:
    """
    Central LLM client for the contract agent.
    Provides clean interfaces for generation, streaming, and embeddings.
    """

    def __init__(self):
        self.client = ollama.Client(host=config.OLLAMA_BASE_URL)
        self.primary_model = config.PRIMARY_MODEL
        self.fast_model = config.FAST_MODEL
        self.embedding_model = config.EMBEDDING_MODEL

    # ------------------------------------------------------------------
    # Health Check
    # ------------------------------------------------------------------

    def check_connection(self) -> bool:
        """Verify Ollama is running and required models are available."""
        try:
            models = self.client.list()
            available = [m.model for m in models.models]
            logger.info(f"Ollama connected. Available models: {available}")

            required = {self.primary_model, self.fast_model}
            missing = required - set(available)

            if missing:
                logger.warning(f"Missing models: {missing}")
                logger.warning(f"Run: ollama pull {' && ollama pull '.join(missing)}")
                return False

            logger.success("All required models available.")
            return True

        except Exception as e:
            logger.error(f"Cannot connect to Ollama at {config.OLLAMA_BASE_URL}: {e}")
            logger.error("Make sure Ollama is running: `ollama serve`")
            return False

    # ------------------------------------------------------------------
    # Core Generation
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,   # Low temp = more deterministic (good for legal)
        max_tokens: int = 2048,
    ) -> str:
        """
        Single-turn generation. Returns complete response as string.
        Use this for review, classification, extraction tasks.
        """
        use_model = model or self.primary_model

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            logger.debug(f"Generating with {use_model} | temp={temperature}")
            response = self.client.chat(
                model=use_model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            )
            return response.message.content

        except Exception as e:
            logger.error(f"Generation failed with {use_model}: {e}")
            raise

    def stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Generator[str, None, None]:
        """
        Streaming generation. Yields text chunks as they arrive.
        Use this for UI display so users see output in real-time.
        """
        use_model = model or self.primary_model

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            for chunk in self.client.chat(
                model=use_model,
                messages=messages,
                stream=True,
                options={"temperature": temperature},
            ):
                if chunk.message.content:
                    yield chunk.message.content

        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            raise

    def fast_generate(self, prompt: str, system: Optional[str] = None) -> str:
        """
        Quick generation using the fast model.
        Use for classification, metadata extraction, simple labeling tasks.
        """
        return self.generate(
            prompt=prompt,
            system=system,
            model=self.fast_model,
            temperature=0.0,    # Zero temp for classification = consistent labels
            max_tokens=512,     # Fast model tasks need short outputs
        )

    # ------------------------------------------------------------------
    # Embeddings (Ready for Phase 2 RAG)
    # ------------------------------------------------------------------

    def embed(self, text: str) -> list[float]:
        """
        Generate embedding vector for a piece of text.
        Used by the RAG pipeline (Phase 2).
        """
        try:
            response = self.client.embeddings(
                model=self.embedding_model,
                prompt=text,
            )
            return response.embedding
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            raise

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts. Used when populating the knowledge base."""
        return [self.embed(t) for t in texts]


# Singleton — import this everywhere
llm = LLMClient()
