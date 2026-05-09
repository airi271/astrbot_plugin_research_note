# 根据问题和相关 chunks 列表，构建提示文本，要求 LLM 只根据这些资料回答问题。
def build_answer_prompt(
    question: str,
    notes: list[dict],
    max_note_chars: int = 1200,
    strict_grounding: bool = True,
) -> str:
    note_blocks = []
    for note in notes:
        content = str(note.get("content", ""))[:max_note_chars]
        source_id = note.get("id", "unknown")
        doc_id = note.get("doc_id")
        if doc_id:
            source_id = f"{doc_id}/{source_id}"
        title = note.get("title")
        source_uri = note.get("source_uri")
        source_meta = ""
        if title or source_uri:
            source_meta = f"\ntitle: {title or ''}\nsource_uri: {source_uri or ''}"
        note_blocks.append(f"[{source_id}]{source_meta}\n{content}")

    sources = "\n\n".join(note_blocks)
    if strict_grounding:
        grounding_rule = "資料に書かれていないことは、推測せず『資料からは分かりません』と答えてください。"
    else:
        grounding_rule = "資料を優先し、不足する部分は一般知識で補っても構いません。"
    return f"""あなたは研究補助AIです。
以下の資料だけを根拠にして、ユーザーの質問に日本語で答えてください。
{grounding_rule}
回答の最後に、使用した資料IDを短く示してください。

資料:
{sources}

質問:
{question}
"""
