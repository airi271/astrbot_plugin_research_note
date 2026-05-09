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


# 根据问题的向量表示和 chunks，返回余弦相似度最高的 top_k 个 chunks。
def search_chunks_by_embedding(
    query_embedding: list[float],
    chunks: list[dict],
    top_k: int = 3,
) -> list[dict]:
    scored = []
    for chunk in chunks:
        chunk_embedding = chunk.get("embedding")
        if not isinstance(chunk_embedding, list):
            continue
        score = cosine_similarity(query_embedding, chunk_embedding)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for score, chunk in scored[:top_k]]
