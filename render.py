"""entries.json 追記と HTML 全再生成、state 更新。"""
import json
import os
from pathlib import Path

from kiroku import config


def load_entries(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"entries": []}


def atomic_write_json(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def merge_entries(existing: dict, digest: dict, summary: dict) -> dict:
    """digest の統計と summary を突き合わせて新エントリを作り、日付降順でマージ。"""
    by_date = {e["date"]: e for e in existing.get("entries", [])}
    for day in digest.get("days", []):
        date = day["date"]
        projects = []
        for pr in day["projects"]:
            proj = pr["project"]
            s = summary.get(date, {}).get(proj, {})
            projects.append({
                "project": proj,
                "summary": s.get("summary", ""),
                "bullets": s.get("bullets", []),
                "stats": pr["stats"],
            })
        by_date[date] = {"date": date, "projects": projects}
    entries = sorted(by_date.values(), key=lambda e: e["date"], reverse=True)
    return {"entries": entries}


def update_state(path: Path, until_ts: str, today: str) -> None:
    atomic_write_json(path, {"last_recorded_ts": until_ts,
                             "last_recorded_date": today})
