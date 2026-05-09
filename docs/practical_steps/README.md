# Practical Steps Index

このディレクトリは、`PRACTICAL_ROADMAP.md` をさらに具体化した実用化フェーズ別ガイドです。

`docs/learning_steps` の次に読む想定です。最初の8ステップで「小さく動く Research Note」を作り、この practical steps で「壊れにくく、資料が増えても使える Research Note」に育てます。

## 読む順番

0. `architecture_overview.md`: Research Note を中心にしたアプリ全体の構造図。
1. `01_foundation_quality.md`: 実用品質の土台作り。
2. `02_documents_and_chunks.md`: Document と Chunk への移行。
3. `03_hybrid_search_and_citation.md`: Embedding Search と Citation。
4. `04_research_tools.md`: Research Note を LLM tool 化する。
5. `05_agent_mode.md`: `/research agent` を作る。
6. `06_import.md`: URL や text import を作る。
7. `07_web_research.md`: AstrBot Web Search と連携する。
8. `08_mcp.md`: MCP tool と安全に連携する。
9. `09_multi_agent.md`: 研究作業を Multi-Agent 化する。
10. `10_research_outputs.md`: brief、outline、compare、claims を作る。
11. `11_storage_backend.md`: 保存 backend を強くする。
12. `12_quality_evaluation.md`: 検索と回答品質を評価する。

## 進め方

- Phase 1 から順番に進める。
- 1つの Phase で複数の小さな commit に分けてもよい。
- 各 Phase の最後に手動確認コマンドを実行する。
- 仕様が迷ったら、より小さい実装を選ぶ。
- MCP、Web Search、Multi-Agent は後半まで待つ。

## なぜ順番が大事か

研究補助プラグインで一番大事なのは「根拠を失わないこと」です。

外部検索、MCP、Multi-Agent を先に入れると、機能は派手になります。しかし、資料を chunk に分ける仕組みや citation が弱いままだと、どの情報に基づいた回答なのか分からなくなります。

そのため、最初は地味でも以下を先に固めます。

- 保存が壊れにくい。
- 長文を chunk に分けられる。
- 検索結果に source がある。
- 回答が source を示せる。
- LLM が資料にないことを勝手に言いにくい。

## 各 Phase の読み方

各ファイルでは、以下の順番で説明します。

- 目的: この Phase で何を良くするか。
- まだ早い場合: 先に戻るべき条件。
- 変更するファイル: 触る可能性が高い場所。
- 実装の順番: 小さく安全に進める手順。
- 動作確認: AstrBot 上で試すコマンド。
- よくある失敗: エラーになりやすい点。
- 完了条件: 次へ進んでよい判断基準。

コードを全部暗記する必要はありません。大事なのは、各 Phase で「何を入力として受け取り、何を保存し、何を返すのか」を説明できるようになることです。
