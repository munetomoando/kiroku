#!/usr/bin/env bash
# 引数 -p を無視して stdin を読み捨て、固定の要約 JSON を返す
cat >/dev/null
cat <<'JSON'
```json
{"__DATE__": {"__PROJ__": {"summary": "テスト要約", "bullets": ["項目1", "項目2"]}}}
```
JSON
