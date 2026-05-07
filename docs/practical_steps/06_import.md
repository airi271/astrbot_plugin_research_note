# 06 Import: URL や Text を資料として取り込む

この Phase では、手で `/research add <text>` に貼るだけでなく、URL やタイトル付き text を資料として取り込めるようにします。

研究補助として実用にするには、資料登録の手間を減らすことが重要です。

## 目的

この Phase の目的は以下です。

- `/research import text` を作る。
- `/research import url` を作る。
- title、source_type、source_uri を保存する。
- import 前に preview を出す。
- 保存確認を挟む。
- 壊れた URL や長すぎる本文で安全に失敗する。

## まだ早い場合

以下が未完成なら Phase 5 以前に戻ります。

- Document と Chunk がある。
- `source_type` と `source_uri` を保存できる。
- chunk 分割ができる。
- `/research show <doc_id>` で metadata を見られる。

## 変更するファイル

```text
main.py
store.py
chunking.py
_conf_schema.json
```

新しく作る候補です。

```text
importers/__init__.py
importers/text_importer.py
importers/url_importer.py
```

## Step 1: import command group を作る

`/research import` の下に command を作ります。

```text
/research import text <title> <content>
/research import url <url>
```

AstrBot の command parser で複雑な引数が扱いにくい場合は、最初は単純な形にします。

```text
/research import_url <url>
/research import_text <content>
```

実用上きれいな command 名より、確実に動くことを優先します。

## Step 2: text import を作る

`/research add` と似ていますが、title や tag を扱いやすくします。

最初の仕様です。

```text
/research import text <content>
```

title は本文の先頭から自動生成します。

```text
title = content の先頭30文字
```

次に余裕があれば title 指定を追加します。

```text
/research import text --title Transformer memo <content>
```

## Step 3: URL import の最小版を作る

最初は `aiohttp` で HTML を取得します。

流れです。

```text
URL を受け取る
http/https か確認する
aiohttp で取得する
HTML から title を取る
HTML タグを簡単に除去して text にする
長すぎる場合は上限で切る
preview を返す
```

最初の HTML 抽出は完璧でなくてよいです。

注意です。

- JavaScript が必要なページはうまく取れない。
- PDF はまだ対象外でよい。
- 論文サイトは抽出が難しい場合がある。

## Step 4: import preview を作る

URL を取得したら、いきなり保存しない方が安全です。

返答例です。

```text
Import preview
title: Example Paper
source: https://example.com/paper
chars: 5230
chunks: 7

preview:
This paper introduces...

保存するには以下を実行してください:
/research import confirm import_abc123
```

preview のために一時保存が必要です。

最初は簡単に、plugin data 内に `pending_imports.json` を作ってもよいです。

## Step 5: confirm で保存する

`/research import confirm <pending_id>` で保存します。

流れです。

```text
pending import を読む
Document を作る
Chunk に分割する
embedding を作る
保存する
pending import を削除する
```

confirm を挟む理由です。

- Webページ抽出が失敗して変な本文になることがある。
- 長すぎるページを勝手に保存しない。
- ユーザーが source を確認できる。

## Step 6: 設定を追加する

追加候補です。

```json
"max_import_chars": {
  "description": "import で取り込む本文の最大文字数",
  "type": "int",
  "default": 50000,
  "minimum": 1000,
  "maximum": 500000
},
"import_preview_chars": {
  "description": "import preview に表示する文字数",
  "type": "int",
  "default": 800,
  "minimum": 100,
  "maximum": 3000
}
```

## Step 7: source_type を分ける

import 方法によって `source_type` を変えます。

```text
手入力: text
URL: url
Web検索結果: web
ファイル: file
agent が作ったメモ: agent_note
```

これにより、回答時に「保存済み資料」と「外部情報」を区別しやすくなります。

## 動作確認

text import です。

```text
/research import text Transformer は attention を使うモデルです。
/research list
/research show doc_001
```

URL import です。

```text
/research import url https://example.com
/research import confirm import_xxxx
/research list
/research ask example.com の内容は？
```

期待することです。

- preview が出る。
- confirm するまで保存されない。
- 保存後に title と source_uri が見える。
- chunk 化される。

## よくある失敗

### URL の本文が navigation だらけになる

HTML 抽出は難しいです。最初は許容し、後で Firecrawl や MCP browser に任せます。

### PDF が読めない

この Phase では対象外でよいです。PDF は file import または MCP 連携で扱います。

### pending import が残り続ける

created_at を保存し、古い pending を消す cleanup を後で追加します。

### 文字化けする

HTTP response の charset を確認します。まずは UTF-8 前提で失敗時にメッセージを返せば十分です。

## この Phase の完了条件

- `/research import text` が使える。
- `/research import url` が preview を返す。
- `/research import confirm <id>` で保存できる。
- import した資料に title、source_type、source_uri が入る。
- import 後に chunk 化される。
- 壊れた URL で安全に失敗する。
