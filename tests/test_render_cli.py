import json
from kiroku import config, render

DIGEST = {"until_ts": "2026-07-18T10:00:00+09:00", "days": [
    {"date": "2026-07-17", "projects": [
        {"project": "companion", "prompts": ["やって"], "highlights": [],
         "stats": {"first_ts": "2026-07-17T09:00:00+09:00",
                   "last_ts": "2026-07-17T18:00:00+09:00",
                   "user_turns": 1, "assistant_turns": 2}}]}]}


def test_write_report_creates_all_files(tmp_path):
    ep, hp, sp = tmp_path / "e.json", tmp_path / "r.html", tmp_path / "s.json"
    summary = {"2026-07-17": {"companion": {"summary": "S", "bullets": ["B"]}}}
    render.write_report(DIGEST, summary, entries_path=ep, html_path=hp, state_path=sp)
    assert json.loads(ep.read_text())["entries"][0]["date"] == "2026-07-17"
    assert "S" in hp.read_text()
    assert json.loads(sp.read_text())["last_recorded_date"] == "2026-07-18"


def test_write_report_uses_fallback_when_summary_empty(tmp_path):
    ep, hp, sp = tmp_path / "e.json", tmp_path / "r.html", tmp_path / "s.json"
    render.write_report(DIGEST, {}, entries_path=ep, html_path=hp, state_path=sp)
    html = hp.read_text()
    assert "やって" in html  # fallback で prompts が箇条書きに出る


def test_write_report_appends_to_existing(tmp_path):
    ep, hp, sp = tmp_path / "e.json", tmp_path / "r.html", tmp_path / "s.json"
    ep.write_text(json.dumps({"entries": [
        {"date": "2026-07-10", "projects": []}]}, ensure_ascii=False))
    render.write_report(DIGEST, {}, entries_path=ep, html_path=hp, state_path=sp)
    dates = [e["date"] for e in json.loads(ep.read_text())["entries"]]
    assert dates == ["2026-07-17", "2026-07-10"]


def test_write_report_recovers_from_null_summary_on_next_day(tmp_path):
    ep, hp, sp = tmp_path / "e.json", tmp_path / "r.html", tmp_path / "s.json"
    bad_summary = {"2026-07-17": {"companion": {"summary": None, "bullets": None}}}
    render.write_report(DIGEST, bad_summary, entries_path=ep, html_path=hp, state_path=sp)

    digest2 = {"until_ts": "2026-07-19T10:00:00+09:00", "days": [
        {"date": "2026-07-18", "projects": [
            {"project": "companion", "prompts": ["y"], "highlights": [],
             "stats": {"first_ts": "2026-07-18T09:00:00+09:00",
                       "last_ts": "2026-07-18T18:00:00+09:00",
                       "user_turns": 1, "assistant_turns": 2}}]}]}
    good_summary = {"2026-07-18": {"companion": {"summary": "OK", "bullets": ["good"]}}}
    render.write_report(digest2, good_summary, entries_path=ep, html_path=hp, state_path=sp)

    assert hp.exists()
    html = hp.read_text()
    assert "2026年7月18日" in html
    dates = [e["date"] for e in json.loads(ep.read_text())["entries"]]
    assert dates == ["2026-07-18", "2026-07-17"]


# --- 失敗した日を state.json に覚えて再要約させる --------------------------

def _state(sp):
    return json.loads(sp.read_text(encoding="utf-8"))


def test_write_report_records_failed_date_as_pending(tmp_path):
    ep, hp, sp = tmp_path / "e.json", tmp_path / "r.html", tmp_path / "s.json"
    render.write_report(DIGEST, {}, entries_path=ep, html_path=hp, state_path=sp)
    assert _state(sp)["pending_dates"] == {"2026-07-17": 1}


def test_write_report_counts_repeated_failures(tmp_path):
    ep, hp, sp = tmp_path / "e.json", tmp_path / "r.html", tmp_path / "s.json"
    sp.write_text(json.dumps({"pending_dates": {"2026-07-17": 1}}))
    render.write_report(DIGEST, {}, entries_path=ep, html_path=hp, state_path=sp)
    assert _state(sp)["pending_dates"] == {"2026-07-17": 2}


def test_write_report_clears_pending_when_summary_succeeds(tmp_path):
    ep, hp, sp = tmp_path / "e.json", tmp_path / "r.html", tmp_path / "s.json"
    sp.write_text(json.dumps({"pending_dates": {"2026-07-17": 1}}))
    summary = {"2026-07-17": {"companion": {"summary": "S", "bullets": ["B"]}}}
    render.write_report(DIGEST, summary, entries_path=ep, html_path=hp, state_path=sp)
    assert _state(sp)["pending_dates"] == {}


def test_write_report_gives_up_after_max_runs(tmp_path):
    # 何度やっても失敗する日を永久に呼び戻し続けない。
    ep, hp, sp = tmp_path / "e.json", tmp_path / "r.html", tmp_path / "s.json"
    sp.write_text(json.dumps(
        {"pending_dates": {"2026-07-17": config.PENDING_MAX_RUNS - 1}}))
    render.write_report(DIGEST, {}, entries_path=ep, html_path=hp, state_path=sp)
    assert _state(sp)["pending_dates"] == {}


def test_write_report_does_not_pend_days_it_did_not_summarize(tmp_path):
    # needs_summary=False の日は claude を呼んでいないので、フォールバックの
    # ままでも「今回失敗した日」とは数えない。
    ep, hp, sp = tmp_path / "e.json", tmp_path / "r.html", tmp_path / "s.json"
    digest = json.loads(json.dumps(DIGEST))
    digest["days"][0]["needs_summary"] = False
    render.write_report(digest, {}, entries_path=ep, html_path=hp, state_path=sp)
    assert _state(sp)["pending_dates"] == {}
