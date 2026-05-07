# 简单的文本分词函数，将文本转换为小写并去掉标点符号，返回单词列表
import math


def tokenize(text: str) -> list[str]:
    normalized = text.lower().replace("\n", " ")
    tokens = []
    for token in normalized.split():
        token = token.strip(".,!?;:()[]{}<>。、！？「」『』（）")
        if token:
            tokens.append(token)
    return tokens
# 计算一个 note 与问题的相关度得分，简单地统计问题中的单词在 note 内容中出现的次数
def score_note(question: str, note: dict) -> int:
    tokens = tokenize(question)
    content = str(note.get("content", "")).lower()
    score = 0
    for token in tokens:
        if token in content:
            score += 1
    return score
    # 根据问题和 notes 列表，计算每个 note 的相关度得分，返回得分最高的 top_k 个 notes
def search_notes(question: str, notes: list[dict], top_k: int = 3) -> list[dict]:
    scored = []
    for note in notes:
        score = score_note(question, note)
        if score > 0:
            scored.append((score, note))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [note for score, note in scored[:top_k]]
# 计算两个向量之间的余弦相似度
def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
# 根据问题的向量表示和 notes 列表，计算每个 note 与问题的余弦相似度得分，返回得分最高的 top_k 个 notes
def search_notes_by_embedding(
    query_embedding: list[float],
    notes: list[dict],
    top_k: int = 3,
) -> list[dict]:
    scored = []
    for note in notes:
        note_embedding = note.get("embedding")
        if not isinstance(note_embedding, list):
            continue
        score = cosine_similarity(query_embedding, note_embedding)
        if score > 0:
            scored.append((score, note))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [note for score, note in scored[:top_k]]