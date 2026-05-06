# 根据问题和相关 notes 列表，构建一个提示文本，要求 LLM 只根据这些 notes 来回答问题，并在最后注明使用了哪些 note ID
def build_answer_prompt(question: str, notes: list[dict], max_note_chars: int = 1200, strict_grounding: bool = True,) -> str:
    note_blocks = []
    for note in notes:
        #max_note_chars = int(self.config.get("max_note_chars", 1200))
        content = str(note.get("content", ""))[:max_note_chars]
        note_blocks.append(f"[{note['id']}]\n{content}")

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
    