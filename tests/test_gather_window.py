import json
from datetime import datetime, timedelta, timezone
from kiroku import gather, config

UTC = timezone.utc


def test_load_state_missing_returns_none(tmp_path):
    assert gather.load_state(tmp_path / "nope.json") is None


def test_compute_window_first_run_is_30_days(tmp_path):
    now = datetime(2026, 7, 18, 10, 0, tzinfo=config.LOCAL_TZ)
    since, until = gather.compute_window(None, now)
    # 30 日前のローカル 0:00
    assert since.strftime("%Y-%m-%d") == "2026-06-18"
    assert since.hour == 0 and since.minute == 0
    assert until == now


def test_compute_window_uses_last_recorded_ts():
    now = datetime(2026, 7, 18, 10, 0, tzinfo=config.LOCAL_TZ)
    state = {"last_recorded_ts": "2026-07-17T05:00:00+00:00",
             "last_recorded_date": "2026-07-17"}
    since, until = gather.compute_window(state, now)
    assert since == config.parse_ts("2026-07-17T05:00:00+00:00")


def test_already_recorded_today():
    now = datetime(2026, 7, 18, 10, 0, tzinfo=config.LOCAL_TZ)
    assert gather.already_recorded_today(
        {"last_recorded_date": "2026-07-18"}, now) is True
    assert gather.already_recorded_today(
        {"last_recorded_date": "2026-07-17"}, now) is False
    assert gather.already_recorded_today(None, now) is False


def test_session_files_excludes_kiroku(tmp_path):
    (tmp_path / "-Users-munetomoando-claude-work-kiroku").mkdir()
    (tmp_path / "-Users-munetomoando-claude-work-kiroku" / "a.jsonl").write_text("{}")
    (tmp_path / "-Users-munetomoando-claude-work-foo").mkdir()
    good = tmp_path / "-Users-munetomoando-claude-work-foo" / "b.jsonl"
    good.write_text("{}")
    files = gather.session_files(tmp_path, config.EXCLUDE_PROJECT_DIRS)
    assert good in files
    assert all("kiroku" not in str(f) for f in files)


def test_build_digest_guard_returns_none(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"last_recorded_date": "2026-07-18",
                                      "last_recorded_ts": "2026-07-18T00:00:00+00:00"}))
    now = datetime(2026, 7, 18, 10, 0, tzinfo=config.LOCAL_TZ)
    assert gather.build_digest(now, state_path=state_path,
                               projects_dir=tmp_path) is None


def test_build_digest_happy_path_returns_digest(tmp_path):
    # state なし → 過去30日が対象。projects に実セッションを1件置く。
    projects = tmp_path / "projects"
    sess = projects / "-Users-munetomoando-claude-work-foo"
    sess.mkdir(parents=True)
    now = datetime(2026, 7, 18, 10, 0, tzinfo=config.LOCAL_TZ)
    recent = (now - timedelta(days=1)).astimezone(timezone.utc)
    ts = recent.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    (sess / "s.jsonl").write_text(
        json.dumps({
            "type": "user", "timestamp": ts,
            "cwd": "/Users/munetomoando/claude-work/foo",
            "isSidechain": False,
            "message": {"role": "user", "content": "テスト指示"}}) + "\n",
        encoding="utf-8")
    state_path = tmp_path / "state.json"  # 存在しない
    digest = gather.build_digest(now, state_path=state_path, projects_dir=projects)
    assert digest is not None
    assert "until_ts" in digest
    assert any(d["projects"] for d in digest["days"])
