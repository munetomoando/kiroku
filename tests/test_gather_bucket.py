from datetime import datetime, timezone
from kiroku import gather

UTC = timezone.utc


def rec(t, role, text, cwd="/Users/munetomoando/claude-work/foo", side=False):
    if role == "user":
        msg = {"role": "user", "content": text}
    else:
        msg = {"role": "assistant", "content": [{"type": "text", "text": text}]}
    return {"type": role, "timestamp": t, "cwd": cwd, "isSidechain": side,
            "message": msg}


def test_bucket_groups_by_date_and_project():
    records = [
        rec("2026-07-17T01:00:00.000Z", "user", "タスクA"),
        rec("2026-07-17T01:05:00.000Z", "assistant", "Aやった"),
        rec("2026-07-18T02:00:00.000Z", "user", "タスクB",
            cwd="/Users/munetomoando/claude-work/bar"),
    ]
    since = datetime(2026, 7, 1, tzinfo=UTC)
    until = datetime(2026, 7, 30, tzinfo=UTC)
    out = gather.bucket_activity(records, since, until)
    dates = [d["date"] for d in out["days"]]
    assert dates == ["2026-07-17", "2026-07-18"]
    day0 = out["days"][0]
    assert day0["projects"][0]["project"] == "foo"
    assert day0["projects"][0]["prompts"] == ["タスクA"]
    assert day0["projects"][0]["highlights"] == ["Aやった"]
    assert day0["projects"][0]["stats"]["user_turns"] == 1
    assert day0["projects"][0]["stats"]["assistant_turns"] == 1


def test_bucket_respects_since_until_window():
    records = [
        rec("2026-06-01T00:00:00.000Z", "user", "古い"),
        rec("2026-07-17T01:00:00.000Z", "user", "対象内"),
    ]
    since = datetime(2026, 7, 1, tzinfo=UTC)
    until = datetime(2026, 7, 30, tzinfo=UTC)
    out = gather.bucket_activity(records, since, until)
    all_prompts = [p for d in out["days"] for pr in d["projects"] for p in pr["prompts"]]
    assert "古い" not in all_prompts
    assert "対象内" in all_prompts
