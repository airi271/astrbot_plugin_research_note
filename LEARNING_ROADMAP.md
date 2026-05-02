# Research Note 学習ロードマップ

このドキュメントは、Python の基礎はあるがアプリ開発やプラグイン開発は初めて、という前提で書いた学習ロードマップです。目標は AstrBot と Mnemosyne を参考にしながら、NotebookLM に近い「研究補助プラグイン」を最小構成から作ることです。

## 目標

最初の完成形は、NotebookLM そのものではなく、NotebookLM の中心機能だけを小さく作ることです。

- 資料やメモを登録できる。
- 登録した資料を検索できる。
- 質問したときに、関連資料を LLM に渡して回答できる。
- 回答の根拠になった資料を表示できる。
- 最初は JSON 保存で作り、後から embedding 検索やベクトルDBに置き換える。

最初から PDF 読み込み、URL 取得、Web 管理画面、Milvus、長期会話記憶、引用 UI まで作ろうとすると難しすぎます。まずは「動く小さいもの」を作り、それを少しずつ強くします。

## 今の作業場所

AstrBot 本体は以下にあります。

```bash
/home/ayaka/codding/astrbotpj/AstrBot
```

このプラグインは以下にあります。

```bash
/home/ayaka/codding/astrbotpj/AstrBot/data/plugins/astrbot_plugin_research_note
```

Python 仮想環境は以下です。

```bash
/home/ayaka/.virtualenvs/.venv
```

作業前には基本的に以下を実行します。

```bash
source /home/ayaka/.virtualenvs/.venv/bin/activate
cd /home/ayaka/codding/astrbotpj/AstrBot
python main.py
```

Python バージョンは確認時点で `Python 3.12.3` です。

## 最初に理解する全体像

AstrBot プラグインは、普通の Python プログラムではなく、AstrBot から呼び出される部品です。

重要な考え方はこの5つです。

- `main.py` がプラグインの入口になる。
- `class MyPlugin(Star)` のように `Star` を継承したクラスを書く。
- `@register(...)` でプラグイン情報を AstrBot に登録する。
- `@filter.command("xxx")` で `/xxx` のようなコマンドを作る。
- `@filter.on_llm_request()` を使うと、LLM に送る前のリクエストを書き換えられる。

Research Note で最も大事なのは、最後の `on_llm_request` です。ここで質問に関連する資料を探し、LLM に渡すプロンプトへ追加すると、RAG らしい動きになります。

## AstrBot で先に読むファイル

以下の順番で読むと迷いにくいです。

コードや用語が分からない場合は、先に以下の補助資料を読んでください。

- `docs/concepts/README.md`: 補助資料の入口。
- `docs/concepts/01_python_for_plugins.md`: クラス、self、import、JSON など。
- `docs/concepts/02_astrbot_plugin_terms.md`: AstrBot の用語。
- `docs/concepts/03_yield_async_event.md`: `yield`、`async/await`、イベント処理。
- `docs/concepts/04_rag_terms.md`: RAG、embedding、top_k、chunk など。
- `docs/concepts/05_developer_workflow.md`: 開発者の読み方、調べ方、デバッグ方法。

### 1. 最小プラグイン

```text
/home/ayaka/codding/astrbotpj/AstrBot/docs/zh/dev/star/guides/simple.md
```

ここで見るものは以下です。

- `Star` を継承する形。
- `__init__` の形。
- `@filter.command("helloworld")` の使い方。
- `yield event.plain_result(...)` でメッセージを返す方法。

最初はコードを完全に理解できなくても大丈夫です。まずは「この形で書くと AstrBot が呼んでくれる」と覚えます。

### 2. LLM の呼び出し

```text
/home/ayaka/codding/astrbotpj/AstrBot/docs/zh/dev/star/guides/ai.md
```

ここで見るものは以下です。

- `event.unified_msg_origin`
- `self.context.get_current_chat_provider_id(...)`
- `self.context.llm_generate(...)`

Research Note の `/research ask` では、最初はこの方法で LLM を直接呼べば十分です。

### 3. LLM リクエスト前フック

```text
/home/ayaka/codding/astrbotpj/AstrBot/docs/zh/dev/star/plugin.md
```

読む場所は `on_llm_request` の説明です。

ここで見るものは以下です。

- `@filter.on_llm_request()`
- `ProviderRequest`
- `req.prompt`
- `req.system_prompt`
- `req.contexts`

NotebookLM 風にするには、質問の前に「関連資料」を追加します。たとえば以下のようなイメージです。

```text
以下はユーザーが登録した研究資料です。

[資料1]
...

[資料2]
...

上の資料だけを根拠にして質問に答えてください。

質問:
...
```

### 4. プラグイン設定

```text
/home/ayaka/codding/astrbotpj/AstrBot/docs/zh/dev/star/guides/plugin-config.md
```

ここで見るものは以下です。

- `_conf_schema.json`
- `AstrBotConfig`
- `__init__(self, context: Context, config: AstrBotConfig)`
- `self.config.get(...)`

最初は設定なしでも作れます。ただし、後で `top_k`、保存先、検索方式、引用表示の有無などを設定化したくなります。

## Mnemosyne で読むべき場所

Mnemosyne は大きなプラグインです。最初から全部読む必要はありません。Research Note に必要な部分だけを読みます。

Mnemosyne は以下にあります。

```text
/home/ayaka/codding/astrbotpj/AstrBot/data/plugins/astrbot_plugin_mnemosyne
```

### 1. プラグインの入口

```text
main.py
```

見る場所は以下です。

- `@register(...)`
- `class Mnemosyne(Star)`
- `__init__`
- `@filter.on_llm_request()`
- `@filter.on_llm_response()`
- `@filter.command_group("memory")`

特に重要なのは `query_memory` です。これは LLM に送る前に長期記憶を検索して、プロンプトへ注入する入口です。

### 2. 検索してプロンプトへ入れる処理

```text
core/memory_operations.py
```

見る関数は以下です。

- `handle_query_memory(...)`
- `_format_and_inject_memory(...)`
- `clean_contexts(...)`
- `store_manual_memory(...)`

Research Note では、Mnemosyne のような「会話の長期記憶」ではなく「研究資料ノート」を扱います。ただし、仕組みは似ています。

- ユーザーの質問を受け取る。
- 関連する情報を探す。
- 見つかった情報をプロンプトに入れる。
- LLM に回答させる。

### 3. 設定ファイル

```text
_conf_schema.json
```

見る項目は以下です。

- `LLM_providers`
- `embedding_provider_id`
- `top_k`
- `memory_injection_method`
- `memory_injection_position`

Research Note でも似た設定を後から作れます。

最初に必要そうな設定は以下です。

- `top_k`: 検索で何件の資料を使うか。
- `max_note_chars`: 1件の資料を何文字まで使うか。
- `answer_with_sources`: 回答に根拠資料を出すか。
- `storage_file`: JSON の保存ファイル名。

## Mnemosyne と Research Note の違い

Mnemosyne は長期記憶プラグインです。会話を自動で要約し、Milvus に保存し、次の会話で思い出します。

Research Note は研究補助プラグインです。ユーザーが明示的に資料を追加し、その資料に基づいて質問に答えます。

| 項目 | Mnemosyne | Research Note 最小版 |
| --- | --- | --- |
| 目的 | 会話の長期記憶 | 研究資料に基づくQA |
| 保存対象 | 会話要約、手動記憶 | ユーザーが登録した資料 |
| 保存先 | Milvus / Milvus Lite | 最初は JSON |
| 検索 | embedding + ベクトル検索 | 最初はキーワード検索 |
| LLM注入 | on_llm_request で記憶を注入 | ask コマンドまたは on_llm_request で資料を注入 |
| 難易度 | 高い | 低く始められる |

最初は Research Note を小さく作り、必要になったら Mnemosyne の技術を一つずつ取り込みます。

## 開発ステップ

### Step 0: Git と作業ルールに慣れる

まず覚えるコマンドは少なくてよいです。

```bash
git status
git branch
git diff
```

意味は以下です。

- `git status`: 今どのファイルが変更されたか見る。
- `git branch`: 今どのブランチにいるか見る。
- `git diff`: 何を変更したか見る。

慣れるまでは、いきなり `git reset` や `git checkout --` は使わない方が安全です。変更が消える可能性があります。

### Step 1: Hello World を自分のプラグイン名に変える

現在の `main.py` はテンプレートに近い状態です。最初の作業は、プラグイン名とコマンド名を Research Note 用に変えることです。

目標は以下です。

```text
/research_hello
```

または

```text
/rn_hello
```

を送ると、Research Note から返事が来る状態にします。

ここで学ぶことは以下です。

- `@register(...)` の意味。
- `@filter.command(...)` の意味。
- `event.get_sender_name()` の使い方。
- `event.message_str` の使い方。
- `yield event.plain_result(...)` の使い方。

完成条件は以下です。

- AstrBot を起動できる。
- プラグインが読み込まれる。
- コマンドに返事がある。
- エラーが出てもログを読んで原因を探せる。

### Step 2: コマンドグループを作る

NotebookLM 風にするなら、コマンドは1つでは足りません。`/research` の下に複数の操作を作ると分かりやすいです。

目標コマンドは以下です。

```text
/research help
/research add <text>
/research list
/research ask <question>
/research clear
```

この段階では、中身はまだ簡単でよいです。

- `/research help`: 使い方を返す。
- `/research add`: 「保存したつもり」と返す。
- `/research list`: 「まだ資料はありません」と返す。
- `/research ask`: 「質問を受け取りました」と返す。
- `/research clear`: 「削除しました」と返す。

ここで学ぶことは以下です。

- `@filter.command_group("research")`
- `@research_group.command("add")`
- コマンド引数の受け取り方。
- 1つのプラグインに複数コマンドを書く方法。

完成条件は以下です。

- `/research help` が使える。
- `/research add テスト資料` が使える。
- `/research ask テスト質問` が使える。

### Step 3: JSON に資料を保存する

最初の保存先は JSON ファイルで十分です。データベースはまだ使いません。

保存する1件の資料は、たとえば以下の形にします。

```json
{
  "id": "note_001",
  "title": "任意タイトル",
  "content": "資料本文",
  "created_at": "2026-05-02T12:00:00"
}
```

最初はタイトルなしでもよいです。

```json
{
  "id": "note_001",
  "content": "資料本文",
  "created_at": "2026-05-02T12:00:00"
}
```

ここで学ぶことは以下です。

- Python の `json` モジュール。
- ファイルを読む。
- ファイルに書く。
- リストに辞書を追加する。
- 例外処理の基本。

保存ファイルの候補は以下です。

```text
data/research_notes.json
```

ただし AstrBot プラグインでは、最終的には AstrBot のデータディレクトリを使う方がよいです。最初は簡単さを優先して、プラグイン内の `data` ディレクトリでも構いません。

完成条件は以下です。

- `/research add テキスト` で JSON に保存される。
- `/research list` で保存済みの資料が見える。
- AstrBot を再起動しても資料が残る。

### Step 4: キーワード検索を作る

最初から embedding 検索に行くと難しくなります。まずは単純な検索で RAG の形を理解します。

最初の検索方法は以下で十分です。

- 質問を空白で分ける。
- 各資料に質問の単語が何個含まれるか数える。
- スコアが高い順に上位3件を返す。

例です。

```text
質問: Transformer attention とは？
資料A: Transformer と attention の説明がある。スコア2。
資料B: RNN の説明だけ。スコア0。
資料C: attention の説明がある。スコア1。
```

ここで学ぶことは以下です。

- 文字列検索。
- リストの並び替え。
- スコアリング。
- `top_k` の考え方。

完成条件は以下です。

- `/research ask 質問` で関連資料が選ばれる。
- 関連資料がないときに「資料が見つかりません」と返せる。
- 関連資料があるときに資料本文を表示できる。

### Step 5: 検索結果を LLM に渡す

ここで初めて NotebookLM 風になります。

やることは以下です。

- `/research ask <question>` を受け取る。
- JSON から資料を読む。
- キーワード検索で関連資料を選ぶ。
- 関連資料と質問をまとめたプロンプトを作る。
- `self.context.llm_generate(...)` で LLM に回答させる。
- 回答をユーザーに返す。

プロンプトの例です。

```text
あなたは研究補助AIです。
以下の資料だけを根拠にして、ユーザーの質問に日本語で答えてください。
資料に書かれていないことは、推測せず「資料からは分かりません」と答えてください。

[資料1]
...

[資料2]
...

質問:
...
```

ここで学ぶことは以下です。

- LLM に渡すプロンプトの作り方。
- RAG の最小構成。
- 「資料に基づいて答える」ための指示文。
- 回答の信頼性を上げる方法。

完成条件は以下です。

- 登録した資料に基づいて回答できる。
- 資料にない質問には、分からないと答えられる。
- どの資料を使ったか表示できる。

### Step 6: コードを分割する

最初は `main.py` だけで作ってもよいです。ただし、長くなりすぎたら分割します。

おすすめ構成です。

```text
astrbot_plugin_research_note/
  main.py
  metadata.yaml
  _conf_schema.json
  store.py
  search.py
  prompts.py
```

役割は以下です。

- `main.py`: AstrBot のコマンド、イベントフックを書く。
- `store.py`: JSON の読み書きを担当する。
- `search.py`: 資料検索を担当する。
- `prompts.py`: LLM に渡すプロンプトを作る。
- `_conf_schema.json`: 設定項目を定義する。

開発未経験の場合、最初から分割しすぎると分かりにくくなります。まずは `main.py` に作り、100行から200行を超えてつらくなったら分けます。

### Step 7: 設定ファイルを追加する

最小版が動いてから `_conf_schema.json` を追加します。

最初にあると便利な設定は以下です。

```json
{
  "top_k": {
    "description": "質問時に使う資料数",
    "type": "int",
    "default": 3,
    "minimum": 1,
    "maximum": 10
  },
  "max_note_chars": {
    "description": "1件の資料からプロンプトに入れる最大文字数",
    "type": "int",
    "default": 1200,
    "minimum": 100,
    "maximum": 10000
  },
  "strict_grounding": {
    "description": "資料にないことを推測しないよう強く指示する",
    "type": "bool",
    "default": true
  }
}
```

ここで学ぶことは以下です。

- 設定スキーマ。
- `AstrBotConfig`。
- `self.config.get("top_k", 3)` のような取得方法。

完成条件は以下です。

- WebUI で設定が見える。
- 設定を変えると検索件数などが変わる。

### Step 8: embedding 検索に進む

キーワード検索で動くものができたら、次に embedding 検索へ進みます。

embedding とは、文章を数字のベクトルに変換することです。意味が近い文章ほど、ベクトルも近くなります。

Mnemosyne で見る場所は以下です。

```text
main.py
core/memory_operations.py
```

見るポイントは以下です。

- `self.context.get_all_embedding_providers()`
- `embedding_provider.get_embedding(text)`
- `embedding_provider_id`
- `top_k`

最初はベクトルDBを使わず、JSON に embedding ベクトルも保存して、Python 側でコサイン類似度を計算してもよいです。

保存データの例です。

```json
{
  "id": "note_001",
  "content": "資料本文",
  "embedding": [0.01, -0.03, 0.22]
}
```

ここで学ぶことは以下です。

- embedding の意味。
- コサイン類似度。
- キーワード検索と意味検索の違い。
- embedding provider が未設定のときのエラー処理。

完成条件は以下です。

- `/research add` のときに embedding も保存する。
- `/research ask` のときに質問の embedding を作る。
- 類似度が高い資料を選べる。

### Step 9: Milvus Lite または別の保存方式を検討する

資料数が少ない間は JSON で十分です。100件から数千件になって、検索が遅い、保存が不安、ベクトル検索を本格化したい、となったら Milvus Lite などを検討します。

Mnemosyne は Milvus を使っていますが、最初に真似するには重いです。

Milvus に進む条件は以下です。

- JSON 保存版が安定して動いている。
- embedding 検索の意味が分かっている。
- 追加、検索、削除の流れを理解している。
- エラーが出たときにログを見られる。

Milvus に進むときに Mnemosyne で見る場所は以下です。

- `memory_manager/vector_db_base.py`
- `memory_manager/vector_db/milvus_manager.py`
- `core/initialization.py`
- `core/memory_operations.py`

### Step 10: NotebookLM らしい機能を足す

最小版が動いてから、以下の順番で追加します。

1. Markdown ファイル読み込み
2. テキストファイル読み込み
3. 長い資料の分割、チャンク化
4. 回答に根拠資料 ID を表示
5. PDF 読み込み
6. URL 読み込み
7. 複数資料セット、プロジェクト単位の管理
8. 要約生成
9. 比較表の生成
10. 研究メモの自動整理

特に重要なのはチャンク化です。長い資料を1件として保存すると、検索もプロンプトも弱くなります。長い資料は小さい段落に分けて保存します。

チャンクの例です。

```json
{
  "id": "note_001_chunk_003",
  "source_id": "note_001",
  "title": "論文A",
  "content": "第3段落の本文",
  "chunk_index": 3
}
```

## 最小版の仕様案

最初のバージョンはこれで十分です。

### コマンド

```text
/research help
/research add <content>
/research list
/research ask <question>
/research clear
```

### `/research help`

使い方を表示します。

表示例です。

```text
Research Note commands:
/research add <text> - 資料を追加
/research list - 資料一覧
/research ask <question> - 資料に基づいて質問
/research clear - 全資料を削除
```

### `/research add <content>`

資料を1件追加します。

最初はタイトルを別に取らなくてよいです。

表示例です。

```text
資料を保存しました: note_001
```

### `/research list`

保存済み資料を表示します。

表示例です。

```text
保存済み資料:
1. note_001: Transformer は...
2. note_002: Attention は...
```

### `/research ask <question>`

関連資料を検索し、LLM に回答させます。

表示例です。

```text
回答:
...

使用した資料:
- note_001
- note_002
```

### `/research clear`

全部削除します。

最初は確認なしでもよいですが、後で `--confirm` を追加した方が安全です。

```text
/research clear --confirm
```

## 最初に避けること

開発初期は以下を避けます。

- 最初から Web 管理画面を作る。
- 最初から Milvus を使う。
- 最初から PDF 読み込みを作る。
- 最初から完璧な引用機能を作る。
- 最初から非同期処理を複雑にする。
- 最初からファイルを細かく分けすぎる。
- 最初から全プラットフォーム対応を考える。

これらは後から追加できます。まずは「手で資料を追加して、質問に答える」だけを完成させます。

## エラーが出たときの見方

初心者のうちは、エラーの全文を読むのが一番大事です。

見るポイントは以下です。

- 一番下の行に何と書いてあるか。
- `File "...", line ...` がどのファイルを指しているか。
- `NameError`、`TypeError`、`ImportError`、`AttributeError` のどれか。

よくあるエラーです。

### `NameError`

変数名や関数名が定義されていません。

例です。

```text
NameError: name 'json' is not defined
```

原因は `import json` を忘れている可能性があります。

### `TypeError`

関数に渡す値の型や数が間違っています。

例です。

```text
TypeError: ask() missing 1 required positional argument
```

コマンド関数の引数が AstrBot の呼び出し方と合っていない可能性があります。

### `ImportError`

モジュールの読み込みに失敗しています。

例です。

```text
ImportError: cannot import name ...
```

import パスが間違っているか、必要なライブラリが入っていない可能性があります。

### `AttributeError`

存在しない属性やメソッドを呼んでいます。

例です。

```text
AttributeError: 'AstrMessageEvent' object has no attribute 'xxx'
```

AstrBot の event API を確認します。

## テストの考え方

最初は自動テストより、手動確認で十分です。

手動確認リストです。

- AstrBot が起動する。
- プラグイン読み込み時にエラーが出ない。
- `/research help` が返る。
- `/research add テスト資料` が成功する。
- `/research list` に追加した資料が出る。
- AstrBot を再起動しても資料が残る。
- `/research ask テスト質問` が関連資料を使って答える。
- 資料がないときのメッセージが分かりやすい。
- 空文字を追加しようとしたときにエラーにならない。

後で余裕が出たら、保存と検索だけ Python の単体テストにします。

## 学習順チェックリスト

### フェーズ1: AstrBot に慣れる

- `main.py` が入口だと分かる。
- `@register` の意味が分かる。
- `@filter.command` の意味が分かる。
- `event.plain_result` で返信できる。
- AstrBot を起動してプラグインを試せる。

### フェーズ2: コマンドを増やす

- コマンドグループを作れる。
- コマンド引数を受け取れる。
- help、add、list、ask、clear を作れる。

### フェーズ3: 保存する

- JSON を読める。
- JSON に書ける。
- 資料 ID を付けられる。
- 再起動後も資料が残る。

### フェーズ4: 検索する

- キーワード検索ができる。
- スコア順に並べられる。
- 上位 `top_k` 件を選べる。

### フェーズ5: LLM に渡す

- 関連資料をプロンプトに入れられる。
- `llm_generate` を使える。
- 資料にないことを推測しないよう指示できる。
- 使用資料を表示できる。

### フェーズ6: Mnemosyne から学ぶ

- `on_llm_request` の使い道が分かる。
- embedding provider の考え方が分かる。
- ベクトル検索の必要性が分かる。
- Milvus は後で使うものだと判断できる。

## 推奨する実装順

実際の実装は以下の順番が一番安全です。

各ステップの詳細版は以下に分けています。

- `docs/learning_steps/00_overview.md`: 全体像、作業の進め方、迷ったときの判断基準。
- `docs/learning_steps/01_hello_world.md`: テンプレートを Research Note 用に変える。
- `docs/learning_steps/02_command_group.md`: `/research help/add/list/ask/clear` の形を作る。
- `docs/learning_steps/03_json_storage.md`: JSON に資料を保存して再起動後も残す。
- `docs/learning_steps/04_keyword_search.md`: キーワード検索で関連資料を選ぶ。
- `docs/learning_steps/05_llm_answer.md`: 検索結果を LLM に渡して回答させる。
- `docs/learning_steps/06_config_and_safety.md`: 設定ファイル、入力チェック、削除確認を入れる。
- `docs/learning_steps/07_refactor.md`: `main.py` から保存、検索、プロンプトを分ける。
- `docs/learning_steps/08_embedding_next.md`: embedding 検索へ進む準備。

1. `main.py` の Hello World を Research Note 用に変える。
2. `/research help` を作る。
3. `/research add` を作る。ただし最初は保存せず返信だけ。
4. `/research list` を作る。ただし最初は固定文だけ。
5. JSON 保存を追加する。
6. `/research add` で JSON に保存する。
7. `/research list` で JSON から読む。
8. `/research clear` を作る。
9. キーワード検索関数を作る。
10. `/research ask` で検索結果だけ返す。
11. `/research ask` で LLM に回答させる。
12. 使用資料 ID を回答の下に出す。
13. `_conf_schema.json` を追加する。
14. `top_k` を設定化する。
15. 長い資料の切り詰めを入れる。
16. 余裕が出たら `store.py`、`search.py`、`prompts.py` に分ける。
17. embedding 検索へ進む。
18. PDF や Markdown 読み込みへ進む。

## 最初の完成定義

バージョン `v0.1.0` の完成定義は以下です。

- `/research help` が使える。
- `/research add <text>` で資料を保存できる。
- `/research list` で資料一覧を見られる。
- `/research ask <question>` で資料に基づく回答が返る。
- `/research clear --confirm` で資料を削除できる。
- 保存は JSON でよい。
- 検索はキーワード検索でよい。
- embedding と Milvus はまだ不要。

この状態まで行けば、NotebookLM 風プラグインの骨格は完成です。

## 次の完成定義

バージョン `v0.2.0` の完成定義は以下です。

- `_conf_schema.json` で `top_k` を設定できる。
- 長い資料を一定文字数で切り詰められる。
- 回答に使用資料 ID を表示できる。
- 空の資料や空の質問を安全に処理できる。
- 保存処理と検索処理が `main.py` から分離されている。

バージョン `v0.3.0` の完成定義は以下です。

- embedding provider を使える。
- 資料保存時に embedding を作れる。
- 質問時に embedding 検索できる。
- embedding provider がない場合はキーワード検索に戻れる。

## 学習メモ

開発では、一度に全部理解しようとしない方が進みます。おすすめは以下です。

- まず動かす。
- 次にログを見る。
- 次に小さく変更する。
- 変更したらすぐ試す。
- 動いたら Git で差分を見る。
- 分からないエラーは全文を残す。

Research Note の開発では、毎回この順番で考えると迷いにくいです。

```text
入力: ユーザーが何を送ったか
保存: どこに何を保存するか
検索: どの資料を選ぶか
プロンプト: LLM に何を渡すか
出力: ユーザーに何を返すか
```

この5つに分ければ、NotebookLM 風の機能も小さい部品として理解できます。
