"""jsonl 走査・抽出・日付×プロジェクト束ね・ダイジェスト生成。"""
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

from kiroku import config

MAX_PROMPTS = 20
MAX_HIGHLIGHTS = 20


def iter_records(paths: list[Path]) -> Iterator[dict]:
    """複数の jsonl を 1 行ずつ parse。壊れた行はスキップ。"""
    for p in paths:
        try:
            fh = p.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def project_name(rec: dict) -> str:
    """cwd の basename をプロジェクト名にする。"""
    cwd = rec.get("cwd")
    if cwd:
        return Path(cwd).name
    return "unknown"


def user_prompt_text(rec: dict) -> str | None:
    """本物のユーザー指示テキストのみ返す。ツール結果・サイドチェーンは None。"""
    if rec.get("type") != "user":
        return None
    if rec.get("isSidechain"):
        return None
    content = rec.get("message", {}).get("content")
    if isinstance(content, str):
        text = content.strip()
        return text or None
    if isinstance(content, list):
        # tool_result などが含まれるユーザーメッセージは指示ではない
        parts = [b.get("text", "") for b in content
                 if isinstance(b, dict) and b.get("type") == "text"]
        joined = "".join(parts).strip()
        return joined or None
    return None


def assistant_texts(rec: dict) -> list[str]:
    """assistant message の text ブロックのみ抽出。"""
    if rec.get("type") != "assistant":
        return []
    content = rec.get("message", {}).get("content")
    if not isinstance(content, list):
        return []
    out = []
    for b in content:
        if isinstance(b, dict) and b.get("type") == "text":
            t = b.get("text", "").strip()
            if t:
                out.append(t)
    return out


def bucket_activity(records: Iterable[dict], since: datetime,
                    until: datetime) -> dict:
    """レコード群を date(local)×project で束ね、統計付きダイジェストを返す。"""
    # days[date][project] = activity dict
    days: dict[str, dict[str, dict]] = {}
    order: dict[str, list[str]] = {}  # date -> project 初出順

    for r in records:
        ts_raw = r.get("timestamp")
        if not ts_raw:
            continue
        try:
            ts = config.parse_ts(ts_raw)
        except (ValueError, TypeError):
            continue
        if not (since <= ts < until):
            continue
        typ = r.get("type")
        if typ not in ("user", "assistant"):
            continue

        date = config.local_date(ts)
        proj = project_name(r)
        day = days.setdefault(date, {})
        order.setdefault(date, [])
        if proj not in day:
            day[proj] = {"prompts": [], "highlights": [],
                         "first_ts": ts, "last_ts": ts,
                         "user_turns": 0, "assistant_turns": 0}
            order[date].append(proj)
        act = day[proj]
        act["first_ts"] = min(act["first_ts"], ts)
        act["last_ts"] = max(act["last_ts"], ts)

        if typ == "user":
            text = user_prompt_text(r)
            if text is not None:
                act["user_turns"] += 1
                if len(act["prompts"]) < MAX_PROMPTS:
                    act["prompts"].append(text)
        else:  # assistant
            act["assistant_turns"] += 1
            for t in assistant_texts(r):
                if len(act["highlights"]) < MAX_HIGHLIGHTS:
                    act["highlights"].append(t)

    out_days = []
    for date in sorted(days):
        projects = []
        for proj in order[date]:
            act = days[date][proj]
            projects.append({
                "project": proj,
                "prompts": act["prompts"],
                "highlights": act["highlights"],
                "stats": {
                    "first_ts": act["first_ts"].astimezone(config.LOCAL_TZ).isoformat(),
                    "last_ts": act["last_ts"].astimezone(config.LOCAL_TZ).isoformat(),
                    "user_turns": act["user_turns"],
                    "assistant_turns": act["assistant_turns"],
                },
            })
        out_days.append({"date": date, "projects": projects})
    return {"days": out_days}
