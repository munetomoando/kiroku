#!/usr/bin/env bash
# sleepwatcher の wakeup フックから呼ばれる薄いラッパ。
# 復帰直後はネットワーク・ログインシェル環境が未整備なことがあるため
# PATH を明示し、少し待ってから本体を起動する。
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
sleep 20
exec "$(dirname "$0")/run-kiroku.sh"
