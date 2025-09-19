#!/usr/bin/env python
import os, sys, json, re, traceback
from typing import Any, Dict
from elasticsearch import Elasticsearch
from dotenv import load_dotenv
from pathlib import Path

# 確実に .env を読み込む (カレントディレクトリに依存しない)
_script_dir = Path(__file__).resolve().parent
_env_file = _script_dir / '.env'
if _env_file.exists():
    load_dotenv(dotenv_path=_env_file)
else:
    load_dotenv()  # フォールバック

ENDPOINT = os.getenv("ES_ENDPOINT", "").rstrip("/")
USERNAME = os.getenv("ES_USERNAME")
PASSWORD = os.getenv("ES_PASSWORD")
API_KEY  = os.getenv("ES_API_KEY")
VERIFY_TLS = os.getenv("ES_TLS_REJECT_UNAUTHORIZED", "true").lower() == "true"
_raw_max_size = os.getenv("ES_MAX_SEARCH_SIZE", "").strip()
MAX_SIZE = int(_raw_max_size) if _raw_max_size.isdigit() else 100
REQUIRE_TIME_RANGE = os.getenv("ES_REQUIRE_TIME_RANGE", "true").lower() == "true"
DEFAULT_LOOKBACK = os.getenv("ES_DEFAULT_LOOKBACK", "now-15m")
ALLOWED_PATTERNS = [p.strip() for p in os.getenv("ES_ALLOWED_INDEX_PATTERNS", "*").split(",")]
VERBOSE = os.getenv("ES_VERBOSE", "false").lower() == "true"

# 複数インデックス設定
INDICES = {
    'default': os.getenv("ES_INDEX", "bunsyo_local_iinkaigijiroku_v0.0.1"),
    'keikakuhoshin': os.getenv("ES_INDEX_keikakuhoshin", "bunsyo_local_keikakuhoshin_v0.0.1"),
    'kouhou': os.getenv("ES_INDEX_kouhou", "bunsyo_local_kouhou_v0.0.1"),
    'yosankessan': os.getenv("ES_INDEX_yosankessan", "bunsyo_local_yosankessan_v0.0.1")
}
FORBIDDEN_ESQL = re.compile(r"\b(DELETE|UPDATE|CREATE|DROP|PUT|POST)\b", re.IGNORECASE)
TIME_FIELD_CANDIDATES = ["@timestamp","timestamp","event.ingested"]

def v(msg: str):
    if VERBOSE: print(f"[debug] {msg}", file=sys.stderr)

def resolve_index(index_arg: str) -> str:
    """インデックス引数を実際のインデックス名に解決"""
    if not index_arg:
        return INDICES['default']

    # キー名で指定された場合
    if index_arg in INDICES:
        return INDICES[index_arg]

    # カンマ区切りのキー名で指定された場合（横断検索）
    if ',' in index_arg:
        resolved_indices = []
        for key in index_arg.split(','):
            key = key.strip()
            if key in INDICES:
                resolved_indices.append(INDICES[key])
            elif key == 'all':
                # 全インデックス
                resolved_indices.extend(INDICES.values())
            else:
                # 直接インデックス名として扱う
                resolved_indices.append(key)
        return ','.join(resolved_indices)

    # 'all'で全インデックス指定
    if index_arg == 'all':
        return ','.join(INDICES.values())

    # 直接インデックス名として扱う
    return index_arg

def match_allowed(index: str) -> bool:
    if ALLOWED_PATTERNS == ["*"]: return True
    for pat in ALLOWED_PATTERNS:
        regex = "^" + re.escape(pat).replace("\\*", ".*") + "$"
        if re.match(regex, index): return True
    return False

def build_client() -> Elasticsearch:
    if not ENDPOINT: raise RuntimeError("ES_ENDPOINT missing")
    kwargs = {"hosts": [ENDPOINT], "verify_certs": VERIFY_TLS}
    if API_KEY: kwargs["api_key"] = API_KEY
    else:
        if not (USERNAME and PASSWORD): raise RuntimeError("Missing Basic auth vars")
        kwargs["basic_auth"] = (USERNAME, PASSWORD)
    return Elasticsearch(**kwargs)

es = build_client()

def jsonrpc_error(id_, code, message, data=None):
    err = {"jsonrpc":"2.0","error":{"code":code,"message":message},"id":id_}
    if data is not None: err["error"]["data"] = data
    return err

def jsonrpc_result(id_, result):
    return {"jsonrpc":"2.0","id":id_,"result":result}

def ensure_time_range(query: Dict[str, Any]) -> Dict[str, Any]:
    if not REQUIRE_TIME_RANGE: return query
    def has_time_range(q):
        if isinstance(q, dict):
            for k,v in q.items():
                if k == "range" and isinstance(v, dict):
                    for f in v.keys():
                        if f in TIME_FIELD_CANDIDATES: return True
                if has_time_range(v): return True
        elif isinstance(q, list):
            for it in q:
                if has_time_range(it): return True
        return False
    if has_time_range(query): return query
    time_field = TIME_FIELD_CANDIDATES[0]
    injected = {"bool":{"must":[{"range": { time_field: {"gte": DEFAULT_LOOKBACK} }}]}}
    if not query: return injected
    return {"bool":{"must":[injected, query]}}

def clamp_size(body: Dict[str,Any]):
    size = body.get("size")
    if size is None: body["size"] = min(10, MAX_SIZE)
    elif size > MAX_SIZE: body["size"] = MAX_SIZE

def tool_health(_args): return es.cluster.health().body

def tool_cat_indices(_args): return es.cat.indices(format="json").body

def tool_search(args):
    index_arg = args.get("index", "default")
    body = args.get("body", {})

    # インデックス名を解決
    resolved_index = resolve_index(index_arg)

    # 複数インデックスの場合は個別にチェック
    for idx in resolved_index.split(','):
        if not match_allowed(idx.strip()):
            raise ValueError(f"index '{idx}' not allowed")

    if "query" in body: body["query"] = ensure_time_range(body["query"])
    else: body["query"] = ensure_time_range({"match_all":{}})
    clamp_size(body)

    return es.search(index=resolved_index, body=body).body

def inject_esql_time_range(esql_query: str) -> str:
    if not REQUIRE_TIME_RANGE: return esql_query
    if re.search(r"\bWHERE\b", esql_query, re.IGNORECASE): return esql_query
    time_field = "@timestamp"
    if "|" in esql_query:
        head, rest = esql_query.split("|",1)
        return f"{head.strip()} WHERE {time_field} >= {DEFAULT_LOOKBACK} | {rest}"
    return f"{esql_query.strip()} WHERE {time_field} >= {DEFAULT_LOOKBACK}"

def tool_esql(args):
    query = args.get("query")
    if not query: raise ValueError("query required")
    if FORBIDDEN_ESQL.search(query): raise ValueError("forbidden keyword")
    q = inject_esql_time_range(query)
    return es.transport.perform_request("POST","/_query", body={"query": q}).body

def tool_list_indices(_args):
    """設定済みインデックス一覧を返す"""
    return {
        "configured_indices": INDICES,
        "usage": {
            "single": "index: 'keikakuhoshin' または index: 'yosankessan'",
            "multiple": "index: 'keikakuhoshin,yosankessan'",
            "all": "index: 'all'"
        }
    }

def tool_multi_search(args):
    """複数インデックス横断検索"""
    indices = args.get("indices", "all")
    query_text = args.get("query")
    size = min(args.get("size", 10), MAX_SIZE)

    if not query_text:
        raise ValueError("query text required")

    resolved_indices = resolve_index(indices)

    # 複数インデックスの場合は個別にチェック
    for idx in resolved_indices.split(','):
        if not match_allowed(idx.strip()):
            raise ValueError(f"index '{idx}' not allowed")

    body = {
        "size": size,
        "query": {
            "multi_match": {
                "query": query_text,
                "fields": ["title^2", "content_text"]
            }
        },
        "_source": ["title", "organization_code", "created_at", "content_text"]
    }

    body["query"] = ensure_time_range(body["query"])

    return es.search(index=resolved_indices, body=body).body

TOOLS = {
    "health": {"fn": tool_health},
    "cat_indices": {"fn": tool_cat_indices},
    "search": {"fn": tool_search},
    "esql": {"fn": tool_esql},
    "list_indices": {"fn": tool_list_indices},
    "multi_search": {"fn": tool_multi_search}
}

def handle_request(obj):
    if not isinstance(obj, dict): return jsonrpc_error(None,-32600,"Invalid Request")
    if obj.get("jsonrpc") != "2.0": return jsonrpc_error(obj.get("id"), -32600, "Invalid jsonrpc version")
    method = obj.get("method"); id_ = obj.get("id")
    if method == "initialize":
        return jsonrpc_result(id_, {
            "protocolVersion": "2025-03-26",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "elasticsearch",
                "version": "1.0.0"
            }
        })
    if method == "list_tools":
        return jsonrpc_result(id_, [ {"name": n, "description": f"Elasticsearch {n}"} for n in TOOLS.keys() ])
    if method == "call_tool":
        params = obj.get("params") or {}
        name = params.get("name")
        if name not in TOOLS: return jsonrpc_error(id_, -32601, "Tool not found")
        try:
            result = TOOLS[name]["fn"](params.get("arguments") or {})
            return jsonrpc_result(id_, {"name": name, "output": result})
        except Exception as e:
            return jsonrpc_error(id_, -32000, str(e), {"trace": traceback.format_exc() if VERBOSE else None})
    return jsonrpc_error(id_, -32601, "Method not found")

def main():
    print(json.dumps({"jsonrpc":"2.0","method":"ready","params":{"ok":True}}), flush=True)
    for line in sys.stdin:
        line=line.strip()
        if not line: continue
        try: obj = json.loads(line)
        except Exception:
            print(json.dumps(jsonrpc_error(None,-32700,"Parse error")), flush=True)
            continue
        resp = handle_request(obj)
        print(json.dumps(resp, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    main()
