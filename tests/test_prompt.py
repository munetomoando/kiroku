from kiroku import prompt

DIGEST = {"days": [{"date": "2026-07-17", "projects": [
    {"project": "companion", "prompts": ["ログイン画面を作って", "色を直して"],
     "highlights": ["実装しました"],
     "stats": {"first_ts": "2026-07-17T09:00:00+09:00",
               "last_ts": "2026-07-17T18:00:00+09:00",
               "user_turns": 2, "assistant_turns": 3}}]}]}


def test_build_prompt_mentions_project_and_date_and_json():
    p = prompt.build_prompt(DIGEST)
    assert "2026-07-17" in p
    assert "companion" in p
    assert "ログイン画面を作って" in p
    assert "JSON" in p


def test_parse_summary_from_fenced_json():
    text = '説明\n```json\n{"2026-07-17": {"companion": {"summary": "s", "bullets": ["b"]}}}\n```\n'
    out = prompt.parse_summary(text)
    assert out["2026-07-17"]["companion"]["summary"] == "s"


def test_parse_summary_from_bare_json():
    text = '{"2026-07-17": {"companion": {"summary": "s", "bullets": []}}}'
    assert prompt.parse_summary(text)["2026-07-17"]["companion"]["summary"] == "s"


def test_parse_summary_bad_returns_empty():
    assert prompt.parse_summary("これはJSONではありません") == {}


def test_fallback_summary_uses_prompts_as_bullets():
    fb = prompt.fallback_summary(DIGEST)
    entry = fb["2026-07-17"]["companion"]
    assert entry["bullets"] == ["ログイン画面を作って", "色を直して"]
    assert entry["summary"] != ""
