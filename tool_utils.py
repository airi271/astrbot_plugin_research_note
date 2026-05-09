from .search import search_chunk_results_by_embedding


class ResearchToolError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


async def search_research_store(
    store,
    query: str,
    top_k: int,
    embedding_provider,
    min_embedding_score: float = 0.0,
) -> tuple[dict, list[dict]]:
    if not embedding_provider:
        raise ResearchToolError("embedding_provider_missing")

    data = store.load_store()
    if not data["chunks"]:
        raise ResearchToolError("empty_store")
    if any(not isinstance(chunk.get("embedding"), list) for chunk in data["chunks"]):
        raise ResearchToolError("missing_embedding")

    try:
        query_embedding = await embedding_provider.get_embedding(query)
    except Exception as exc:
        raise ResearchToolError("query_embedding_failed") from exc

    results = search_chunk_results_by_embedding(
        query_embedding,
        data["documents"],
        data["chunks"],
        top_k=top_k,
        min_embedding_score=min_embedding_score,
    )
    return data, results


def compact_search_results(results: list[dict], preview_chars: int = 240) -> dict:
    compact = []
    for result in results:
        chunk = result["chunk"]
        document = result.get("document", {})
        compact.append(
            {
                "doc_id": chunk.get("doc_id"),
                "chunk_id": chunk.get("id"),
                "title": document.get("title", ""),
                "source_uri": document.get("source_uri", ""),
                "score": round(float(result.get("embedding_score", 0.0)), 4),
                "preview": str(chunk.get("content", ""))[:preview_chars],
            }
        )
    return {"results": compact}


def get_document_summary(store, doc_id: str, preview_chars: int = 240) -> dict:
    data = store.load_store()
    document = next(
        (doc for doc in data["documents"] if doc.get("id") == doc_id), None
    )
    if not document:
        return {"error": "document_not_found", "doc_id": doc_id}

    chunks = [chunk for chunk in data["chunks"] if chunk.get("doc_id") == doc_id]
    return {
        "document": document,
        "chunk_count": len(chunks),
        "chunks": [
            {
                "chunk_id": chunk.get("id"),
                "index": chunk.get("index"),
                "has_embedding": isinstance(chunk.get("embedding"), list),
                "preview": str(chunk.get("content", ""))[:preview_chars],
            }
            for chunk in chunks[:10]
        ],
    }
