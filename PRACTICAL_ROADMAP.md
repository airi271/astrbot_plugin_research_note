# Research Note 実用化ロードマップ

このドキュメントは、現在の `Research Note` を根拠付き研究補助 AstrBot プラグインとして実用レベルに近づけるための開発方針です。

結論から言うと、難しいですが現実的です。ただし、既存サービスの再現を目標にするのではなく、AstrBot の強みである `FunctionTool`、`tool_loop_agent()`、MCP、Knowledge Base、Web Search、SubAgent を段階的に取り込む方が安全です。

各 Phase の詳しい手順は `docs/practical_steps/README.md` から順番に読めます。

## 現在地

現時点でできていることです。

- `/research add` で資料テキストを保存できる。
- `/research list` で保存済み資料を確認できる。
- `/research ask` で関連資料を検索し、LLM に渡して回答できる。
- JSON 保存ができる。
- embedding provider を使って embedding 検索できる。
- 全 chunk に embedding を付ける方針で、キーワード検索 fallback は使わない。
- `top_k`、`max_note_chars`、`max_add_chars`、`strict_grounding` を設定化できている。

現在の実装は「学習用の最小 RAG」としては十分です。実用化では、次の問題を順番に解決します。

- 長い資料をそのまま1件の note として扱っている。
- 資料のタイトル、出典 URL、著者、タグ、プロジェクト名などの metadata がない。
- 引用が note ID 単位で、本文のどこに基づくかが弱い。
- URL、PDF、Markdown、Web検索結果などを資料化する入口がない。
- LLM が資料検索を自律的に使う tool になっていない。
- MCP や AstrBot 組み込み Web Search とまだ連携していない。
- 複数の専門 agent に仕事を分ける構造がまだない。

## 目標

最初の実用版は以下を目指します。

- 研究プロジェクトごとに資料を管理できる。
- URL、テキスト、ファイル由来テキストを資料として取り込める。
- 長文資料を chunk に分け、chunk 単位で検索できる。
- 回答に根拠となった chunk ID、タイトル、出典を出せる。
- LLM が必要なときに `research_search` などの tool を呼べる。
- `/research ask` は「固定 RAG」、`/research agent` は「tool 使用 agent」として使い分ける。
- MCP や AstrBot 組み込み Web Search は外部調査、ファイル読取、ページ抽出の補助として使う。
- Multi-Agent は後半で、検索、要約、批判的検証、執筆を分担する。

## 判断

### 難易度

実用レベルまでは中から高です。理由は、UIよりも「資料をどう分割し、検索し、引用し、幻覚を抑えるか」が難しいためです。

ただし、AstrBot には次の土台があります。

- `Context.llm_generate()` で通常の LLM 呼び出しができる。
- `Context.tool_loop_agent()` で LLM が tool を呼ぶ agent loop を使える。
- `FunctionTool` と `ToolSet` で独自 tool を定義できる。
- `context.add_llm_tools()` または `@filter.llm_tool` で tool を登録できる。
- MCP server は `data/mcp_server.json` から読み込まれ、MCP tool として `FunctionToolManager` に登録される。
- 組み込み tool として Web Search、Knowledge Base、File Read、Grep、Python、Shell などがある。
- SubAgent Orchestrator は `transfer_to_*` の handoff tool を使う構造になっている。

そのため、Research Note 側は全部を自作せず、まず「研究資料ストア」と「研究用 tool 群」に集中するのがよいです。

### 作らない方がよいもの

初期実用版では以下は後回しにします。

- 特定サービスの UI 完全再現。
- 音声概要生成。
- 複雑な PDF レイアウト解析。
- 独自ベクトル DB サーバー運用。
- 全 AstrBot 会話への常時自動注入。
- すべての MCP tool を無制限に agent に渡すこと。

## 推奨アーキテクチャ

### 1. データ層

JSON から始めますが、note 単位ではなく document と chunk に分けます。

```text
Document
- id: doc_001
- project_id: default
- title: Attention Is All You Need
- source_type: text | url | file | web
- source_uri: URL or file path or empty
- tags: [transformer, llm]
- created_at
- updated_at

Chunk
- id: chunk_001
- doc_id: doc_001
- index: 0
- content: chunk text
- embedding: list[float] | null
- metadata: page, heading, url, etc.
```

最初は `research_store.json` ひとつにまとめてよいです。資料が増えたら `documents.json`、`chunks.json`、`indexes.json` に分けます。

### 2. 検索層

検索は3段階にします。

- `keyword`: provider なしでも動く最低限の検索。
- `embedding`: AstrBot embedding provider がある場合の意味検索。
- `hybrid`: keyword と embedding のスコアを混ぜる検索。

実用上は hybrid が最も安定します。固有名詞、式、論文名は keyword が強く、言い換え質問は embedding が強いためです。

### 3. 回答層

回答は必ず context pack を作ってから LLM に渡します。

```text
Question
Context chunks
Citation rules
Answer format
Uncertainty rules
```

回答には最低限、以下を出します。

- Answer
- Sources
- Unknowns

`Unknowns` は資料から分からない点を明示する欄です。研究補助では、分からないことを分からないと言える方が重要です。

### 4. Tool 層

Research Note 自体を LLM tool として登録します。

最初に作る tool です。

- `research_search`: 保存済み資料から関連 chunk を検索する。
- `research_get_document`: document ID で資料概要と chunk 一覧を返す。
- `research_add_text`: テキストを資料として追加する。
- `research_summarize_document`: document 単位で要約する。

後で追加する tool です。

- `research_import_url`: URL を取得して資料化する。
- `research_web_search`: Web検索結果を候補として返す。
- `research_extract_claims`: 資料から主張、根拠、未解決点を抽出する。
- `research_compare_sources`: 複数資料の一致点と矛盾点を比較する。

### 5. Agent 層

`/research ask` は従来通り短く確実な RAG として残します。

`/research agent` を新設し、`tool_loop_agent()` を使います。この agent は必要に応じて `research_search`、Web Search、MCP tool を呼びます。

用途の違いです。

- `/research ask`: 速い、予測しやすい、検索して答えるだけ。
- `/research agent`: 遅いが強い、検索、追加調査、比較、要約、深掘りができる。

## AstrBot 機能の使い方

### FunctionTool

Research Note の検索、追加、要約を `FunctionTool` として公開します。これにより、通常のコマンドだけでなく agent からも同じ機能を呼べます。

参照先です。

- `astrbot/core/agent/tool.py`
- `docs/en/dev/star/guides/ai.md`
- `docs/zh/dev/star/plugin.md`

### tool_loop_agent

`tool_loop_agent()` は LLM が tool を呼び、結果を見てまた考える loop を実行します。「質問に応じて資料を探す」「必要なら Web も見る」研究補助の動きに向いています。

Research Note では `/research agent <task>` に使います。

### MCP

MCP は Research Note の中で直接実装しすぎない方がよいです。AstrBot 本体が `data/mcp_server.json` から MCP server を起動し、MCP tool を `FunctionToolManager` に登録します。

Research Note 側では次の方針にします。

- MCP tool は agent mode で必要なものだけ `ToolSet` に入れる。
- ファイル読取、外部論文検索、ブラウザ操作などは MCP に任せる余地を残す。
- どの MCP tool を許可するかは設定で allowlist にする。

### 組み込み Web Search

AstrBot には Baidu、Tavily、BoCha、Brave、Firecrawl 系の Web Search / Extract tool があります。API key や provider 設定が必要なものがあるため、Research Note の必須機能にはしません。

使う場合は `/research agent` から呼ばせ、検索結果をすぐ保存するのではなく、ユーザー確認後に `/research import` する流れが安全です。

### Knowledge Base

AstrBot 既存 Knowledge Base は大規模資料管理に強い可能性があります。ただし Research Note の目的は「研究プロジェクトと引用管理」なので、最初は別物として扱います。

将来は次のどちらかを選べます。

- Research Note 独自ストアを続ける。
- AstrBot Knowledge Base を backend として使い、Research Note は研究用 UI と引用整形を担当する。

### Multi-Agent

最初から入れる必要はありません。研究補助で本当に有効になるのは、資料数と作業種類が増えてからです。

候補 agent です。

- Retriever Agent: 資料検索と context pack 作成。
- Reader Agent: 長い資料の要約、章ごとの整理。
- Critic Agent: 回答の根拠不足、矛盾、飛躍を指摘。
- Writer Agent: 研究ノート、比較表、発表原稿を作る。

AstrBot の SubAgent Orchestrator を使う場合は、設定で `transfer_to_*` tool を作り、各 subagent に Research Note tool や Web Search tool を割り当てます。

## 開発フェーズ

## Phase 1: 実用品質の土台作り

目的は、今の学習用コードを壊れにくい最小実用品質にすることです。

作業です。

- 不要な `helloworld`、`research_hellow`、未使用 import を削除する。
- `research add` で content を取り出してから embedding を作る順番に直す。
- `provider_id` 取得失敗時の例外を握りつぶさず、ユーザー向けメッセージにする。
- `NoteStore.load_notes(logger)` の logger 引数をなくし、store 内で破損時の扱いを整理する。
- 保存時に一時ファイル経由で atomic write する。
- `note_001` 方式を、削除後も重複しない ID 生成に変える。
- `/research delete <id>`、`/research show <id>` を追加する。
- `/research reindex` で既存資料の embedding を作り直す。
- 回答に debug prompt を常時出さない設定を追加する。

完了条件です。

- 既存テストが通る。
- JSON が壊れても起動不能にならない。
- 追加、一覧、表示、削除、質問、再 indexing が一通り動く。

## Phase 2: Document と Chunk への移行

目的は、長文資料を扱える構造にすることです。

作業です。

- `Note` を `Document` と `Chunk` に分ける。
- `/research add` は内部で chunk 分割する。
- chunk size、chunk overlap を設定化する。
- 検索結果は chunk 単位にする。
- 回答の source は `doc_id`、`chunk_id`、title、source_uri を出す。
- 空の `research_notes.json` から新形式で保存を始める。

完了条件です。

- 1万文字以上の資料でも検索と回答が安定する。
- 引用が note 単位ではなく chunk 単位になる。
- 古い JSON から移行できる。

## Phase 3: Hybrid Search と Citation

目的は、検索品質と根拠表示を改善することです。

作業です。

- keyword score と embedding score を別々に計算する。
- hybrid score を実装する。
- 検索結果に score と match reason を付ける。
- `min_score`、`top_k`、`max_context_chars` を設定化する。
- 回答 prompt に citation rule を明記する。
- `/research search <query>` で LLM を呼ばず検索結果だけ確認できるようにする。

完了条件です。

- 固有名詞、短いキーワード、言い換え質問のすべてで検索できる。
- `/research search` でなぜその資料が選ばれたか確認できる。
- 回答に使った chunk が明示される。

## Phase 4: Research Tools 化

目的は、Research Note を agent から呼べる能力として公開することです。

作業です。

- `tools/research_search.py` などを作り、`FunctionTool` を定義する。
- `research_search` tool を `context.add_llm_tools()` で登録する。
- `research_get_document` tool を作る。
- `research_add_text` tool を作る。
- tool の返却は長すぎない JSON 文字列にする。
- tool 用の unit test を追加する。

完了条件です。

- LLM が通常会話や agent mode から Research Note 検索を呼べる。
- tool の返却が短く、引用に必要な情報を含む。
- コマンド実装と tool 実装で検索ロジックを重複させない。

## Phase 5: Agent Mode

目的は、自律的に資料検索や整理を行う研究補助を作ることです。

作業です。

- `/research agent <task>` を追加する。
- `tool_loop_agent()` を使い、`research_search` と `research_get_document` を渡す。
- system prompt に「資料検索を先に行う」「根拠がない場合は不明と言う」を入れる。
- max_steps、tool_call_timeout を設定化する。
- agent が呼んだ tool と最終 source をログに残す。
- `/research agent` は最初は Research Note tool のみに限定する。

完了条件です。

- ユーザーが曖昧に質問しても、agent が検索してから答える。
- 必要以上に tool を呼び続けない。
- 通常の `/research ask` より深い比較、整理、要約ができる。

## Phase 6: Import 機能

目的は、研究資料を手で貼り付ける負担を減らすことです。

作業です。

- `/research import url <url>` を追加する。
- 最初は `aiohttp` で HTML を取得し、title と本文候補を抽出する。
- Firecrawl extract tool が使える環境では agent mode から利用できるようにする。
- `/research import text --title <title>` を追加する。
- ファイル import は AstrBot の file read tool または MCP file tool との連携を検討する。
- import 前に preview を出し、保存確認を求める。

完了条件です。

- URL から資料を取り込める。
- 取り込み結果の title、source_uri、chunk 数を確認できる。
- 壊れたページや長すぎるページで安全に失敗できる。

## Phase 7: Web Research 連携

目的は、保存済み資料だけでは足りない場合に外部調査できるようにすることです。

作業です。

- 設定に `enable_web_research` を追加する。
- AstrBot 組み込み Web Search tool を allowlist で選べるようにする。
- `/research agent` に Web Search tool を追加するモードを作る。
- 検索結果は即保存せず、候補として返す。
- `/research save-web-result <result_id>` のような確認付き保存を作る。
- 外部情報と保存済み資料を回答上で区別する。

完了条件です。

- 保存済み資料だけでは不十分な質問で、Web検索候補を提示できる。
- 外部情報を勝手に永続保存しない。
- 回答で「保存済み資料」と「Web検索結果」が混ざらず表示される。

## Phase 8: MCP 連携

目的は、外部ツールやローカル資料処理を拡張可能にすることです。

作業です。

- 設定に `allowed_mcp_tools` を追加する。
- `context.get_llm_tool_manager()` から指定 tool だけを `ToolSet` に入れる helper を作る。
- `/research agent --mcp` のように MCP 使用を明示的にする。
- MCP tool の結果を Research Note に保存する場合は必ず確認を挟む。
- MCP tool のエラー、timeout、長すぎる結果を整形する。

完了条件です。

- 許可した MCP tool だけ agent が使える。
- MCP tool の暴走や不要な外部アクセスを抑制できる。
- file、paper search、browser などを後から差し替えられる。

## Phase 9: Multi-Agent 化

目的は、研究作業を分担して品質を上げることです。

作業です。

- まず plugin 内の `FunctionTool` として subagent を作る。
- `RetrieverAgentTool` は検索と context pack 作成だけ担当する。
- `ReaderAgentTool` は資料要約だけ担当する。
- `CriticAgentTool` は回答の根拠不足と矛盾を指摘する。
- `WriterAgentTool` は最終回答、比較表、研究ノート整形を担当する。
- うまく動いたら AstrBot SubAgent Orchestrator の設定方式へ寄せる。

完了条件です。

- 複数資料の比較で、単一 agent より安定した回答になる。
- 根拠不足や矛盾を検出できる。
- 役割ごとの prompt と tool が分離される。

## Phase 10: 研究ノート出力

目的は、回答だけでなく研究成果物を作れるようにすることです。

作業です。

- `/research brief <topic>` で短い研究ブリーフを作る。
- `/research outline <topic>` で章立てを作る。
- `/research compare <query>` で比較表を作る。
- `/research claims <doc_id>` で主張、根拠、限界を抽出する。
- Markdown 出力を整える。
- 出力に source list を必ず付ける。

完了条件です。

- 研究メモ、比較表、発表下書きの生成ができる。
- すべての成果物に source が付く。
- 保存済み資料だけで作った内容と、一般知識を含む内容が区別される。

## Phase 11: 保存 backend の強化

目的は、資料数が増えたときの性能と安全性を確保することです。

作業です。

- JSON が遅くなったら SQLite へ移行する。
- embedding は SQLite の別テーブルまたはファイルに分ける。
- 必要になったら Milvus / Milvus Lite を検討する。
- backup と export/import を作る。
- schema_version を保存し migration を管理する。

完了条件です。

- 数百から数千 chunk で実用速度を維持できる。
- データ移行と backup ができる。
- 壊れた保存ファイルから復旧しやすい。

## Phase 12: 品質評価

目的は、研究補助として信頼できるかを測ることです。

作業です。

- 小さな評価データセットを作る。
- 質問、期待される source、期待回答の要点を保存する。
- keyword、embedding、hybrid の検索結果を比較する。
- citation が正しいかを手動確認しやすくする。
- hallucination しやすい質問をテストに入れる。

完了条件です。

- 検索変更で品質が上がったか下がったか分かる。
- citation の抜けや誤りを発見できる。
- 実用前に regression を検出できる。

## 最初に着手する順番

最短で実用感を出すなら、この順番がよいです。

1. Phase 1 の cleanup と安全化。
2. Phase 2 の chunk 化。
3. Phase 3 の `/research search` と citation 改善。
4. Phase 4 の `research_search` tool 化。
5. Phase 5 の `/research agent`。

MCP、Web Search、Multi-Agent は魅力的ですが、chunk と citation が弱いまま入れると、外部情報が増えるだけで信頼性が下がります。まず「保存済み資料に正確に答える」能力を固めるべきです。

## 実装上の注意

- LLM に渡す context は長くしすぎない。
- source は必ず ID と短い引用本文を持たせる。
- Web や MCP の結果は、保存済み資料とは別扱いにする。
- agent に渡す tool は allowlist にする。
- delete、clear、import、web save は確認を挟む。
- embedding provider がない環境でも最低限動くようにする。
- prompt debug は設定で切り替える。
- JSON 保存中に落ちても壊れにくい atomic write にする。

## 完成イメージ

実用版では、以下のように使える状態を目指します。

```text
/research project create llm_papers
/research import url https://example.com/paper-summary
/research add --title "Transformer memo" <text>
/research search attention mechanism
/research ask この資料群では attention の利点はどう説明されている？
/research agent 関連資料を比較して、Transformer と RNN の違いを表にして
/research brief attention mechanism
```

最終的な価値は「チャット内で研究資料を蓄積し、根拠付きで検索、要約、比較、執筆補助ができること」です。特定サービスの再現ではなく、AstrBot の会話環境と tool / MCP / agent 能力を活かした研究補助を目標にします。
