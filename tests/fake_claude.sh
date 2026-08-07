#!/usr/bin/env bash
# 本物の claude の代わり。引数 -p は無視し、stdin のプロンプトに現れる
# 日付とプロジェクト名を読み取って、それに対応する要約 JSON を返す。
# （固定キーを返すと本物なら通る経路でも「該当日なし」となり、再試行に
#  入って end-to-end テストが実態と食い違うため、実際の値を反映させる。）
input="$(cat)"
date="$(printf '%s\n' "$input" | sed -n 's/^## \([0-9][0-9-]*\)$/\1/p' | head -1)"
projects="$(printf '%s\n' "$input" | sed -n 's/^### プロジェクト: \(.*\)$/\1/p')"
[ -n "$date" ] || date="__DATE__"
[ -n "$projects" ] || projects="__PROJ__"

printf '```json\n{"%s": {' "$date"
first=1
while IFS= read -r p; do
  [ -n "$p" ] || continue
  [ "$first" -eq 1 ] || printf ', '
  first=0
  printf '"%s": {"summary": "テスト要約", "bullets": ["項目1", "項目2"]}' "$p"
done <<EOF
$projects
EOF
printf '}}\n```\n'
