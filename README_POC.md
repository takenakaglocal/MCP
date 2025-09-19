# Elasticsearch LLM PoC ガイド (Python 版)

## 目的
最短で「本番 Elastic クラスターに対し LLM (Copilot Agent) 経由で読み取り分析ができる」Python MCP サーバを構築する。

## ゴール (Day1)
1. 接続: health / cat indices 取得成功
2. LLM から自然言語→Query DSL 生成→検索実行
3. ES|QL (対応バージョン) 実行

## 手順概要
1. `.env` を作成し認証値投入 (コミット禁止)
2. Python 仮想環境作成 & 依存導入
3. VS Code 再読み込み (Copilot が `.vscode/mcp.json` を検出)
4. Copilot チャットで分析指示
5. 必要に応じてターミナルで JSON-RPC 手動検証

## 前提
- Python 3.11+ 推奨
- `pip`, `venv` 利用可能
- Elasticsearch 7.17+ / 8.x (ES|QL は 8.11+)

## .env 例 (値は本番発行情報に置換)
```
ES_ENDPOINT=https://your-prod-endpoint
ES_USERNAME=readonly_user
ES_PASSWORD=********
# もしくは (Basic の代わり)
# ES_API_KEY=***
ES_TLS_REJECT_UNAUTHORIZED=true
ES_MAX_SEARCH_SIZE=100
ES_REQUIRE_TIME_RANGE=true
ES_DEFAULT_LOOKBACK=now-15m
ES_ALLOWED_INDEX_PATTERNS=logs-*,metrics-*
```

## セットアップ
```
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## (A) 手動起動 & JSON-RPC 疎通テスト
### 1. 常駐起動
```
python mcp_elasticsearch.py
```
表示例:
```
{"jsonrpc":"2.0","method":"ready","params":{"ok":True}}
```

### 2. ワンショット initialize
```
echo '{"jsonrpc":"2.0","id":1,"method":"initialize"}' | python mcp_elasticsearch.py
```

### 3. ツール一覧
```
echo '{"jsonrpc":"2.0","id":2,"method":"list_tools"}' | python mcp_elasticsearch.py | jq .
```

### 4. health
```
echo '{"jsonrpc":"2.0","id":3,"method":"call_tool","params":{"name":"health"}}' | python mcp_elasticsearch.py | jq .
```

### 5. indices
```
echo '{"jsonrpc":"2.0","id":4,"method":"call_tool","params":{"name":"cat_indices"}}' | python mcp_elasticsearch.py | jq .
```

### 6. search サンプル
```
echo '{"jsonrpc":"2.0","id":5,"method":"call_tool","params":{"name":"search","arguments":{"index":"logs-*","body":{"size":5,"query":{"match_all":{}}}}}}' | python mcp_elasticsearch.py | jq .
```

### 7. ES|QL (対応バージョンのみ)
```
echo '{"jsonrpc":"2.0","id":6,"method":"call_tool","params":{"name":"esql","arguments":{"query":"FROM logs-* WHERE level == \"ERROR\" | STATS c = COUNT(*)"}}}' | python mcp_elasticsearch.py | jq .
```
`WHERE` 句や時間条件が無い場合は `ES_DEFAULT_LOOKBACK` が自動付与。

## (B) Copilot 連携フロー
以下は VS Code 上で Copilot (MCP 対応) から Elasticsearch 分析を実行する具体手順。

### 事前チェック (一度だけ)
1. 拡張機能: GitHub Copilot を最新化 (プレビュー機能で MCP/Tools が有効であること)。
2. `.vscode/mcp.json` が存在し、`command: "python"`, `args: ["mcp_elasticsearch.py"]` になっている。
3. `.env` に認証情報が設定されている (貼り付け厳禁: 値は漏洩させない)。
4. Python 仮想環境が有効化されている (必要なら VS Code 右下でインタプリタ選択)。
5. (任意) 手動テストで `python mcp_elasticsearch.py` を起動し `ready` 行が出ることを確認後 Ctrl+C で停止。

### 起動タイミング
- Copilot は VS Code ウィンドウ再読み込み時に `.vscode/mcp.json` を読み込み、サーバープロセスを自動起動する実装が想定。
- 自動起動に失敗する場合: 一度 `python mcp_elasticsearch.py` を手動起動し動くかを切り分け。

### ツール認識確認
Copilot チャットを開き、次のいずれかを送信:
```
利用可能なツール一覧を表示して
```
意図: 内部で `list_tools` 相当を呼ばせる。返答で `health`, `cat_indices`, `search`, `esql` の名前が言及されれば成功。

表示されない場合の確認ポイント:
- Output パネル -> GitHub Copilot / 拡張ログにエラーが無いか
- `mcp_elasticsearch.py` がファイルパス違いで呼ばれていない (mcp.json の args 確認)
- Python 仮想環境選択ミスで `elasticsearch` モジュール未インストール

### 初回ガードプロンプト (推奨)
最初に制約を明示して LLM に記憶させる:
```
以後の対話では Elasticsearch 読み取り専用ツール (health / cat_indices / search / esql) だけを使ってください。破壊的 API や書き込み操作は禁止です。size は最大 100。時間範囲未指定時は now-15m から now でお願いします。
```

### 直近10件取得 (例)
```
logs-* から直近15分で新しいドキュメントを @timestamp 降順に 10 件だけ取得し、@timestamp, level, message だけ表示して。
```
期待される内部動作: Copilot が `search` ツール呼出 -> size=10, sort desc, _source フィールド限定。本サーバは時間範囲欠如時に自動補完するため省略可。

### エラー時の再指示例
- Copilot が書き込み API を示唆: 
```
書き込み操作は不要です。search か esql のみで再生成してください。
```
- size が大き過ぎる: 
```
size を 50 以下にして再生成してください。
```

### 集計例 (Query DSL)
```
logs-* から過去 30 分の ERROR 件数を 5 分粒度で時系列集計し、バケットごとの件数を JSON で。
```

### 集計例 (ES|QL)
```
ES|QL で logs-* の直近 30 分 ERROR の件数を 5 分単位で集計して。
```
(8.11+ 前提。対応していなければ search での実装を促す)

### 結果要約例
```
上記時系列集計の増加が急だったタイムウィンドウを 2 箇所だけ抽出し、(開始時刻, 終了時刻, 件数増分) を列挙してください。
```

### 期待する Copilot 応答改善のコツ
| 目的 | 調整する指示要素 |
|------|------------------|
| フィールド限定 | "@timestamp, level, message だけ" |
| 負荷低減 | "size は最大 20" / "集計時は size=0" |
| 時間制御 | "過去 X 分" を明示 (自動補完任せない) |
| 形式指定 | "JSON で" / "表形式(テキスト)で" |

### トラブルシュート (Copilot 側)
| 症状 | 原因候補 | 対処 |
|------|----------|------|
| ツールを使わず説明だけ返す | コンテキスト不足 | 目的と利用可能ツールを再度明示 |
| search body が巨大 | 指示に制約 absent | プロンプトで size, _source を明示 |
| 時間範囲不正 (未来含む) | LLM 推論揺らぎ | 範囲を now-XXm to now と明記 |
| esql 失敗 | 旧バージョン / ES|QL 未有効 | search での代替を指示 |

### ログ確認
Copilot が内部で失敗した疑いがある場合:
1. Output パネル -> Copilot ログ
2. 必要なら `ES_VERBOSE=true python mcp_elasticsearch.py` を手動起動し標準エラー出力を観察

## 注意点 (Python 版特有)
| 項目 | 内容 |
|------|------|
| TLS | `ES_TLS_REJECT_UNAUTHORIZED=false` で検証無効 (本番禁止) |
| サイズ制限 | `ES_MAX_SEARCH_SIZE` で強制上限 |
| 時間範囲強制 | `ES_REQUIRE_TIME_RANGE=true` で `@timestamp` 未指定時に挿入 |
| インデックス制御 | `ES_ALLOWED_INDEX_PATTERNS` でワイルドカード許可制御 |
| ES|QL 禁止語 | DELETE/UPDATE/CREATE/DROP/PUT/POST を拒否 |

## 失敗時チェック
| 症状 | チェック | 例 |
|------|----------|----|
| 401 | 認証情報 | echo $ES_USERNAME |
| 403 | ロール不足 | read 権限確認 |
| SSL | チェーン | openssl s_client -connect host:443 -servername host -showcerts |
| タイムアウト | ネットワーク | curl -vk $ES_ENDPOINT/ |
| インデックス拒否 | パターン | 環境変数 `ES_ALLOWED_INDEX_PATTERNS` |

## 安全ガード
- 書き込み系 API 未実装
- size 上限 / 時間範囲自動
- インデックス allow-list
- ES|QL 禁止キーワード検査

## 次の拡張候補
- レート制限 / 監査ログ / 結果サマリ整形 / キャッシュ

---
短期 PoC 用メモ終わり
