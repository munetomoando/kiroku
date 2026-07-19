# 作業報告書 自動生成

MacBook のスリープ復帰をトリガーに、Claude Code の前日の作業を Claude が要約し、
単一の累積 HTML（`作業報告書.html`）へ日ごとに積み上げます。最新の記録が上に
積み上がり、上部の月ボタンで各月へジャンプできます。

## 仕組み

sleepwatcher（wake）→ `wakeup.sh` → `run-kiroku.sh`：

1. `gather.py` … `~/.claude/projects` の各セッション jsonl から、前回記録以降の作業を
   日付 × プロジェクト別に抽出（kiroku 自身は除外）。前回記録以降に新しい作業が無ければ何もしない。
   任意の時間に何度でも実行でき、同じ日に複数回実行しても、その日の作業は 0:00 から
   まとめ直されて 1 つの項目に更新される（朝の分が夕方の実行で消えない）。
2. `claude -p` … 抽出結果を要約し、プロジェクトごとの要約文＋箇条書きを生成。
3. `render.py` … `entries.json`（全記録の元データ）に当日分を追記し、そこから
   `作業報告書.html` を毎回まるごと再生成。

`entries.json` が真実の源で、HTML は毎回そこから再生成されます。要約に失敗した場合でも、
機械抽出した箇条書きで最低限の記録を残します。

## 手動実行

    cd /Users/munetomoando/claude-work/kiroku && bash run-kiroku.sh

初回は state.json が無いため、過去 2 日分を日ごとにバックフィルします。

## デスクトップ / Dock から起動（ボタン）

ターミナルを開かずにクリックで実行できるアプリを作れます。

    osacompile -o ~/Desktop/kiroku.app /Users/munetomoando/claude-work/kiroku/launcher.applescript

`~/Desktop/kiroku.app` をダブルクリックすると `run-kiroku.sh` が走り、新しい作業が
あれば報告書を更新して Safari で表示します（無ければ何もしません）。Dock にドラッグ
すれば、いつでも1クリックで振り返れます。ソースは `launcher.applescript`。

（メニューバー常駐にしたい場合は SwiftBar / xbar などの別アプリが必要です。）

## sleepwatcher 設定

    brew install sleepwatcher
    ln -sf "$PWD/wakeup.sh" ~/.wakeup
    brew services start sleepwatcher

sleepwatcher はスリープ復帰時に `~/.wakeup` を実行します。`wakeup.sh` は 20 秒待って
から `run-kiroku.sh` を起動します（復帰直後の環境が整うのを待つため）。

## ファイル構成

| ファイル | 役割 |
|---|---|
| `作業報告書.html` | 成果物（累積・単一ファイル） |
| `entries.json` | 全記録の元データ（真実の源） |
| `state.json` | 前回記録タイムスタンプ・最終記録日 |
| `config.py` | パス・定数・時刻ユーティリティ |
| `gather.py` | jsonl 抽出（決定的） |
| `prompt.py` | 要約プロンプト生成・応答パース・フォールバック |
| `render.py` | entries.json 追記＋HTML 再生成（決定的） |
| `run-kiroku.sh` | オーケストレーション（ロック・ログ付き） |
| `wakeup.sh` | sleepwatcher 用ラッパ |
| `kiroku.log` | 実行ログ |

## リセット（最初から作り直す）

    rm -f state.json entries.json 作業報告書.html
    bash run-kiroku.sh   # 再び過去 2 日をバックフィル

## トラブルシュート

- 生成されない: `tail -n 30 kiroku.log` を確認。
- 同じ日に複数回実行すると、その日の作業はまとめて 1 項目に更新されます。前回以降に
  新しい作業が無い時だけ何もしません（正常）。
- 要約が空: `claude -p` が単体で動くか（認証）を確認。失敗時も箇条書きで記録は残ります。

## テスト

    cd /Users/munetomoando/claude-work/kiroku && .venv/bin/python -m pytest -q

著者: 安藤至大
