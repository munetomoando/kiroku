#!/usr/bin/env bash
# kiroku セットアップ（macOS 専用）。
#   ./install.sh
# を実行すると、ランチャーアプリを生成し、任意で sleepwatcher 連携を設定する。
set -euo pipefail

KIROKU_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_PATH="/Applications/kiroku.app"

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
warn() { printf '\033[33m  ! %s\033[0m\n' "$*"; }
ask()  { local q="$1" a; read -r -p "$q " a; [ "${a:-}" = "y" ] || [ "${a:-}" = "Y" ]; }

say "kiroku セットアップを開始します"
info "配置先: $KIROKU_DIR"

# 1) 前提チェック --------------------------------------------------------------
if [ "$(uname)" != "Darwin" ]; then
  warn "kiroku は macOS 専用です（現在: $(uname)）。中止します。"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  warn "python3 が見つかりません。Python 3 をインストールしてから再実行してください。"
  exit 1
fi
info "python3: $(python3 --version 2>&1)"

if command -v claude >/dev/null 2>&1; then
  info "claude CLI: 検出 ($(command -v claude))"
else
  warn "claude CLI が見つかりません。要約には Claude Code CLI が必要です。"
  warn "後で導入する場合は、そのままセットアップを続行して構いません。"
fi

# 2) ランチャーアプリの生成 ----------------------------------------------------
say "ランチャーアプリを生成します"
TMP_SCPT="$(mktemp -d)/launcher.applescript"
# テンプレートの __KIROKU_DIR__ を実際の配置パスに置換してから osacompile。
sed "s#__KIROKU_DIR__#${KIROKU_DIR}#g" "$KIROKU_DIR/launcher.applescript" >"$TMP_SCPT"

if [ -e "$APP_PATH" ]; then
  info "既存の $APP_PATH を置き換えます"
  rm -rf "$APP_PATH"
fi
osacompile -o "$APP_PATH" "$TMP_SCPT"

# プリビルドのアイコンを適用（Pillow 不要）。
# osacompile は既定アイコン入りの Assets.car と CFBundleIconName を毎回作る。
# それらが applet.icns より優先されるため、アセットカタログを無効化して
# applet.icns（CFBundleIconFile）へフォールバックさせる。
if [ -f "$KIROKU_DIR/icon/kiroku.icns" ]; then
  cp "$KIROKU_DIR/icon/kiroku.icns" "$APP_PATH/Contents/Resources/applet.icns"
  /usr/libexec/PlistBuddy -c "Delete :CFBundleIconName" \
    "$APP_PATH/Contents/Info.plist" >/dev/null 2>&1 || true
  if [ -f "$APP_PATH/Contents/Resources/Assets.car" ]; then
    mv "$APP_PATH/Contents/Resources/Assets.car" \
       "$APP_PATH/Contents/Resources/Assets.car.disabled"
  fi
fi
codesign --force --deep -s - "$APP_PATH" >/dev/null 2>&1 || true
# アイコンキャッシュを更新（Dock/Finder に反映）。
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
[ -x "$LSREGISTER" ] && "$LSREGISTER" -f "$APP_PATH" >/dev/null 2>&1 || true
touch "$APP_PATH"; killall Dock >/dev/null 2>&1 || true
info "生成: $APP_PATH"
info "Finder でこのアプリを Dock へドラッグすると、クリックで報告書を開けます。"

# 3) sleepwatcher 連携（任意）--------------------------------------------------
say "スリープ復帰時の自動実行（sleepwatcher）を設定しますか？"
info "設定すると、前日の作業があれば復帰時に自動で報告書を更新します。"
if ask "設定する？ [y/N]"; then
  if ! command -v brew >/dev/null 2>&1; then
    warn "Homebrew が見つかりません。https://brew.sh を導入してから再実行してください。"
  else
    if ! brew list sleepwatcher >/dev/null 2>&1; then
      info "sleepwatcher をインストールします..."
      brew install sleepwatcher
    fi
    ln -sf "$KIROKU_DIR/wakeup.sh" "$HOME/.wakeup"
    brew services start sleepwatcher >/dev/null 2>&1 || brew services restart sleepwatcher
    info "sleepwatcher を有効化しました（~/.wakeup → wakeup.sh）。"
  fi
else
  info "自動実行はスキップしました。あとで設定する場合は README を参照してください。"
fi

# 4) 完了 --------------------------------------------------------------------
say "セットアップ完了"
info "手動実行:  bash \"$KIROKU_DIR/run-kiroku.sh\""
info "またはアプリ $APP_PATH をクリック。"
info "初回は過去 2 日分の作業を要約して 作業報告書.html を生成します。"
