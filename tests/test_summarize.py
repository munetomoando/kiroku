from kiroku import summarize


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

    result = summarize.summarize_digest(digest, "claude", runner=runner)
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
