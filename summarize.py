"""ダイジェストを日ごとに claude -p で要約し、要約マップを組み立てる。"""
import json
import os
import subprocess
import sys
import time

from kiroku import config, prompt

# 1 日分の要約を諦めるまでの試行回数と、試行間の待ち時間（秒）。
# 実運用で観測された失敗はいずれも一過性だった:
#   - API Error: Connection closed mid-response（応答の途中で切断）
#   - API Error: Unable to connect to API (ENOTFOUND)（復帰直後で DNS 未確立）
#   - 「JSON を作ります」という前置きだけ返して end_turn
# 1 回で諦めるとその日の要約が丸ごと失われるため、間を置いて作り直す。
# 待ち時間は試行回数に比例して伸ばす（ネットワーク復帰待ちを兼ねる）。
MAX_ATTEMPTS = int(os.environ.get("KIROKU_SUMMARY_ATTEMPTS", "3"))
RETRY_WAIT_SEC = float(os.environ.get("KIROKU_SUMMARY_WAIT_SEC", "15"))


def _write_stage(text: str) -> None:
    """進捗テキストを KIROKU_STAGE_FILE へ書き出す（未設定なら何もしない）。
    ランチャーがこのファイルを読み、進捗ウィンドウに現在の段階を表示する。"""
    path = os.environ.get("KIROKU_STAGE_FILE")
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass


def _tail(text: str | None, limit: int = 300) -> str:
    """ログ 1 行に収まるよう、末尾だけを 1 行にして返す。"""
    return " ".join((text or "").split())[-limit:]


def _default_runner(claude_bin: str, prompt_text: str) -> str | None:
    """claude -p を専用 cwd で呼び、stdout を返す。失敗なら None。
    専用 cwd（config.SUMMARIZER_CWD）で実行することで、この要約呼び出し自体が
    ~/.claude/projects の専用プロジェクトに記録され、kiroku 本体の記録を汚さない。
    失敗時は理由を stderr に残す（run-kiroku.sh が kiroku.log へ追記する）。
    理由を捨てていたため、過去の失敗調査ではセッション jsonl を掘る必要があった。"""
    try:
        config.SUMMARIZER_CWD.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([claude_bin, "-p"], input=prompt_text,
                                capture_output=True, text=True,
                                cwd=str(config.SUMMARIZER_CWD))
    except OSError as e:
        sys.stderr.write(f"[summarize] claude を起動できません: {claude_bin} ({e})\n")
        return None
    if result.returncode != 0:
        # API エラー（Connection closed / ENOTFOUND など）は stdout 側に出る
        # ことがあるため、両方の末尾を残す。
        sys.stderr.write(
            f"[summarize] claude 異常終了 code={result.returncode}"
            f" stderr={_tail(result.stderr)!r} stdout={_tail(result.stdout)!r}\n")
        return None
    return result.stdout


def summarize_day(day: dict, claude_bin: str, runner=_default_runner,
                  attempts: int = MAX_ATTEMPTS,
                  wait_sec: float = RETRY_WAIT_SEC) -> dict:
    """1 日分を要約して {project: {summary, bullets}} を返す。
    一過性の失敗に備え、使える応答が得られるまで attempts 回まで試す。
    すべて失敗したら {}（render 側でフォールバックされる）。"""
    date = day.get("date")
    for attempt in range(1, attempts + 1):
        out = runner(claude_bin, prompt.build_prompt({"days": [day]}))
        if out is None:
            reason = "claude 呼び出し失敗"
        else:
            day_map = prompt.parse_summary(out).get(date, {})
            if day_map:
                return day_map
            reason = "応答に該当日の JSON なし"
        sys.stderr.write(
            f"[summarize] {date}: {reason}（試行 {attempt}/{attempts}）\n")
        if attempt < attempts and wait_sec:
            time.sleep(wait_sec * attempt)
    return {}


def summarize_digest(digest: dict, claude_bin: str, runner=_default_runner,
                     attempts: int = MAX_ATTEMPTS,
                     wait_sec: float = RETRY_WAIT_SEC) -> dict:
    """各 day を個別に要約。戻り値は {date: {project: {summary, bullets}}}。
    ある日が全試行で失敗しても、他の日の要約は続行する。"""
    summary: dict = {}
    days = digest.get("days", [])
    for i, day in enumerate(days):
        date = day.get("date")
        if not day.get("needs_summary", True):
            # 再要約待ちの日を呼び戻すために期間が伸びただけの日。
            # すでに要約できているので claude は呼ばない（render 側で温存される）。
            continue
        _write_stage(f"要約を生成しています…（{len(days)}日中 {i + 1}日目）")
        day_map = summarize_day(day, claude_bin, runner=runner,
                                attempts=attempts, wait_sec=wait_sec)
        if day_map:
            summary[date] = day_map
            sys.stderr.write(f"[summarize] {date}: 要約成功（{i+1}/{len(days)}）\n")
        else:
            sys.stderr.write(
                f"[summarize] {date}: 要約失敗・{attempts}回とも不成立"
                f"（{i+1}/{len(days)}）\n")
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
