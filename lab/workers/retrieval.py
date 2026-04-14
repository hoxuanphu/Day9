"""
workers/retrieval.py — Retrieval Worker
Sprint 2: Implement retrieval từ ChromaDB, trả về chunks + sources.

Input (từ AgentState):
    - task: câu hỏi cần retrieve
    - (optional) retrieved_chunks nếu đã có từ trước

Output (vào AgentState):
    - retrieved_chunks: list of {"text", "source", "score", "metadata"}
    - retrieved_sources: list of source filenames
    - worker_io_log: log input/output của worker này

Gọi độc lập để test:
    python workers/retrieval.py
"""

import os
import sys
import re

# ─────────────────────────────────────────────
# Worker Contract (xem contracts/worker_contracts.yaml)
# Input:  {"task": str, "top_k": int = 3}
# Output: {"retrieved_chunks": list, "retrieved_sources": list, "error": dict | None}
# ─────────────────────────────────────────────

WORKER_NAME = "retrieval_worker"
DEFAULT_TOP_K = 3


def _get_embedding_fn():
    """
    Trả về embedding function.
    TODO Sprint 1: Implement dùng OpenAI hoặc Sentence Transformers.
    """
    # Option A: Sentence Transformers (offline, không cần API key)
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        def embed(text: str) -> list:
            return model.encode([text])[0].tolist()
        return embed
    except ImportError:
        pass

    # Option B: OpenAI (cần API key)
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        def embed(text: str) -> list:
            resp = client.embeddings.create(input=text, model="text-embedding-3-small")
            return resp.data[0].embedding
        return embed
    except ImportError:
        pass

    # Fallback: random embeddings cho test (KHÔNG dùng production)
    import random
    def embed(text: str) -> list:
        return [random.random() for _ in range(384)]
    print("⚠️  WARNING: Using random embeddings (test only). Install sentence-transformers.")
    return embed


def _get_collection():
    """
    Kết nối ChromaDB collection.
    TODO Sprint 2: Đảm bảo collection đã được build từ Step 3 trong README.
    """
    import chromadb
    client = chromadb.PersistentClient(path="./chroma_db")
    try:
        collection = client.get_collection("day09_docs")
    except Exception:
        # Auto-create nếu chưa có
        collection = client.get_or_create_collection(
            "day09_docs",
            metadata={"hnsw:space": "cosine"}
        )
        print(f"⚠️  Collection 'day09_docs' chưa có data. Chạy index script trong README trước.")
    return collection


def _tokenize(text: str) -> set:
    """Tokenize đơn giản để tính overlap query-chunk."""
    tokens = re.findall(r"[a-zA-Z0-9_]+", (text or "").lower())
    stopwords = {
        "la", "va", "the", "cho", "voi", "mot", "nhung", "duoc", "trong",
        "is", "the", "a", "an", "and", "or", "to", "of", "for", "in",
    }
    return {t for t in tokens if len(t) > 2 and t not in stopwords}


def _rerank_and_filter(chunks: list, query: str, top_k: int) -> list:
    """
    Rerank nhẹ theo lexical overlap và lọc chunk nhiễu.
    Giữ đúng tinh thần lab: grounded, không bịa dữ liệu.
    """
    if not chunks:
        return []

    query_tokens = _tokenize(query)
    scored = []
    for chunk in chunks:
        text_tokens = _tokenize(chunk.get("text", ""))
        overlap = len(query_tokens.intersection(text_tokens))
        overlap_ratio = overlap / max(1, len(query_tokens))
        base_score = float(chunk.get("score", 0.0))

        # Rerank score: ưu tiên relevance gốc, cộng nhẹ overlap lexical
        rerank_score = (0.8 * base_score) + (0.2 * overlap_ratio)

        metadata = dict(chunk.get("metadata", {}))
        metadata["overlap_count"] = overlap
        metadata["overlap_ratio"] = round(overlap_ratio, 4)
        metadata["rerank_score"] = round(rerank_score, 4)
        chunk["metadata"] = metadata
        scored.append((rerank_score, overlap, chunk))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    # Lọc nhiễu: giữ chunk nếu score đủ tốt hoặc có overlap trực tiếp
    filtered = []
    for rerank_score, overlap, chunk in scored:
        if rerank_score >= 0.35 or overlap >= 1:
            filtered.append(chunk)
        if len(filtered) >= top_k:
            break

    # Fallback: nếu lọc quá gắt và mất hết, giữ top 1 theo rerank
    if not filtered and scored:
        filtered = [scored[0][2]]

    return filtered


def retrieve_dense(query: str, top_k: int = DEFAULT_TOP_K) -> list:
    """
    Dense retrieval: embed query → query ChromaDB → trả về top_k chunks.

    TODO Sprint 2: Implement phần này.
    - Dùng _get_embedding_fn() để embed query
    - Query collection với n_results=top_k
    - Format result thành list of dict

    Returns:
        list of {"text": str, "source": str, "score": float, "metadata": dict}
    """
    # TODO: Implement dense retrieval
    embed = _get_embedding_fn()
    query_embedding = embed(query)

    try:
        collection = _get_collection()
        candidate_k = max(top_k * 2, top_k + 2)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=candidate_k,
            include=["documents", "distances", "metadatas"]
        )

        chunks = []
        for i, (doc, dist, meta) in enumerate(zip(
            results["documents"][0],
            results["distances"][0],
            results["metadatas"][0]
        )):
            raw_distance = float(dist)
            # Map cosine distance [0, 2] -> similarity-like score [0, 1]
            raw_score = 1.0 - (raw_distance / 2.0)
            score = max(0.0, min(1.0, raw_score))
            metadata = dict(meta or {})
            metadata["raw_distance"] = round(raw_distance, 6)
            metadata["raw_score"] = round(raw_score, 6)
            metadata["score_mapping"] = "score = clamp(1 - distance/2, 0, 1)"
            chunks.append({
                "text": doc,
                "source": metadata.get("source", "unknown"),
                "score": round(score, 4),
                "metadata": metadata,
            })
        return _rerank_and_filter(chunks, query=query, top_k=top_k)

    except Exception as e:
        print(f"⚠️  ChromaDB query failed: {e}")
        # Fallback: return empty (abstain)
        return []


def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.

    Args:
        state: AgentState dict

    Returns:
        Updated AgentState với retrieved_chunks và retrieved_sources
    """
    task = state.get("task", "")
    top_k = state.get("retrieval_top_k", DEFAULT_TOP_K)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])

    state["workers_called"].append(WORKER_NAME)

    # Log worker IO (theo contract)
    worker_io = {
        "worker": WORKER_NAME,
        "input": {"task": task, "top_k": top_k},
        "output": None,
        "error": None,
    }

    try:
        chunks = retrieve_dense(task, top_k=top_k)

        sources = list({c["source"] for c in chunks})

        state["retrieved_chunks"] = chunks
        state["retrieved_sources"] = sources

        worker_io["output"] = {
            "chunks_count": len(chunks),
            "sources": sources,
        }
        state["history"].append(
            f"[{WORKER_NAME}] retrieved {len(chunks)} chunks from {sources}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "RETRIEVAL_FAILED", "reason": str(e)}
        state["retrieved_chunks"] = []
        state["retrieved_sources"] = []
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    # Ghi worker IO vào state để trace
    state.setdefault("worker_io_logs", []).append(worker_io)

    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Retrieval Worker — Standalone Test")
    print("=" * 50)

    test_queries = [
        "SLA ticket P1 là bao lâu?",
        "Điều kiện được hoàn tiền là gì?",
        "Ai phê duyệt cấp quyền Level 3?",
    ]

    for query in test_queries:
        print(f"\n▶ Query: {query}")
        result = run({"task": query})
        chunks = result.get("retrieved_chunks", [])
        print(f"  Retrieved: {len(chunks)} chunks")
        for c in chunks[:2]:
            print(f"    [{c['score']:.3f}] {c['source']}: {c['text'][:80]}...")
        print(f"  Sources: {result.get('retrieved_sources', [])}")

    print("\n✅ retrieval_worker test done.")
