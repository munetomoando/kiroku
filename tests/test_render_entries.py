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


def test_update_state_writes_date_and_ts(tmp_path):
    p = tmp_path / "state.json"
    render.update_state(p, "2026-07-18T10:00:00+09:00", "2026-07-18")
    data = json.loads(p.read_text())
    assert data["last_recorded_ts"] == "2026-07-18T10:00:00+09:00"
    assert data["last_recorded_date"] == "2026-07-18"
