# 简单的文本分词函数，将文本转换为小写并去掉标点符号，返回单词列表
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