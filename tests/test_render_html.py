from kiroku import render

ENTRIES = {"entries": [
    {"date": "2026-07-18", "projects": [
        {"project": "companion", "summary": "要約B", "bullets": ["b1", "b2"],
         "stats": {"first_ts": "2026-07-18T09:00:00+09:00",
                   "last_ts": "2026-07-18T12:00:00+09:00",
                   "user_turns": 3, "assistant_turns": 5}}]},
    {"date": "2026-07-01", "projects": [
        {"project": "hairsalon", "summary": "要約A", "bullets": ["a1"],
         "stats": {"first_ts": "2026-07-01T10:00:00+09:00",
                   "last_ts": "2026-07-01T11:00:00+09:00",
                   "user_turns": 1, "assistant_turns": 1}}]},
    {"date": "2026-06-20", "projects": [
        {"project": "nuce", "summary": "6月分", "bullets": ["z"],
         "stats": {"first_ts": "2026-06-20T10:00:00+09:00",
                   "last_ts": "2026-06-20T11:00:00+09:00",
                   "user_turns": 1, "assistant_turns": 1}}]}]}


def test_month_anchor_uses_oldest_date_in_month():
    anchors = render.month_anchor_dates(ENTRIES)
    assert anchors["2026-07"] == "2026-07-01"  # 7月の最古
    assert anchors["2026-06"] == "2026-06-20"


def test_render_html_latest_on_top():
    html = render.render_html(ENTRIES)
    assert html.strip().startswith("<!DOCTYPE html>")
    # 2026-07-18 が 2026-07-01 より前（上）に現れる
    assert html.index("2026年7月18日") < html.index("2026年7月1日")


def test_render_html_has_month_nav_and_anchors():
    html = render.render_html(ENTRIES)
    assert 'href="#m-2026-07"' in html
    assert 'href="#m-2026-06"' in html
    assert 'id="m-2026-07"' in html  # 月アンカーが存在


def test_render_html_has_project_headings_and_stats():
    html = render.render_html(ENTRIES)
    assert "companion" in html
    assert "要約B" in html
    assert "b1" in html and "b2" in html
    assert "安藤至大" in html


def test_render_html_escapes_html():
    entries = {"entries": [{"date": "2026-07-18", "projects": [
        {"project": "x", "summary": "<script>bad</script>", "bullets": ["a<b"],
         "stats": {"first_ts": "2026-07-18T09:00:00+09:00",
                   "last_ts": "2026-07-18T09:00:00+09:00",
                   "user_turns": 1, "assistant_turns": 1}}]}]}
    html = render.render_html(entries)
    assert "<script>bad" not in html
    assert "&lt;script&gt;" in html


def test_render_html_handles_null_summary_and_bullets():
    entries = {"entries": [{"date": "2026-07-18", "projects": [
        {"project": "x", "summary": None, "bullets": [None, "ok"],
         "stats": {"first_ts": "2026-07-18T09:00:00+09:00",
                   "last_ts": "2026-07-18T09:00:00+09:00",
                   "user_turns": 1, "assistant_turns": 1}}]}]}
    html = render.render_html(entries)
    assert "ok" in html
