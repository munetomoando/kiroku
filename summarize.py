"""ダイジェストを日ごとに claude -p で要約し、要約マップを組み立てる。"""
import json
import os
import subprocess
import sys

from kiroku import prompt


def _default_runner(claude_bin: str, prompt_text: str) -> str | None:
    """claude -p を呼び、stdout を返す。失敗（非0終了・起動不可）なら None。"""
    try:
        result = subprocess.run([claude_bin, "-p"], input=prompt_text,
                                capture_output=True, text=True)
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def summarize_digest(digest: dict, claude_bin: str, runner=_default_runner) -> dict:
    """各 day を個別に要約。戻り値は {date: {project: {summary, bullets}}}。
    ある日の要約が失敗/空なら、その日はスキップ（render 側でフォールバックされる）。"""
    summary: dict = {}
    days = digest.get("days", [])
    for i, day in enumerate(days):
        date = day.get("date")
        prompt_text = prompt.build_prompt({"days": [day]})
        out = runner(claude_bin, prompt_text)
        if out is None:
            sys.stderr.write(f"[summarize] {date}: 要約失敗（{i+1}/{len(days)}）\n")
            continue
        parsed = prompt.parse_summary(out)
        day_map = parsed.get(date, {})
        if day_map:
            summary[date] = day_map
            sys.stderr.write(f"[summarize] {date}: 要約成功（{i+1}/{len(days)}）\n")
        else:
            sys.stderr.write(f"[summarize] {date}: 応答から該当日なし（{i+1}/{len(days)}）\n")
    return summary


def main() -> int:
    """stdin のダイジェストを日ごとに要約し、要約マップ JSON を stdout に出す。"""
    claude_bin = os.environ.get("KIROKU_CLAUDE_BIN", "claude")
    digest = json.load(sys.stdin)
    summary = summarize_digest(digest, claude_bin)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
