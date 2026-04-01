from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from dataclasses import dataclass, field

from mneia.core.llm import LLMClient
from mneia.memory.store import MemoryStore, StoredDocument

logger = logging.getLogger(__name__)

MIN_CLUSTER_SIZE = 3
MAX_RAPTOR_NODES = 20
MAX_DOCS_FOR_RAPTOR = 500


def _sklearn_available() -> bool:
    try:
        import sklearn  # noqa: F401
        return True
    except ImportError:
        return False


@dataclass
class RaptorNode:
    """Synthetic summary document representing a cluster of related docs."""
    cluster_id: str
    summary: str
    source_doc_ids: list[int]
    level: int
    topics: list[str] = field(default_factory=list)


async def build_raptor_tree(
    store: MemoryStore,
    llm: LLMClient,
    source: str | None = None,
) -> list[RaptorNode]:
    """Build a RAPTOR-style hierarchy over stored documents.

    RAPTOR (Recursive Abstractive Processing For Tree-Organized Retrieval):
    1. Vectorise docs with TF-IDF (no external embedding service needed)
    2. Cluster by cosine similarity using agglomerative clustering
    3. Generate an LLM summary for each cluster
    4. Return RaptorNode objects that can be injected into RAG context

    Requires scikit-learn. Returns [] if unavailable or too few documents.
    """
    if not _sklearn_available():
        logger.debug("scikit-learn not available — RAPTOR skipped")
        return []

    docs = await store.get_recent(limit=MAX_DOCS_FOR_RAPTOR, source=source)
    if len(docs) < MIN_CLUSTER_SIZE:
        return []

    try:
        vectors, valid_docs = _tfidf_vectors(docs)
    except Exception as exc:
        logger.debug("RAPTOR TF-IDF vectorization failed: %s", exc)
        return []

    clusters = _cluster(vectors, valid_docs)
    nodes: list[RaptorNode] = []

    for cluster_id, cluster_docs in clusters.items():
        if len(cluster_docs) < 2:
            continue
        summary = await _summarize(cluster_docs, llm)
        if not summary:
            continue
        nodes.append(RaptorNode(
            cluster_id=cluster_id,
            summary=summary,
            source_doc_ids=[d.id for d in cluster_docs],
            level=0,
            topics=_top_words(cluster_docs),
        ))
        if len(nodes) >= MAX_RAPTOR_NODES:
            break

    logger.info(
        "RAPTOR: %d cluster summaries from %d docs", len(nodes), len(valid_docs),
    )
    return nodes


def _tfidf_vectors(docs: list[StoredDocument]) -> tuple[object, list[StoredDocument]]:
    from sklearn.feature_extraction.text import TfidfVectorizer

    texts = [f"{d.title} {d.content[:600]}" for d in docs]
    vec = TfidfVectorizer(max_features=512, stop_words="english", min_df=2, sublinear_tf=True)
    matrix = vec.fit_transform(texts)
    return matrix, docs


def _cluster(vectors: object, docs: list[StoredDocument]) -> dict[str, list[StoredDocument]]:
    from sklearn.cluster import AgglomerativeClustering

    n = min(MAX_RAPTOR_NODES, max(2, len(docs) // 5))
    try:
        X = vectors.toarray()  # type: ignore[union-attr]
    except AttributeError:
        X = vectors
    labels = AgglomerativeClustering(n_clusters=n).fit_predict(X)
    result: dict[str, list[StoredDocument]] = {}
    for doc, label in zip(docs, labels):
        result.setdefault(str(label), []).append(doc)
    return result


async def _summarize(docs: list[StoredDocument], llm: LLMClient) -> str | None:
    snippets = "\n\n".join(
        f"[{d.source}] {d.title}: {d.content[:250]}" for d in docs[:8]
    )
    prompt = (
        f"Summarise the common themes across these {len(docs)} related documents "
        f"in 2-3 sentences. Focus on key people, projects, and decisions.\n\n{snippets}"
    )
    try:
        out = await asyncio.wait_for(
            llm.generate(
                prompt,
                system="You are a document cluster summariser. Be concise and factual.",
            ),
            timeout=15.0,
        )
        return out.strip() if out else None
    except Exception as exc:
        logger.debug("RAPTOR summary failed: %s", exc)
        return None


def _top_words(docs: list[StoredDocument], n: int = 5) -> list[str]:
    stop = {
        "this", "that", "with", "from", "have", "been", "will", "they",
        "were", "what", "when", "your", "also", "more", "into", "about",
        "which", "there", "their", "these", "those", "other", "some",
    }
    words: list[str] = []
    for d in docs:
        words.extend(re.findall(r"\b[A-Za-z]{4,}\b", f"{d.title} {d.content[:200]}"))
    counter = Counter(w.lower() for w in words if w.lower() not in stop)
    return [w for w, _ in counter.most_common(n)]
