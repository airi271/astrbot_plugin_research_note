import math


# 计算两个向量之间的余弦相似度。
def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_document_index(documents: list[dict]) -> dict[str, dict]:
    return {str(doc.get("id")): doc for doc in documents}


# 根据问题的向量表示和 chunks，返回余弦相似度最高的検索結果。
def search_chunk_results_by_embedding(
    query_embedding: list[float],
    documents: list[dict],
    chunks: list[dict],
    top_k: int = 3,
    min_embedding_score: float = 0.0,
) -> list[dict]:
    doc_index = build_document_index(documents)
    results = []
    for chunk in chunks:
        chunk_embedding = chunk.get("embedding")
        if not isinstance(chunk_embedding, list):
            continue
        score = cosine_similarity(query_embedding, chunk_embedding)
        if score < min_embedding_score:
            continue
        results.append(
            {
                "chunk": chunk,
                "document": doc_index.get(str(chunk.get("doc_id")), {}),
                "embedding_score": score,
            }
        )

    results.sort(key=lambda item: item["embedding_score"], reverse=True)
    return results[:top_k]
