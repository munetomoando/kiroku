"""デモデータ生成スクリプトのテスト。"""
import importlib.util
from pathlib import Path

from kiroku import config

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_seed_demo():
    """docs/demo/seed_demo.py はパッケージ外なのでパスから直接読み込む。"""
    path = REPO_ROOT / "docs" / "demo" / "seed_demo.py"
    spec = importlib.util.spec_from_file_location("seed_demo", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_entries_span_multiple_months():
    """月ボタンと年グループが写るよう、2 か月以上にまたがる必要がある。"""
    mod = _load_seed_demo()
    entries = mod.build_demo_entries()["entries"]
    months = {e["date"][:7] for e in entries}
    assert len(months) >= 2, f"月が {months} の 1 種類しかない"


def test_entries_are_date_descending():
    """render_html は日付降順を前提にしている。"""
    mod = _load_seed_demo()
    dates = [e["date"] for e in mod.build_demo_entries()["entries"]]
    assert dates == sorted(dates, reverse=True)


def test_enough_days_to_look_stacked():
    """「積み上がる」ことが伝わるよう 4 日分以上。"""
    mod = _load_seed_demo()
    assert len(mod.build_demo_entries()["entries"]) >= 4


def test_only_fictional_project_names():
    """実在のプロジェクト名が紛れ込んでいないこと。"""
    mod = _load_seed_demo()
    used = {p["project"]
            for e in mod.build_demo_entries()["entries"]
            for p in e["projects"]}
    assert used <= set(mod.DEMO_PROJECTS), f"想定外の名前: {used - set(mod.DEMO_PROJECTS)}"


def test_every_project_has_summary_and_bullets():
    mod = _load_seed_demo()
    for e in mod.build_demo_entries()["entries"]:
        assert e["projects"], f"{e['date']} にプロジェクトがない"
        for p in e["projects"]:
            assert p["summary"].strip()
            assert len(p["bullets"]) >= 3
            assert set(p["stats"]) == {
                "first_ts", "last_ts", "user_turns", "assistant_turns"}


def test_renders_html_to_given_path(tmp_path):
    """CLI 相当の write_demo_html が指定パスにだけ書くこと。"""
    mod = _load_seed_demo()
    out = tmp_path / "demo.html"
    before = {p: p.stat().st_mtime_ns for p in
              (config.ENTRIES_PATH, config.STATE_PATH, config.HTML_PATH) if p.exists()}
    mod.write_demo_html(out)
    html = out.read_text(encoding="utf-8")
    assert "<title>作業報告書</title>" in html
    assert 'class="month-btn"' in html
    assert list(tmp_path.iterdir()) == [out], "指定パス以外にも書き出している"
    assert {p: p.stat().st_mtime_ns for p in before} == before, \
        "実データ（entries.json / state.json / 作業報告書.html）に触れている"
