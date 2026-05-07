# 07 Web Research: AstrBot Web Search と連携する

この Phase では、保存済み資料だけでは足りない場合に Web Search を使えるようにします。

ただし、Web Search は便利ですが、研究補助では危険もあります。外部情報を勝手に保存したり、保存済み資料と混ぜて回答したりしないようにします。

## 目的

この Phase の目的は以下です。

- `enable_web_research` 設定を追加する。
- Web Search tool の allowlist を作る。
- `/research agent` で Web Search tool を使える mode を作る。
- Web検索結果は候補として返す。
- 保存する場合はユーザー確認を挟む。
- 回答で保存済み資料と Web検索結果を区別する。

## まだ早い場合

以下が未完成なら Phase 6 以前に戻ります。

- `/research agent` が Research Note tool だけで動く。
- import preview と confirm がある。
- source_type が保存される。
- citation が出る。

## 使える可能性がある AstrBot 組み込み tool

AstrBot 本体には Web Search 系 tool があります。

```text
web_search_baidu
web_search_tavily
tavily_extract_web_page
web_search_bocha
web_search_brave
web_search_firecrawl
firecrawl_extract_web_page
```

環境によって API key や provider 設定が必要です。Research Note の必須機能にしない方が安全です。

## 変更するファイル

```text
main.py
_conf_schema.json
```

必要なら追加します。

```text
tool_selectors.py
web_results.py
```

## Step 1: 設定を追加する

Web Research は default off にします。

```json
"enable_web_research": {
  "description": "research agent で Web Search tool を使う",
  "type": "bool",
  "default": false
},
"allowed_web_tools": {
  "description": "research agent に渡す Web Search tool 名",
  "type": "list",
  "items": {"type": "string"},
  "default": []
}
```

default off にする理由です。

- API key がない環境で失敗しない。
- 外部アクセスを勝手にしない。
- 保存済み資料だけで答えたい用途を守る。

## Step 2: allowlist から tool を取得する

AstrBot の tool manager から tool を取得します。

考え方です。

```text
context.get_llm_tool_manager() を取得
allowed_web_tools の名前を順に見る
存在する tool だけ ToolSet に入れる
存在しない tool は log に出す
```

tool はすべて渡さないでください。allowlist にあるものだけ渡します。

## Step 3: /research agent の mode を分ける

最初は明示的に Web を使う command にします。

候補です。

```text
/research agent_web <task>
```

または設定で有効なときだけ `/research agent` に追加します。

初心者には `agent_web` の方が分かりやすいです。

```text
/research agent: 保存済み資料だけ
/research agent_web: 保存済み資料 + Web Search
```

## Step 4: Web 用 system prompt を作る

保存済み資料と Web検索結果を区別させます。

例です。

```text
まず保存済み資料を research_search で確認してください。
保存済み資料だけでは不足する場合のみ Web Search tool を使ってください。
Web Search の結果は外部情報として扱い、保存済み資料とは区別してください。
Web の情報を Research Note に保存する場合は、ユーザー確認が必要です。
```

## Step 5: Web結果をすぐ保存しない

Web検索結果は候補として返します。

返答例です。

```text
保存済み資料から分かること:
...

Web検索で見つかった候補:
1. title...
   url: ...
   summary: ...

保存するには:
/research import url <url>
```

自動保存しない理由です。

- 検索結果が間違っている可能性がある。
- 広告や低品質ページが混ざる。
- ユーザーが保存する資料を選ぶべき。

## Step 6: save-web-result は後で作る

最初は `/research import url <url>` に誘導すれば十分です。

後で、検索結果に ID を付けて保存する機能を作れます。

```text
/research save-web-result web_001 --confirm
```

ただし、これは pending import と似ているため、Phase 6 の仕組みを再利用します。

## 動作確認

設定で Web Research を有効にし、使える tool 名を入れます。

例です。

```text
allowed_web_tools: ["web_search_tavily"]
```

試すコマンドです。

```text
/research agent_web 保存済み資料にない最新情報を調べて候補を出して
```

期待することです。

- まず Research Note を検索する。
- 足りない場合だけ Web Search を使う。
- Web 結果を保存済み資料と区別して表示する。
- 勝手に保存しない。

## よくある失敗

### Web tool が見つからない

AstrBot 側で Web Search provider が設定されているか確認します。tool 名が正しいかも確認します。

### API key エラーが出る

Research Note の問題ではなく、AstrBot provider 設定の問題です。ユーザー向けには短く表示し、詳細は log に残します。

### agent が保存済み資料を見ずに Web へ行く

system prompt を強くします。`まず research_search` と明記します。

### Web情報と保存済み資料が混ざる

回答 format を分けます。

```text
Saved Sources:
Web Candidates:
```

## この Phase の完了条件

- Web Research が default off になっている。
- allowlist の Web tool だけ渡す。
- `/research agent` と Web 使用 mode が分かれている。
- Web結果を勝手に保存しない。
- 保存済み資料と Web情報が回答上で区別される。
