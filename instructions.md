# instructions.md

## motivate
Elasticsearch の検索・分析能力を LLM (GitHub Copilot Agent + MCP) と統合することで、従来の手動 DSL / ES|QL 作成を自然言語プロンプトで高速化し、探索的データ分析の反復速度と認知効率を向上させる。複雑な bool クエリや集計を都度記述する負担を軽減し、観点切り替えを高速に行える。

## premise
- 対象は既存の Elasticsearch クラスター（Elastic Cloud / オンプレ いずれも可）
- 認証は Basic 認証（ユーザー名 + パスワード）をデフォルト、代替として API Key 方式を選択可能
- 操作は読み取り専用（search / monitor 権限）に限定
- VS Code + GitHub Copilot (MCP 対応版) を利用
- 破壊的操作（ドキュメント更新/削除、インデックス作成・削除、テンプレ変更等）は対象外

## purpose
本書のみを参照して安全にセットアップし、自然言語から Elasticsearch の検索/簡易分析（Query DSL / ES|QL）を行える状態に到達させる。

## situation
- 例: ログ / メトリクス / イベントデータのアドホック調査
- 分析担当者が LLM に「直近24時間のエラーレートを時系列集計」などを自然言語で指示→ LLM が検索クエリ生成→ MCP 経由で Elasticsearch をクエリ実行→ 結果を要約

## 背景とゴール
| 項目 | 内容 |
|------|------|
| 背景 | 手動での Query DSL 作成は学習コスト・記述コストが高い |
| 課題 | クエリ表現の複雑化 / 素早い仮説検証の阻害 |
| ゴール | 1) 安全な認証管理 2) 読み取り限定 MCP 接続 3) 動作確認 4) LLM プロンプト指針 5) 代表的クエリ例参照 |

## 前提条件
- VS Code 最新版
- GitHub Copilot (MCP 対応拡張) 有効
- ネットワークから Elasticsearch エンドポイント (例: `https://example.es.amazonaws.com` または Elastic Cloud 提供 URL) に到達可能
- Python 3.11 以上（MCP サーバは Python 実装に統一）
- Elasticsearch バージョン: 7.17+ および 8.x を想定（API Key は両系統で利用可能。ただし 8.x ではセキュリティ有効化標準化）
- 権限: 最小ロール (cluster: monitor 系 / indices: read, view_index_metadata) のみ

## セキュリティ方針
⚠️ 認証情報はリポジトリにコミットしない。
- `.env` に格納し `.gitignore` で除外
- 代替: VS Code User Settings の secret storage / environment injection
- 最小権限原則: 読み取りロールのみ
- API Key 利用時は定期ローテーション（失効日時設定推奨）
- HTTPS 利用必須 / 証明書検証無効化は一時的例外措置として明示的に警告
- LLM プロンプト内に秘密値を貼り付けない

## セットアップ手順
### 1. リポジトリ初期化（必要な場合）
```
# 例 (必要時)
git init
```

### 2. `.gitignore` に `.env` を含める
```
echo ".env" >> .gitignore
```

### 3. `.env.example` 作成（キー名のみ、値は書かない）
付録参照。

### 4. `.env` 実ファイルをローカル作成
```
ES_ENDPOINT=https://<your-endpoint>
ES_USERNAME=<your-username>
ES_PASSWORD=<your-password>
# 代替方式を使う場合は上記2行をコメントアウトし ES_API_KEY を使用
# ES_API_KEY=<base64 or key string>
ES_TLS_REJECT_UNAUTHORIZED=true
```
(値はコミット禁止)

### 5. VS Code Settings (一部) で環境参照（任意）
`settings.json` に MCP 拡張が参照する環境マッピングを記述可能（付録参照）。

### 6. MCP サーバ設定ファイル
`.vscode/mcp.json` に Elasticsearch ツールエントリを定義（例は付録）。環境変数経由で認証情報を取得。Basic / API Key の選択をロジック側で分岐。

### 7. GitHub Copilot Agent への指示例
```
Elasticsearch クラスターに接続して "logs-*" から直近15分の error レベル件数を集計し、1分粒度で表示してください。破壊的操作は禁止です。
```

### 8. 権限検証クエリ
1. `_cluster/health`
2. `_cat/indices?format=json&bytes=b`
3. サンプル search: 対象インデックス1件に対し `size: 1`

### 9. ES|QL / Query DSL 確認
Elasticsearch 8.11+ で ES|QL 安定版。バージョンにより `/_query` エンドポイント差異あり。使用前にバージョン確認推奨。

## Basic認証（デフォルト）
必要変数: `ES_ENDPOINT`, `ES_USERNAME`, `ES_PASSWORD`

### curl 疎通
```
curl -u "$ES_USERNAME:$ES_PASSWORD" \
  -H 'Accept: application/json' \
  "$ES_ENDPOINT" -s | jq '.tagline?'
```

### 証明書チェーン確認
```
openssl s_client -connect <host>:443 -servername <host> -showcerts </dev/null
```

### MCP 側動作（想定ロジック）
1. `ES_API_KEY` が未設定で `ES_USERNAME`/`ES_PASSWORD` が存在 → Basic Authorization ヘッダ生成
2. `ES_TLS_REJECT_UNAUTHORIZED=false` の場合のみ証明書検証回避（⚠️ 本番禁止）

## API Key（代替）
必要変数: `ES_ENDPOINT`, `ES_API_KEY`

### 前提
管理者が Kibana か API で read-only 権限を付与した API Key を発行。`id:api_key` を base64 した複合ではなく、Elasticsearch 8.x 以降は標準出力された統一キー文字列を `Authorization: ApiKey <key>` で送信。

### curl 疎通
```
curl -H "Authorization: ApiKey $ES_API_KEY" \
  -H 'Accept: application/json' "$ES_ENDPOINT/_cluster/health?pretty"
```

### Basic との違い
- ローテーション容易
- 失効日付 (expiration) を設定可能
- 1つのキーに権限境界を限定しやすい

## 動作確認
| ステップ | コマンド / 操作 | 期待結果 |
|----------|-----------------|----------|
| 1 | `_cluster/health` | status (green/yellow) JSON |
| 2 | `_cat/indices?format=json` | インデックス一覧 JSON |
| 3 | Search size=0 集計 | 集計結果が返る |
| 4 | ES|QL STATS | 統計列が返る |

失敗時: HTTP ステータス / `error.type` を記録しトラブルシューティング章参照。

## 運用Tips（自然言語→ES|QL 例など）
### プロンプトテンプレ（破壊的操作防止）
```
以下のガードを厳守して Elasticsearch 検索クエリ (Query DSL または ES|QL) を生成:
- 読み取り専用: search, _cluster/health, cat APIs のみ
- 禁止: delete, update, index, ingest, reindex, snapshot, tasks/_cancel
- レスポンス最適化: size <= 100, _source フィールドは必要最小限
出力: 1) 選択API種別 2) 生成クエリ JSON/ES|QL 3) 簡潔説明
```

### Query DSL / ES|QL 選択指針
| 用途 | 推奨 | 理由 |
|------|------|------|
| 単純フィルタ + 集計 | ES|QL | 簡潔、パイプライク表現 |
| 複雑なネスト bool 条件 | Query DSL | 柔軟性高い |
| 特殊スコアリング | Query DSL | score 操作可能 |
| 簡易サンプリング | ES|QL SAMPLE | 記述短い |

### 負荷最適化
- `track_total_hits`: 大規模インデックスで正確件数不要時 `false` / 部分数値
- `_source` フィルタ (`_source": ["fieldA","fieldB"]`)
- 集計使用時 `size: 0`
- 過去短期間に限定 (`range` で now-15m/now)

### 例: 自然言語 → Query DSL
要望: "logs-* から過去1時間の level=ERROR の件数を 5分毎に" → Date Histogram + Filter Aggregation。

## トラブルシューティング
| 症状 | 原因候補 | 対処 |
|------|----------|------|
| 401 Unauthorized | 資格情報誤り / API Key 失効 / 時刻ずれ | 値再確認 / 新規キー発行 / NTP 同期 |
| 403 Forbidden | ロール不足 (indices:read 欠如) | 管理者にロール追加依頼 |
| 証明書エラー (SELF_SIGNED) | 社内 CA / MITM Proxy | CA ルート証明書を信頼ストアへ追加 |
| 証明書 unknown CA | 中間証明書欠落 | 完全チェーン導入 / trust store 追加 |
| タイムアウト | Firewall / ネットワーク遅延 | ポート開放 (443/9200) / 再試行 / region 近接化 |
| インデックスが出ない | パターン不整合 / 権限不足 | `GET _cat/indices` で名称確認 / role 修正 |
| LLM が破壊的 API 提案 | プロンプトガード不足 | ガードテンプレ追加 / 生成後フィルタ |
| プロキシ越し失敗 | 環境変数未設定 | `HTTPS_PROXY`/`NO_PROXY` 設定 |
| API Key 生成不可 | 権限不足 | 管理者に key:manage 権限依頼 |

### 証明書検証回避 (最終手段)
⚠️ 開発検証以外で `ES_TLS_REJECT_UNAUTHORIZED=false` を使用しない。恒久対応: 正しい証明書チェーン整備。

## 付録
### A. .env.example
```
# Elasticsearch 基本 (Basic 認証)
ES_ENDPOINT=
ES_USERNAME=
ES_PASSWORD=

# 代替 (API Key 認証)
ES_API_KEY=

# TLS 設定
ES_TLS_REJECT_UNAUTHORIZED=
```

### B. .vscode/mcp.json 例
```json
{
  "servers": {
    "elasticsearch": {
      "command": "python",
      "args": ["mcp_elasticsearch.py"],
      "env": {
        "ES_ENDPOINT": "${env:ES_ENDPOINT}",
        "ES_USERNAME": "${env:ES_USERNAME}",
        "ES_PASSWORD": "${env:ES_PASSWORD}",
        "ES_API_KEY": "${env:ES_API_KEY}",
        "ES_TLS_REJECT_UNAUTHORIZED": "${env:ES_TLS_REJECT_UNAUTHORIZED}",
        "ES_MAX_SEARCH_SIZE": "${env:ES_MAX_SEARCH_SIZE}",
        "ES_REQUIRE_TIME_RANGE": "${env:ES_REQUIRE_TIME_RANGE}",
        "ES_DEFAULT_LOOKBACK": "${env:ES_DEFAULT_LOOKBACK}",
        "ES_ALLOWED_INDEX_PATTERNS": "${env:ES_ALLOWED_INDEX_PATTERNS}",
        "ES_VERBOSE": "${env:ES_VERBOSE}"
      }
    }
  }
}
```

### C. settings.json 断片
```jsonc
{
  "mcp.elasticsearch.timeoutMs": 15000,
  "mcp.elasticsearch.safeMode": true,
  // 環境変数は OS 側 / .env から読み取り。secretStorage 利用時は拡張ガイド参照。
}
```

### D. Query DSL 例集
#### 1. シンプル検索 (最新1件)
```json
POST logs-*/_search
{
  "size": 1,
  "sort": [{ "@timestamp": "desc" }],
  "query": { "match_all": {} }
}
```
#### 2. エラーカウント (過去15分)
```json
POST logs-*/_search
{
  "size": 0,
  "query": {
    "bool": {
      "filter": [
        { "term": { "level": "ERROR" }},
        { "range": { "@timestamp": { "gte": "now-15m" }}}
      ]
    }
  },
  "aggs": {
    "by_minute": {
      "date_histogram": {
        "field": "@timestamp",
        "fixed_interval": "1m"
      }
    }
  }
}
```
#### 3. 集計 + 平均
```json
POST metrics-*/_search
{
  "size": 0,
  "query": { "range": { "@timestamp": { "gte": "now-1h" }}},
  "aggs": {
    "per_service": {
      "terms": { "field": "service.keyword", "size": 10 },
      "aggs": {
        "avg_latency": { "avg": { "field": "latency_ms" }}
      }
    }
  }
}
```

### E. ES|QL 例
```text
FROM logs-* WHERE @timestamp >= NOW() - 15 MINUTES AND level == "ERROR" | STATS error_count = COUNT(*)
```
```text
FROM metrics-* WHERE @timestamp >= NOW() - 1 HOUR
| STATS avg_latency = AVG(latency_ms) BY service
| SORT avg_latency DESC
| LIMIT 10
```
```text
FROM logs-* SAMPLE 50 | WHERE level IN ("WARN", "ERROR") | KEEP @timestamp, level, message
```

### F. curl テンプレ
```bash
# Basic
curl -u "$ES_USERNAME:$ES_PASSWORD" -H 'Accept: application/json' "$ES_ENDPOINT/_cluster/health?pretty"
# API Key
curl -H "Authorization: ApiKey $ES_API_KEY" -H 'Accept: application/json' "$ES_ENDPOINT/_cluster/health?pretty"
```

### G. 最小ロール例 (概念)
```
cluster: ["monitor"]
indices:
  - names: ["logs-*", "metrics-*"]
    privileges: ["read", "view_index_metadata"]
```

### H. LLM プロンプト テンプレ
```
あなたは Elasticsearch 読み取り専用アシスタントです。禁止: 破壊的 API (update/delete/index/reindex/snapshot 等)。
ユーザー要望を Query DSL または ES|QL へ変換し、次形式で出力:
1) api_type: search | esql
2) query: <クエリ本文>
3) rationale: <簡潔理由>
制約: size <= 100, 時間範囲指定が無い場合は now-15m から now。
```

## 注意事項 / 免責
- 本書は読み取り専用ワークフロー向け。構成変更や書込み操作は組織ポリシーとレビュー手順に従うこと。
- 証明書検証無効化は恒久策ではない。

## 今後の拡張案
- OpenSearch 互換: 多くの Query DSL 部分互換 (ES|QL 非対応バージョンあり)
- Embedding / kNN 検索拡張 (読み取り用途で vector フィールド活用)
- キャッシュヒット率観測 / `_stats` 取得による分析高速化
- Python サーバのレート制限 / 監査ログ / 結果整形強化

---
以上。
