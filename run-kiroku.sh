#!/usr/bin/env bash
set -euo pipefail

# kiroku ルートと親（PYTHONPATH 用）
KIROKU_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$KIROKU_DIR")"
export PYTHONPATH="$PARENT_DIR${PYTHONPATH:+:$PYTHONPATH}"

# ログは entries/state/html と同じ場所（config.LOG_PATH と一致させる）。
# ここだけ KIROKU_HOME を無視していたため、テスト実行が本番のログに混ざり、
# 障害調査のときに実行履歴が読みにくくなっていた。
LOG="${KIROKU_HOME:-$KIROKU_DIR}/kiroku.log"
LOCK="$KIROKU_DIR/.kiroku.lock"
PY="${KIROKU_PYTHON:-python3}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >>"$LOG"; }

# claude の実体を解決する。sleepwatcher やアプリからの起動では PATH が
# 最小限になるため、PATH だけに頼るとインストール先が変わった時点で自動実行が
# 静かに全滅する（ネイティブ版インストーラで ~/.local/bin へ移った際に発生）。
# 既知の配置先も順に探し、見つからなければログに理由を残す。
resolve_claude() {
  if [ -n "${KIROKU_CLAUDE_BIN:-}" ]; then
    printf '%s' "$KIROKU_CLAUDE_BIN"; return 0
  fi
  local c
  if c="$(command -v claude 2>/dev/null)" && [ -n "$c" ]; then
    printf '%s' "$c"; return 0
  fi
  for c in "$HOME/.local/bin/claude" "$HOME/.claude/local/claude" \
           "/opt/homebrew/bin/claude" "/usr/local/bin/claude"; do
    if [ -x "$c" ]; then printf '%s' "$c"; return 0; fi
  done
  return 1
}

# 進捗テキストを段階ファイルへ（KIROKU_STAGE_FILE 未設定なら何もしない）。
# ランチャーがこれを読み、進捗ウィンドウに現在の段階を表示する。
stage() { [ -n "${KIROKU_STAGE_FILE:-}" ] && printf '%s' "$1" >"$KIROKU_STAGE_FILE" 2>/dev/null || true; }

# 多重起動防止（既にロックがあれば終了）
if ! mkdir "$LOCK" 2>/dev/null; then
  log "既にロック中のため終了"
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

log "=== 実行開始 ==="

if CLAUDE_BIN="$(resolve_claude)"; then
  :
else
  CLAUDE_BIN="claude"
  log "警告: claude が見つかりません（PATH=$PATH）。要約はフォールバックになります"
fi

# 自動実行（KIROKU_AUTO=1、sleepwatcher 経由）では表示は1日1回まで。
# その日すでに記録済みなら、この後の更新は行うが完了後の表示だけ抑止する。
# 判定は state.json が更新される前（ここ）で行う必要がある。
AUTO_SKIP_OPEN=0
if [ "${KIROKU_AUTO:-0}" = "1" ]; then
  if "$PY" -c "
import datetime, sys
from kiroku import gather, config
now = datetime.datetime.now(config.LOCAL_TZ)
sys.exit(0 if gather.already_recorded_today(
    gather.load_state(config.STATE_PATH), now) else 1)
"; then
    AUTO_SKIP_OPEN=1
  fi
fi

# 1) ダイジェスト取得
stage "作業を収集しています…"
DIGEST="$("$PY" -m kiroku.gather)"
if echo "$DIGEST" | "$PY" -c "import sys,json;d=json.load(sys.stdin);sys.exit(0 if d.get('days') else 1)"; then
  log "ダイジェスト取得（記録あり）"
else
  log "記録対象なし（1日ガードまたは差分なし）→ 終了"
  exit 0
fi

# 2) 日ごとに要約（summarize が claude を日単位で呼ぶ。stderr はログへ）
#    summarize 側が「N日中 i日目」の細かい段階を KIROKU_STAGE_FILE に書き込む。
stage "要約を生成しています…"
SUMMARY="$(printf '%s' "$DIGEST" | KIROKU_CLAUDE_BIN="$CLAUDE_BIN" "$PY" -m kiroku.summarize 2>>"$LOG")"
if [ -z "$SUMMARY" ]; then
  SUMMARY="{}"
  log "要約が空 → フォールバック使用"
else
  log "要約生成 完了"
fi

# 3) レンダリング（digest + summary を stdin で渡す）
stage "報告書を作成しています…"
printf '{"digest":%s,"summary":%s}' "$DIGEST" "$SUMMARY" | "$PY" -m kiroku.render
log "レンダリング完了 → 作業報告書.html 更新"

# 4) 更新された報告書を画面に表示（KIROKU_OPEN=0 で無効化）。
#    ここに到達するのは新しい記録が追記された時だけなので「更新時のみ表示」になる。
OUT_DIR="${KIROKU_HOME:-$KIROKU_DIR}"
HTML="$OUT_DIR/作業報告書.html"
if [ "$AUTO_SKIP_OPEN" = "1" ]; then
  log "自動実行・当日表示済み → 更新のみ（表示せず）"
elif [ "${KIROKU_OPEN:-1}" = "1" ] && command -v open >/dev/null 2>&1; then
  if open "$HTML" 2>>"$LOG"; then
    log "報告書を画面に表示"
  else
    log "報告書の表示に失敗"
  fi
fi
log "=== 実行終了 ==="
