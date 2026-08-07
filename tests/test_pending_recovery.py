"""要約に失敗した日が後日の実行で回復するまで（gather → summarize → render）。

2026-08-06 の profile は、その日の最後の実行で要約に失敗し、日付が変わった
時点で対象期間から外れて二度と要約されなかった。この結合テストは
「失敗 → state に記録 → 後日の実行で呼び戻して回復」の一巡を確かめる。
"""
import json
import re
from datetime import datetime, timezone

from kiroku import config, gather, render, summarize

JST = config.LOCAL_TZ


def _echoing_runner(fail_dates=()):
    """プロンプト中の日付・プロジェクト名をそのまま返す疑似 claude。
    fail_dates に挙げた日だけ失敗する。"""
    def runner(claude_bin, prompt_text):
        m = re.search(r"^## (\d{4}-\d{2}-\d{2})$", prompt_text, re.M)
        assert m, "プロンプトに日付が無い"
        date = m.group(1)
        if date in fail_dates:
            return None
        projects = re.findall(r"^### プロジェクト: (.+)$", prompt_text, re.M)
        return json.dumps({date: {p: {"summary": f"{date} の要約",
                                      "bullets": ["b"]} for p in projects}})
    return runner


def _write_record(path, dt, text):
    ts = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    line = json.dumps({"type": "user", "timestamp": ts,
                       "cwd": "/Users/munetomoando/claude-work/foo",
                       "isSidechain": False,
                       "message": {"role": "user", "content": text}})
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _run(now, paths, fail_dates=()):
    """1 回分の実行（ダイジェスト → 要約 → 書き出し）。何もしなければ None。"""
    digest = gather.build_digest(now, state_path=paths["state"],
                                 projects_dir=paths["projects"])
    if digest is None:
        return None
    summary = summarize.summarize_digest(
        digest, "claude", runner=_echoing_runner(fail_dates), wait_sec=0)
    render.write_report(digest, summary, entries_path=paths["entries"],
                        html_path=paths["html"], state_path=paths["state"])
    return digest


def _paths(tmp_path):
    projects = tmp_path / "projects"
    sess = projects / "-Users-munetomoando-claude-work-foo"
    sess.mkdir(parents=True)
    for day, text in ((17, "17日の作業"), (18, "18日の作業"), (19, "19日の作業")):
        _write_record(sess / "s.jsonl",
                      datetime(2026, 7, day, 10, 0, tzinfo=JST), text)
    return {"projects": projects, "state": tmp_path / "state.json",
            "entries": tmp_path / "entries.json", "html": tmp_path / "r.html"}


def _state(paths):
    return json.loads(paths["state"].read_text(encoding="utf-8"))


def _summary_of(paths, date):
    entries = json.loads(paths["entries"].read_text(encoding="utf-8"))
    entry = {e["date"]: e for e in entries["entries"]}[date]
    return entry["projects"][0]["summary"]


def test_failed_day_is_recovered_by_a_later_run(tmp_path):
    paths = _paths(tmp_path)

    # 1 回目（7/17 夜）: 7/17 の要約に失敗 → プレースホルダ＋再要約待ちに記録
    _run(datetime(2026, 7, 17, 23, 0, tzinfo=JST), paths, fail_dates={"2026-07-17"})
    assert _state(paths)["pending_dates"] == {"2026-07-17": 1}
    assert "自動要約なし" in _summary_of(paths, "2026-07-17")

    # 2 回目（7/18 夜）: 7/17 はまだ失敗、7/18 は成功
    _run(datetime(2026, 7, 18, 23, 0, tzinfo=JST), paths, fail_dates={"2026-07-17"})
    assert _state(paths)["pending_dates"] == {"2026-07-17": 2}
    assert _summary_of(paths, "2026-07-18") == "2026-07-18 の要約"

    # 3 回目（7/19 夜）: 通常の対象期間は 7/18 以降だが、7/17 が呼び戻されて回復
    digest = _run(datetime(2026, 7, 19, 23, 0, tzinfo=JST), paths)
    assert "2026-07-17" in [d["date"] for d in digest["days"]]
    assert _summary_of(paths, "2026-07-17") == "2026-07-17 の要約"
    assert _state(paths)["pending_dates"] == {}


def test_recovered_day_is_not_resummarized_again(tmp_path):
    # 回復した日は pending から消え、以降の実行で claude を呼ばれない。
    paths = _paths(tmp_path)
    _run(datetime(2026, 7, 17, 23, 0, tzinfo=JST), paths, fail_dates={"2026-07-17"})
    _run(datetime(2026, 7, 18, 23, 0, tzinfo=JST), paths)  # ここで 7/17 も回復
    assert _state(paths)["pending_dates"] == {}

    digest = gather.build_digest(datetime(2026, 7, 19, 23, 0, tzinfo=JST),
                                 state_path=paths["state"],
                                 projects_dir=paths["projects"])
    dates = [d["date"] for d in digest["days"] if d["needs_summary"]]
    assert "2026-07-17" not in dates


def test_hopeless_day_is_abandoned_after_max_runs(tmp_path):
    # 何度やっても失敗する日を毎回呼び戻し続けない。
    paths = _paths(tmp_path)
    always_fail = {"2026-07-17"}
    _run(datetime(2026, 7, 17, 23, 0, tzinfo=JST), paths, fail_dates=always_fail)
    _run(datetime(2026, 7, 18, 23, 0, tzinfo=JST), paths, fail_dates=always_fail)
    assert _state(paths)["pending_dates"] == {"2026-07-17": 2}

    _run(datetime(2026, 7, 19, 23, 0, tzinfo=JST), paths, fail_dates=always_fail)
    assert _state(paths)["pending_dates"] == {}  # 諦める（呼び戻しは止まる）
    assert "自動要約なし" in _summary_of(paths, "2026-07-17")
