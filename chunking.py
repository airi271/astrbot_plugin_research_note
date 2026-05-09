def split_text_into_chunks(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[str]:
    text = text.strip()
    if not text:
        return []

    chunk_size = max(1, chunk_size)
    chunk_overlap = max(0, min(chunk_overlap, chunk_size - 1))
    step = chunk_size - chunk_overlap

    chunks = []
    start = 0
    while start < len(text):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += step
    return chunks
