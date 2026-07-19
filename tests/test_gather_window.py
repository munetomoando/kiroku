import json
from datetime import datetime, timedelta, timezone
from kiroku import gather, config

UTC = timezone.utc


def test_load_state_missing_returns_none(tmp_path):
    assert gather.load_state(tmp_path / "nope.json") is None


def test_compute_window_first_run_is_2_days(tmp_path):
    now = datetime(2026, 7, 18, 10, 0, tzinfo=config.LOCAL_TZ)
    since, until = gather.compute_window(None, now)
    # 2 日前のローカル 0:00
    assert since.strftime("%Y-%m-%d") == "2026-07-16"
    assert since.hour == 0 and since.minute == 0
    assert until == now


def test_compute_window_uses_last_recorded_day_midnight():
    # 前回記録時刻を含む「日の 0:00」から再スキャンする。
    now = datetime(2026, 7, 18, 10, 0, tzinfo=config.LOCAL_TZ)
    state = {"last_recorded_ts": "2026-07-17T05:00:00+00:00",  # = 07-17 14:00 JST
             "last_recorded_date": "2026-07-17"}
    since, until = gather.compute_window(state, now)
    assert config.local_date(since) == "2026-07-17"
    assert since.astimezone(config.LOCAL_TZ).hour == 0
    assert since.astimezone(config.LOCAL_TZ).minute == 0


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


def test_build_digest_no_work_returns_none(tmp_path):
    # 対象作業が1件も無ければ None。
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"last_recorded_date": "2026-07-18",
                                      "last_recorded_ts": "2026-07-18T00:00:00+00:00"}))
    now = datetime(2026, 7, 18, 10, 0, tzinfo=config.LOCAL_TZ)
    assert gather.build_digest(now, state_path=state_path,
                               projects_dir=tmp_path) is None


def _write_user_record(path, dt_jst, text="作業", cwd="/Users/munetomoando/claude-work/foo"):
    """指定した JST 日時のユーザーレコードを jsonl に1行追記する。"""
    ts = dt_jst.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    line = json.dumps({"type": "user", "timestamp": ts, "cwd": cwd,
                       "isSidechain": False,
                       "message": {"role": "user", "content": text}})
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def test_build_digest_same_day_rerun_consolidates_full_day(tmp_path):
    # 朝(09:00)に記録済み。その後さらに作業(08:00は既存, 11:00が新規)。
    # 同じ日に再実行すると、当日の 0:00 から再スキャンし、当日分をまとめて返す。
    jst = config.LOCAL_TZ
    projects = tmp_path / "projects"
    sess = projects / "-Users-munetomoando-claude-work-foo"
    sess.mkdir(parents=True)
    f = sess / "s.jsonl"
    _write_user_record(f, datetime(2026, 7, 18, 8, 0, tzinfo=jst), "朝の作業")
    _write_user_record(f, datetime(2026, 7, 18, 11, 0, tzinfo=jst), "昼の新しい作業")

    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(
        {"last_recorded_ts": "2026-07-18T09:00:00+09:00",
         "last_recorded_date": "2026-07-18"}))
    now = datetime(2026, 7, 18, 18, 0, tzinfo=jst)

    digest = gather.build_digest(now, state_path=state_path, projects_dir=projects)
    assert digest is not None                       # 新しい作業(11:00)があるので実行される
    day = digest["days"][0]
    assert day["date"] == "2026-07-18"
    stats = day["projects"][0]["stats"]
    # 当日 0:00 から再スキャンしたので、朝(08:00)の作業も同じ当日項目に含まれる
    assert config.parse_ts(stats["first_ts"]).astimezone(jst).hour == 8
    assert stats["user_turns"] == 2


def test_build_digest_no_new_work_returns_none(tmp_path):
    # 前回記録(12:00)より後の作業が無ければ、同日再実行でも None（何もしない）。
    jst = config.LOCAL_TZ
    projects = tmp_path / "projects"
    sess = projects / "-Users-munetomoando-claude-work-foo"
    sess.mkdir(parents=True)
    _write_user_record(sess / "s.jsonl",
                       datetime(2026, 7, 18, 9, 0, tzinfo=jst), "記録済みの作業")

    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(
        {"last_recorded_ts": "2026-07-18T12:00:00+09:00",
         "last_recorded_date": "2026-07-18"}))
    now = datetime(2026, 7, 18, 18, 0, tzinfo=jst)

    assert gather.build_digest(now, state_path=state_path,
                               projects_dir=projects) is None


def test_build_digest_happy_path_returns_digest(tmp_path):
    # state なし → 過去2日が対象。projects に実セッションを1件置く。
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
