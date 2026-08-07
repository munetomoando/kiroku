import stat

from kiroku import summarize


def _day(date: str, project: str = "foo") -> dict:
    return {"date": date, "projects": [
        {"project": project, "stats": {"user_turns": 1, "assistant_turns": 1,
                                       "first_ts": f"{date}T01:00:00+00:00",
                                       "last_ts": f"{date}T01:05:00+00:00"},
         "prompts": ["やって"], "highlights": ["やりました"]},
    ]}


def test_summarize_single_day_success():
    digest = {"days": [
        {"date": "2026-07-17", "projects": [
            {"project": "foo", "stats": {"user_turns": 1, "assistant_turns": 1,
                                          "first_ts": "2026-07-17T01:00:00+00:00",
                                          "last_ts": "2026-07-17T01:05:00+00:00"},
             "prompts": ["やって"], "highlights": ["やりました"]},
        ]},
    ]}

    def runner(claude_bin, prompt_text):
        return '{"2026-07-17": {"foo": {"summary": "S", "bullets": ["b"]}}}'

    result = summarize.summarize_digest(digest, "claude", runner=runner)
    assert result["2026-07-17"]["foo"]["summary"] == "S"


def test_summarize_failure_is_skipped():
    digest = {"days": [
        {"date": "2026-07-18", "projects": [
            {"project": "foo", "stats": {"user_turns": 1, "assistant_turns": 1,
                                          "first_ts": "2026-07-18T01:00:00+00:00",
                                          "last_ts": "2026-07-18T01:05:00+00:00"},
             "prompts": ["やって"], "highlights": ["やりました"]},
        ]},
    ]}

    def runner(claude_bin, prompt_text):
        return None

    result = summarize.summarize_digest(digest, "claude", runner=runner, wait_sec=0)
    assert "2026-07-18" not in result
    assert result == {}


def test_summarize_multi_day_independent_calls():
    digest = {"days": [
        {"date": "2026-07-16", "projects": [
            {"project": "foo", "stats": {"user_turns": 1, "assistant_turns": 1,
                                          "first_ts": "2026-07-16T01:00:00+00:00",
                                          "last_ts": "2026-07-16T01:05:00+00:00"},
             "prompts": ["A"], "highlights": ["a"]},
        ]},
        {"date": "2026-07-17", "projects": [
            {"project": "bar", "stats": {"user_turns": 1, "assistant_turns": 1,
                                          "first_ts": "2026-07-17T01:00:00+00:00",
                                          "last_ts": "2026-07-17T01:05:00+00:00"},
             "prompts": ["B"], "highlights": ["b"]},
        ]},
    ]}

    def runner(claude_bin, prompt_text):
        if "2026-07-16" in prompt_text:
            return '{"2026-07-16": {"foo": {"summary": "S1", "bullets": ["b1"]}}}'
        if "2026-07-17" in prompt_text:
            return '{"2026-07-17": {"bar": {"summary": "S2", "bullets": ["b2"]}}}'
        return None

    result = summarize.summarize_digest(digest, "claude", runner=runner)
    assert result["2026-07-16"]["foo"]["summary"] == "S1"
    assert result["2026-07-17"]["bar"]["summary"] == "S2"


# --- 一過性の失敗に対する再試行 -------------------------------------------
# 実運用のログでは、要約失敗の原因はいずれも一過性だった:
#   - API Error: Connection closed mid-response
#   - API Error: Unable to connect to API (ENOTFOUND)（スリープ復帰直後の DNS 未復帰）
#   - 「JSON を作ります」という前置きだけ返して end_turn
# 1 回で諦めるとその日の要約が丸ごと失われるため、再試行できること。

def test_summarize_retries_after_runner_failure():
    digest = {"days": [_day("2026-07-17")]}
    calls = []

    def runner(claude_bin, prompt_text):
        calls.append(1)
        if len(calls) == 1:
            return None  # claude が異常終了
        return '{"2026-07-17": {"foo": {"summary": "S", "bullets": ["b"]}}}'

    result = summarize.summarize_digest(digest, "claude", runner=runner, wait_sec=0)
    assert result["2026-07-17"]["foo"]["summary"] == "S"
    assert len(calls) == 2


def test_summarize_retries_when_response_has_no_json():
    digest = {"days": [_day("2026-07-17")]}
    calls = []

    def runner(claude_bin, prompt_text):
        calls.append(1)
        if len(calls) == 1:
            # 前置きだけ返して終了した実例（2026-08-02 のセッション）
            return "I'll produce the summary JSON for the two projects on 2026-07-17."
        return '{"2026-07-17": {"foo": {"summary": "S", "bullets": ["b"]}}}'

    result = summarize.summarize_digest(digest, "claude", runner=runner, wait_sec=0)
    assert result["2026-07-17"]["foo"]["summary"] == "S"
    assert len(calls) == 2


def test_summarize_gives_up_after_max_attempts():
    digest = {"days": [_day("2026-07-17")]}
    calls = []

    def runner(claude_bin, prompt_text):
        calls.append(1)
        return None

    result = summarize.summarize_digest(digest, "claude", runner=runner, wait_sec=0)
    assert result == {}
    assert len(calls) == summarize.MAX_ATTEMPTS


def test_summarize_one_bad_day_does_not_stop_the_others():
    digest = {"days": [_day("2026-07-16", "foo"), _day("2026-07-17", "bar")]}

    def runner(claude_bin, prompt_text):
        if "2026-07-16" in prompt_text:
            return None
        return '{"2026-07-17": {"bar": {"summary": "S2", "bullets": ["b"]}}}'

    result = summarize.summarize_digest(digest, "claude", runner=runner, wait_sec=0)
    assert "2026-07-16" not in result
    assert result["2026-07-17"]["bar"]["summary"] == "S2"


# --- 失敗理由をログに残す -------------------------------------------------
# 調査時に「要約失敗」としか残っておらず、原因の特定に
# ~/.claude/projects の jsonl を掘る必要があった。理由を stderr に出すこと
# （run-kiroku.sh が stderr を kiroku.log へ追記する）。

def test_default_runner_logs_missing_binary(capsys):
    out = summarize._default_runner("/nonexistent/path/to/claude", "x")
    assert out is None
    err = capsys.readouterr().err
    assert "/nonexistent/path/to/claude" in err


def test_default_runner_logs_exit_code_and_stderr(tmp_path, capsys):
    fake = tmp_path / "failing_claude.sh"
    fake.write_text('#!/usr/bin/env bash\ncat >/dev/null\n'
                    'echo "Credit balance is too low" >&2\nexit 1\n',
                    encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)

    out = summarize._default_runner(str(fake), "x")
    assert out is None
    err = capsys.readouterr().err
    assert "1" in err                          # 終了コード
    assert "Credit balance is too low" in err  # claude 側の理由


def test_summarize_skips_days_not_marked_for_resummary():
    # needs_summary=False の日（＝すでに要約できている過去日）は claude を
    # 呼ばない。pending の呼び戻しで期間が伸びても呼び出しは増えない。
    older = _day("2026-07-16", "foo")
    older["needs_summary"] = False
    digest = {"days": [older, _day("2026-07-17", "bar")]}
    calls = []

    def runner(claude_bin, prompt_text):
        calls.append(prompt_text)
        return '{"2026-07-17": {"bar": {"summary": "S", "bullets": ["b"]}}}'

    result = summarize.summarize_digest(digest, "claude", runner=runner, wait_sec=0)
    assert "2026-07-16" not in result
    assert result["2026-07-17"]["bar"]["summary"] == "S"
    assert len(calls) == 1
