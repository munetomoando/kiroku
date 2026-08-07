import json
from kiroku import render

DIGEST = {"until_ts": "2026-07-18T10:00:00+09:00", "days": [
    {"date": "2026-07-17", "projects": [
        {"project": "companion", "prompts": ["x"], "highlights": [],
         "stats": {"first_ts": "2026-07-17T09:00:00+09:00",
                   "last_ts": "2026-07-17T18:00:00+09:00",
                   "user_turns": 1, "assistant_turns": 2}}]}]}
SUMMARY = {"2026-07-17": {"companion": {"summary": "要約文", "bullets": ["トピック1"]}}}


def test_merge_puts_summary_and_stats_together():
    out = render.merge_entries({"entries": []}, DIGEST, SUMMARY)
    e = out["entries"][0]
    assert e["date"] == "2026-07-17"
    pr = e["projects"][0]
    assert pr["project"] == "companion"
    assert pr["summary"] == "要約文"
    assert pr["bullets"] == ["トピック1"]
    assert pr["stats"]["user_turns"] == 1


def test_merge_sorts_dates_descending():
    existing = {"entries": [{"date": "2026-07-10", "projects": []}]}
    out = render.merge_entries(existing, DIGEST, SUMMARY)
    assert [e["date"] for e in out["entries"]] == ["2026-07-17", "2026-07-10"]


def test_merge_replaces_same_date():
    existing = {"entries": [{"date": "2026-07-17", "projects": [{"project": "old"}]}]}
    out = render.merge_entries(existing, DIGEST, SUMMARY)
    same = [e for e in out["entries"] if e["date"] == "2026-07-17"]
    assert len(same) == 1
    assert same[0]["projects"][0]["project"] == "companion"


def test_merge_sanitizes_null_summary_and_bullets():
    summary = {"2026-07-17": {"companion": {"summary": None, "bullets": None}}}
    out = render.merge_entries({"entries": []}, DIGEST, summary)
    pr = out["entries"][0]["projects"][0]
    assert pr["summary"] == ""
    assert pr["bullets"] == []


FOO_DIGEST = {"until_ts": "2026-07-18T10:00:00+09:00", "days": [
    {"date": "2026-07-17", "projects": [
        {"project": "foo", "prompts": ["やったこと1", "やったこと2"], "highlights": [],
         "stats": {"first_ts": "2026-07-17T09:00:00+09:00",
                   "last_ts": "2026-07-17T18:00:00+09:00",
                   "user_turns": 1, "assistant_turns": 2}}]}]}


def test_merge_falls_back_to_prompts_when_project_missing_from_summary():
    out = render.merge_entries({"entries": []}, FOO_DIGEST, {})
    pr = out["entries"][0]["projects"][0]
    assert pr["project"] == "foo"
    assert pr["bullets"] == ["やったこと1", "やったこと2"]
    assert pr["summary"] != ""


def test_merge_falls_back_to_placeholder_when_prompts_empty():
    digest = {"until_ts": "2026-07-18T10:00:00+09:00", "days": [
        {"date": "2026-07-17", "projects": [
            {"project": "foo", "prompts": [], "highlights": [],
             "stats": {"first_ts": "2026-07-17T09:00:00+09:00",
                       "last_ts": "2026-07-17T18:00:00+09:00",
                       "user_turns": 1, "assistant_turns": 2}}]}]}
    out = render.merge_entries({"entries": []}, digest, {})
    pr = out["entries"][0]["projects"][0]
    assert pr["bullets"] == ["（記録された指示なし）"]


def test_merge_keeps_real_summary_unchanged():
    out = render.merge_entries({"entries": []}, DIGEST, SUMMARY)
    pr = out["entries"][0]["projects"][0]
    assert pr["summary"] == "要約文"
    assert pr["bullets"] == ["トピック1"]


def test_update_state_writes_date_and_ts(tmp_path):
    p = tmp_path / "state.json"
    render.update_state(p, "2026-07-18T10:00:00+09:00", "2026-07-18")
    data = json.loads(p.read_text())
    assert data["last_recorded_ts"] == "2026-07-18T10:00:00+09:00"
    assert data["last_recorded_date"] == "2026-07-18"


# --- 一過性の要約失敗が、すでに生成できていた要約を壊さないこと ------------
# 実例: 2026-08-03 は 22:35 の実行で要約に成功していたが、翌 8/4 17:18 の
# 再実行（同日再スキャン仕様）が API エラーで失敗し、成功済みの要約が
# プレースホルダ文言に上書きされて消えた。

def test_merge_keeps_existing_summary_when_new_summary_is_missing():
    existing = {"entries": [{"date": "2026-07-17", "projects": [
        {"project": "foo", "summary": "きちんとした要約", "bullets": ["A", "B"],
         "stats": {"first_ts": "2026-07-17T09:00:00+09:00",
                   "last_ts": "2026-07-17T12:00:00+09:00",
                   "user_turns": 1, "assistant_turns": 1}}]}]}

    out = render.merge_entries(existing, FOO_DIGEST, {})  # 要約が丸ごと失敗

    pr = out["entries"][0]["projects"][0]
    assert pr["summary"] == "きちんとした要約"
    assert pr["bullets"] == ["A", "B"]
    # 統計だけは新しいダイジェストの値で更新される
    assert pr["stats"]["assistant_turns"] == 2


def test_merge_replaces_previous_placeholder_with_real_summary():
    existing = {"entries": [{"date": "2026-07-17", "projects": [
        {"project": "foo", "summary": "foo で作業を行いました（自動要約なし）。",
         "bullets": ["やったこと1"], "fallback": True,
         "stats": {"first_ts": "2026-07-17T09:00:00+09:00",
                   "last_ts": "2026-07-17T12:00:00+09:00",
                   "user_turns": 1, "assistant_turns": 1}}]}]}
    summary = {"2026-07-17": {"foo": {"summary": "本物", "bullets": ["X"]}}}

    out = render.merge_entries(existing, FOO_DIGEST, summary)

    pr = out["entries"][0]["projects"][0]
    assert pr["summary"] == "本物"
    assert pr["fallback"] is False


def test_merge_replaces_legacy_placeholder_without_flag():
    # fallback フラグ導入前に書かれた entries.json のプレースホルダも、
    # 文言から判定して「守るべき要約」とは見なさない。
    existing = {"entries": [{"date": "2026-07-17", "projects": [
        {"project": "foo",
         "summary": "foo で作業を行いました（自動要約は生成できませんでした）。",
         "bullets": ["やったこと1"],
         "stats": {"first_ts": "2026-07-17T09:00:00+09:00",
                   "last_ts": "2026-07-17T12:00:00+09:00",
                   "user_turns": 1, "assistant_turns": 1}}]}]}

    out = render.merge_entries(existing, FOO_DIGEST, {})

    pr = out["entries"][0]["projects"][0]
    assert pr["fallback"] is True
    assert pr["bullets"] == ["やったこと1", "やったこと2"]  # 最新の指示で作り直す
