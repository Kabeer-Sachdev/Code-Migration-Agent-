"""
RAG Engine - keyword-weighted pattern retrieval.
Scores each stored pattern against the query using token overlap,
then returns the top-k most relevant migration patterns.
No external vector DB or ML model required - fully self-contained.
"""
import re
import logging
from typing import List, Dict, Any

from .patterns import MIGRATION_PATTERNS

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> set:
    """Lowercase, strip punctuation, split into tokens."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return set(text.split())


def _score_pattern(pattern: Dict[str, Any], query_tokens: set) -> float:
    """
    Compute relevance score for a pattern given the query tokens.
    Weights:
        keyword match   → 3 pts each
        dotnet text     → 1 pt each token overlap
        java text       → 0.5 pts each token overlap
    """
    score = 0.0

    # Keyword matches (highest weight)
    kw_tokens = {k.lower() for k in pattern.get("keywords", [])}
    score += len(query_tokens & kw_tokens) * 3.0

    # .NET description token overlap
    dotnet_tokens = _tokenize(pattern.get("dotnet", ""))
    score += len(query_tokens & dotnet_tokens) * 1.0

    # Java description token overlap
    java_tokens = _tokenize(pattern.get("java", ""))
    score += len(query_tokens & java_tokens) * 0.5

    # Category match bonus
    category = pattern.get("category", "").lower()
    if category in query_tokens:
        score += 2.0

    return score


class RAGEngine:
    """
    Retrieves the top-k relevant migration patterns for a given code/query string.
    Acts as the RAG (Retrieval-Augmented Generation) layer - the retrieved patterns
    are injected into the LLM prompt to guide the migration.
    """

    def __init__(self) -> None:
        self._patterns = MIGRATION_PATTERNS
        logger.info("RAGEngine initialised with %d patterns", len(self._patterns))

    def retrieve(self, query: str, top_k: int = 6) -> List[Dict[str, Any]]:
        """
        Retrieve the top_k patterns most relevant to `query`.
        Returns a list of pattern dicts, sorted by descending score.
        """
        query_tokens = _tokenize(query)
        if not query_tokens:
            return self._patterns[:top_k]

        scored = [
            (_score_pattern(p, query_tokens), p)
            for p in self._patterns
        ]
        scored.sort(key=lambda x: x[0], reverse=True)

        # Only return patterns with non-zero relevance (at least one match)
        relevant = [p for score, p in scored if score > 0]
        result = relevant[:top_k] if relevant else self._patterns[:top_k]

        logger.info(
            "RAG retrieved %d/%d patterns for query (len=%d tokens)",
            len(result), len(self._patterns), len(query_tokens)
        )
        return result

    def retrieve_for_code(self, code_content: str, top_k: int = 8) -> List[Dict[str, Any]]:
        """
        Convenience method: retrieves patterns relevant to actual .NET source code.
        Extracts the most informative query terms from the code automatically.
        """
        # Extract .NET-specific keywords present in the code
        interesting_patterns = [
            r"\[ApiController\]", r"\[HttpGet\]", r"\[HttpPost\]",
            r"\[HttpPut\]", r"\[HttpDelete\]", r"ControllerBase",
            r"DbContext", r"DbSet", r"IRepository", r"async\s+Task",
            r"await\s+", r"ILogger", r"IOptions", r"IMemoryCache",
            r"IHostedService", r"BackgroundService", r"AutoMapper",
            r"MediatR", r"FluentValidation", r"\.Where\(", r"\.Select\(",
            r"\.Include\(", r"\.FirstOrDefault\(", r"\[Authorize\]",
            r"\[Required\]", r"\[Key\]", r"appsettings",
        ]

        found_terms = []
        for pat in interesting_patterns:
            if re.search(pat, code_content, re.IGNORECASE):
                # Extract the clean keyword
                clean = re.sub(r"[\[\]\\()\s\.\*\+]", "", pat).lower()
                found_terms.append(clean)

        query = " ".join(found_terms) + " " + code_content[:500]
        return self.retrieve(query, top_k=top_k)

    def format_for_prompt(self, patterns: List[Dict[str, Any]]) -> str:
        """
        Format retrieved patterns as a structured block for injection into the LLM prompt.
        """
        if not patterns:
            return "No specific patterns retrieved."

        lines = []
        for i, p in enumerate(patterns, start=1):
            lines.append(f"### Pattern {i}: {p.get('category', '').upper()} - {p.get('dotnet', '')[:80]}")
            lines.append(f"  .NET : {p.get('dotnet', '')}")
            lines.append(f"  Java : {p.get('java', '')}")
            if p.get("example_dotnet"):
                lines.append(f"  Example (.NET):\n    {p['example_dotnet']}")
            if p.get("example_java"):
                lines.append(f"  Example (Java):\n    {p['example_java']}")
            lines.append("")

        return "\n".join(lines)


# Singleton
rag_engine = RAGEngine()
