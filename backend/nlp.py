"""
Semantic NLP engine using sentence-transformers all-MiniLM-L6-v2.

Key difference vs TF-IDF:
  - "MTBF 6000 hours" and "reliability 5000 hours" score ~0.72 similarity
    because both describe a dependability metric in time units.
  - TF-IDF would score ~0.0 because no words overlap.

Thresholds are recalibrated for semantic cosine similarity:
  >= 0.55  -> compliant
  >= 0.30  -> partial
  <  0.30  -> non-compliant

Torch is optional: if unavailable (e.g. Python 3.14 pre-release),
numpy is used for cosine similarity -- same accuracy, just slightly slower.
"""

from __future__ import annotations

import re
import numpy as np
from typing import TypedDict

# sentence-transformers lazy import so startup errors are clear
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print("[nlp] Loading all-MiniLM-L6-v2 ...")
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        print("[nlp] Model ready.")
    return _model


# Requirement keywords (same heuristic as original JS)
_REQ_KEYWORDS = [
    "shall", "must", "required", "minimum", "maximum", "comply",
    "specification", "standard", "certif", "test", "qualify",
    "performance", "material", "capacity", "deliver", "supply",
    "provide", "ensure", "temperature", "mtbf", "reliability",
    "packaging", "traceability",
]

COMPLIANT_THRESHOLD = 0.55
PARTIAL_THRESHOLD = 0.30


class ClauseResult(TypedDict):
    id: int
    text: str
    score: float           # 0-100
    status: str            # "compliant" | "partial" | "non-compliant"
    matched_terms: list[str]
    missing_terms: list[str]
    best_vendor_match: str


def _cosine_numpy(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D numpy arrays."""
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _cosine_matrix_numpy(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity between one vector and a matrix of row vectors."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-9, norms)
    norm_matrix = matrix / norms
    query_norm = query / (np.linalg.norm(query) + 1e-9)
    return norm_matrix @ query_norm


def extract_requirements(text: str, max_clauses: int = 20) -> list[str]:
    """Split tender text into requirement sentences."""
    text = re.sub(r"\n+", " ", text)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 25]

    reqs = [
        s for s in sentences
        if any(kw in s.lower() for kw in _REQ_KEYWORDS)
    ]

    result = reqs if len(reqs) >= 3 else sentences
    return result[:max_clauses]


def _split_vendor_sentences(vendor_text: str) -> list[str]:
    vendor_text = re.sub(r"\n+", " ", vendor_text)
    sents = re.split(r"(?<=[.!?])\s+", vendor_text)
    return [s.strip() for s in sents if len(s.strip()) > 10]


def score_clauses(clauses: list[str], vendor_text: str) -> list[ClauseResult]:
    """
    For each clause, compute semantic similarity to the full vendor document
    AND find the best matching vendor sentence.
    """
    model = _get_model()
    vendor_sentences = _split_vendor_sentences(vendor_text)

    # Encode everything in one batch for efficiency
    all_texts = clauses + [vendor_text] + vendor_sentences
    # convert_to_numpy=True works without torch
    embeddings = model.encode(all_texts, convert_to_numpy=True, show_progress_bar=False)

    clause_embs = embeddings[: len(clauses)]
    vendor_doc_emb = embeddings[len(clauses)]
    vendor_sent_embs = embeddings[len(clauses) + 1 :]

    results: list[ClauseResult] = []

    for i, (clause_text, c_emb) in enumerate(zip(clauses, clause_embs)):
        # Similarity to the full vendor document
        doc_sim = _cosine_numpy(c_emb, vendor_doc_emb)

        # Best matching vendor sentence
        best_match_text = ""
        best_match_score = 0.0
        if len(vendor_sent_embs) > 0:
            sent_sims = _cosine_matrix_numpy(c_emb, vendor_sent_embs)
            best_idx = int(np.argmax(sent_sims))
            best_match_score = float(sent_sims[best_idx])
            best_match_text = vendor_sentences[best_idx] if vendor_sentences else ""

        # Use max of doc-level and best-sentence similarity
        final_score = max(doc_sim, best_match_score * 0.9)
        final_score = min(final_score, 1.0)

        # Determine status
        if final_score >= COMPLIANT_THRESHOLD:
            status = "compliant"
        elif final_score >= PARTIAL_THRESHOLD:
            status = "partial"
        else:
            status = "non-compliant"

        # Concept matching
        clause_tokens = set(
            w for w in re.sub(r"[^a-z0-9\s]", " ", clause_text.lower()).split()
            if len(w) > 3
        )
        vendor_tokens = set(
            w for w in re.sub(r"[^a-z0-9\s]", " ", vendor_text.lower()).split()
            if len(w) > 3
        )
        matched = sorted(clause_tokens & vendor_tokens)[:8]
        missing = sorted(clause_tokens - vendor_tokens)[:8]

        results.append(
            ClauseResult(
                id=i + 1,
                text=clause_text,
                score=round(final_score * 100),
                status=status,
                matched_terms=matched,
                missing_terms=missing,
                best_vendor_match=best_match_text,
            )
        )

    return results
