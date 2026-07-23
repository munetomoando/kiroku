#!/usr/bin/env bash
# sleepwatcher の wakeup フックから呼ばれる薄いラッパ。
# 復帰直後はネットワーク・ログインシェル環境が未整備なことがあるため
# PATH を明示し、少し待ってから本体を起動する。
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
sleep "${KIROKU_WAKE_DELAY:-20}"
# sleepwatcher はこのスクリプトを ~/.wakeup（シンボリックリンク）として
# 実行するため、$0 はリンク側のパスになる。dirname "$0" では実体の場所を
# 見失うので、リンクをたどって本物の配置ディレクトリを解決する。
SRC="$0"
while [ -L "$SRC" ]; do
  DIR="$(cd "$(dirname "$SRC")" && pwd)"
  SRC="$(readlink "$SRC")"
  case "$SRC" in /*) ;; *) SRC="$DIR/$SRC" ;; esac
done
exec "$(cd "$(dirname "$SRC")" && pwd)/run-kiroku.sh"
