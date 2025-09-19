#!/bin/bash
# Elasticsearch MCP ヘルパースクリプト

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRIPT_DIR/venv/bin/python"
MCP="$SCRIPT_DIR/mcp_elasticsearch.py"

# 関数定義
es_health() {
    echo '{"jsonrpc":"2.0","id":"1","method":"call_tool","params":{"name":"health","arguments":{}}}' | $PYTHON $MCP
}

es_indices() {
    echo '{"jsonrpc":"2.0","id":"1","method":"call_tool","params":{"name":"cat_indices","arguments":{}}}' | $PYTHON $MCP
}

es_search() {
    local index=${1:-"logs-*"}
    local size=${2:-5}
    echo "{\"jsonrpc\":\"2.0\",\"id\":\"1\",\"method\":\"call_tool\",\"params\":{\"name\":\"search\",\"arguments\":{\"index\":\"$index\",\"body\":{\"size\":$size,\"sort\":[{\"@timestamp\":{\"order\":\"desc\"}}]}}}}" | $PYTHON $MCP
}

es_errors() {
    local index=${1:-"logs-*"}
    echo "{\"jsonrpc\":\"2.0\",\"id\":\"1\",\"method\":\"call_tool\",\"params\":{\"name\":\"search\",\"arguments\":{\"index\":\"$index\",\"body\":{\"size\":0,\"track_total_hits\":true,\"query\":{\"term\":{\"level\":\"ERROR\"}},\"aggs\":{\"first_ts\":{\"min\":{\"field\":\"@timestamp\"}},\"last_ts\":{\"max\":{\"field\":\"@timestamp\"}}}}}}}" | $PYTHON $MCP
}

# 使用方法表示
echo "Elasticsearch MCP Helper"
echo "使用可能コマンド:"
echo "  es_health      - クラスタ状態"
echo "  es_indices     - インデックス一覧"
echo "  es_search      - 最新ログ検索 (例: es_search logs-* 10)"
echo "  es_errors      - エラー集計"