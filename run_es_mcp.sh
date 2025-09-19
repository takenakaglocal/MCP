#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

log() { echo "[mcp-es][$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2; }
: "${ES_MCP_DEBUG:=false}"

# Python 決定
if [ -x "venv/bin/python" ]; then
  PY_BIN="venv/bin/python"
else
  PY_BIN="$(command -v python3 || true)"
  if [ -z "$PY_BIN" ]; then
    log "python3 が見つかりません"; exit 127
  fi
  log "venv/bin/python が無いので fallback: $PY_BIN"
fi

# .env ロード
if [ -f .env ]; then
  while IFS= read -r line; do
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    if [[ "$line" =~ ^[A-Z0-9_]+=.* ]]; then
      export "$line"
      [ "$ES_MCP_DEBUG" = "true" ] && log "export $line"
    fi
  done < .env
else
  log ".env 見つからず (続行)"
fi

# デフォルト補完
: "${ES_MAX_SEARCH_SIZE:=100}"
: "${ES_REQUIRE_TIME_RANGE:=true}"
: "${ES_DEFAULT_LOOKBACK:=now-15m}"
: "${ES_ALLOWED_INDEX_PATTERNS:=logs-*}"
: "${ES_VERBOSE:=false}"

# 依存チェック
if ! "$PY_BIN" - <<'PY'
try:
    import elasticsearch  # noqa
except Exception as e:
    raise SystemExit(1)
PY
then
  log "elasticsearch 未インストール。pip で導入試行。"
  "$PY_BIN" -m pip install --quiet elasticsearch python-dotenv || { log "pip install 失敗"; exit 1; }
fi

log "Starting mcp_elasticsearch.py with $PY_BIN"
exec "$PY_BIN" mcp_elasticsearch.py
