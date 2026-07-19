# kiroku — Claude Code 作業報告書の自動生成（macOS）

Claude Code での日々の作業を Claude 自身が要約し、単一の累積 HTML
（`作業報告書.html`）へ日ごとに積み上げるツールです。最新の記録が上に積み上がり、
上部の月ボタンで各月へジャンプできます。地層のように記録が貯まっていきます。

- 全プロジェクト横断で「昨日までの作業」をまとめる
- 同じ日に何度実行しても、その日の作業は 1 項目にまとめ直される
- スリープ復帰時に自動実行（任意）、または Dock のアイコンをクリックで実行
- 生成物・元データはすべてローカル。外部送信なし

## 動作要件

- **macOS**（`osacompile` / `open` / 任意で Homebrew の sleepwatcher を使用）
- **Python 3**（標準ライブラリのみ。追加パッケージ不要）
- **Claude Code CLI**（`claude` コマンド。要約に使用）

## インストール

```bash
git clone <このリポジトリのURL> kiroku
cd kiroku
./install.sh
```

`install.sh` は次を行います:

1. macOS / `python3` / `claude` CLI の確認
2. クリックで起動できるランチャーアプリ `/Applications/kiroku.app` を生成
   （配置パスを埋め込み、同梱アイコンを適用）
3. （任意）スリープ復帰時の自動実行を sleepwatcher で設定

生成後、Finder で `kiroku.app` を Dock へドラッグしておくと、いつでも 1 クリックで
報告書を開けます。

## 使い方

- **アイコンをクリック**: 新しい作業があれば報告書を更新し、更新の有無に関わらず
  必ずブラウザで報告書を開きます（「今の報告書を見る」操作）。
- **手動実行（ターミナル）**:

      bash run-kiroku.sh

- **自動（スリープ復帰）**: 前日までに新しい作業があった時だけ報告書を更新・表示します。

初回は `state.json` が無いため、過去 2 日分を日ごとにバックフィルします。

## 仕組み

`run-kiroku.sh` が 3 段階で動きます:

1. `gather.py` … `~/.claude/projects` の各セッション jsonl から、前回記録以降の作業を
   日付 × プロジェクト別に抽出。前回以降に新しい作業が無ければ何もしません。
   （要約用の内部呼び出しは専用ディレクトリ `.summarizer` に隔離し、記録対象から除外）
2. `claude -p` … 抽出結果を要約し、プロジェクトごとの要約文＋箇条書きを生成。
3. `render.py` … `entries.json`（全記録の元データ）に当日分を追記し、そこから
   `作業報告書.html` を毎回まるごと再生成。

`entries.json` が真実の源で、HTML は毎回そこから再生成されます。要約に失敗しても、
機械抽出した箇条書きで最低限の記録を残します。

## sleepwatcher を後から設定する

`install.sh` でスキップした場合は、次で有効化できます:

```bash
brew install sleepwatcher
ln -sf "$PWD/wakeup.sh" ~/.wakeup
brew services start sleepwatcher
```

`wakeup.sh` は復帰後 20 秒待ってから `run-kiroku.sh` を起動します。

## ランチャーアプリを作り直す

`install.sh` を再実行すれば再生成されます。手動で作る場合:

```bash
sed "s#__KIROKU_DIR__#$PWD#g" launcher.applescript > /tmp/kiroku.applescript
osacompile -o /Applications/kiroku.app /tmp/kiroku.applescript
cp icon/kiroku.icns /Applications/kiroku.app/Contents/Resources/applet.icns
codesign --force --deep -s - /Applications/kiroku.app
```

アプリ内スクリプトだけ差し替えたい場合（アイコンを保持）は、`Contents/Resources/Scripts/main.scpt`
を上書きして再署名してください。

## ファイル構成

| ファイル | 役割 |
|---|---|
| `作業報告書.html` | 成果物（累積・単一ファイル。git 管理外） |
| `entries.json` | 全記録の元データ（真実の源。git 管理外） |
| `state.json` | 前回記録タイムスタンプ・最終記録日（git 管理外） |
| `config.py` | パス・定数・時刻ユーティリティ |
| `gather.py` | jsonl 抽出（決定的） |
| `prompt.py` | 要約プロンプト生成・応答パース・フォールバック |
| `render.py` | entries.json 追記＋HTML 再生成（決定的） |
| `run-kiroku.sh` | オーケストレーション（ロック・ログ付き） |
| `wakeup.sh` | sleepwatcher 用ラッパ |
| `launcher.applescript` | ランチャーアプリの雛形（install.sh がパスを埋め込む） |
| `install.sh` | セットアップ（アプリ生成・sleepwatcher 設定） |

`entries.json` / `state.json` / `作業報告書.html` / `kiroku.log` / `.summarizer/` は
`.gitignore` 済みで、各利用者のローカルにのみ生成されます。

## リセット（最初から作り直す）

```bash
rm -f state.json entries.json 作業報告書.html
bash run-kiroku.sh   # 再び過去 2 日をバックフィル
```

## アンインストール

```bash
brew services stop sleepwatcher   # 自動実行を設定した場合
rm -f ~/.wakeup
rm -rf /Applications/kiroku.app
```

あとは clone したディレクトリを削除すれば完了です。

## トラブルシュート

- 生成されない: `tail -n 30 kiroku.log` を確認。
- 要約が空: `claude -p` が単体で動くか（認証）を確認。失敗時も箇条書きで記録は残ります。
- アイコンが Dock に反映されない: 一度 Dock から外して入れ直すと確実です。

## 開発

テストと（アイコン再生成用の）依存は仮想環境で:

```bash
python3 -m venv .venv
.venv/bin/pip install pytest pillow
.venv/bin/python -m pytest -q
```

（実行時は標準ライブラリのみで動くため、利用だけなら venv は不要です。）
