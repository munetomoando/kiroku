# kiroku トラフィック記録（自動生成）

このブランチは GitHub Actions（`.github/workflows/traffic.yml`）が毎日更新する
データ専用ブランチです。手動で編集しないでください。

- `clones.csv` … 日次クローン数（`date,clones,unique_cloners`）
- `views.csv`  … 日次閲覧数（`date,views,unique_visitors`）
- `stars.csv`  … スター数の推移（`date,stars`）

GitHub の Traffic API は直近 14 日分しか返さないため、毎日スナップショットを
取り、日付キーで累積しています。
