#!/usr/bin/env bash
set -euo pipefail

# kiroku ルートと親（PYTHONPATH 用）
KIROKU_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$KIROKU_DIR")"
export PYTHONPATH="$PARENT_DIR${PYTHONPATH:+:$PYTHONPATH}"

LOG="$KIROKU_DIR/kiroku.log"
LOCK="$KIROKU_DIR/.kiroku.lock"
CLAUDE_BIN="${KIROKU_CLAUDE_BIN:-claude}"
PY="${KIROKU_PYTHON:-python3}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >>"$LOG"; }

# 多重起動防止（既にロックがあれば終了）
if ! mkdir "$LOCK" 2>/dev/null; then
  log "既にロック中のため終了"
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

log "=== 実行開始 ==="

# 1) ダイジェスト取得
DIGEST="$("$PY" -m kiroku.gather)"
if echo "$DIGEST" | "$PY" -c "import sys,json;d=json.load(sys.stdin);sys.exit(0 if d.get('days') else 1)"; then
  log "ダイジェスト取得（記録あり）"
else
  log "記録対象なし（1日ガードまたは差分なし）→ 終了"
  exit 0
fi

# 2) 日ごとに要約（summarize が claude を日単位で呼ぶ。stderr はログへ）
SUMMARY="$(printf '%s' "$DIGEST" | KIROKU_CLAUDE_BIN="$CLAUDE_BIN" "$PY" -m kiroku.summarize 2>>"$LOG")"
if [ -z "$SUMMARY" ]; then
  SUMMARY="{}"
  log "要約が空 → フォールバック使用"
else
  log "要約生成 完了"
fi

# 3) レンダリング（digest + summary を stdin で渡す）
printf '{"digest":%s,"summary":%s}' "$DIGEST" "$SUMMARY" | "$PY" -m kiroku.render
log "レンダリング完了 → 作業報告書.html 更新"
log "=== 実行終了 ==="
