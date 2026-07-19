"""jsonl 走査・抽出・日付×プロジェクト束ね・ダイジェスト生成。"""
import json
from datetime import datetime, timedelta
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
    content = (rec.get("message") or {}).get("content")
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
    content = (rec.get("message") or {}).get("content")
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
        if not isinstance(r, dict):
            continue
        ts_raw = r.get("timestamp")
        if not isinstance(ts_raw, str):
            continue
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


def load_state(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# 初回実行（state なし）でさかのぼる日数。日ごとに claude を呼ぶため、
# 大きすぎると初回の呼び出し回数・所要時間が増える。
FIRST_RUN_DAYS = 2


def _local_midnight(dt: datetime) -> datetime:
    """dt を含むローカル日の 0:00 を返す。"""
    return dt.astimezone(config.LOCAL_TZ).replace(
        hour=0, minute=0, second=0, microsecond=0)


def compute_window(state: dict | None, now: datetime) -> tuple[datetime, datetime]:
    if state and state.get("last_recorded_ts"):
        # 前回記録時刻を含む「日の 0:00」から再スキャンする。こうすると、
        # 同じ日に複数回実行しても、その日の項目は毎回「その日全体」で
        # 作り直されて置換されるため、朝の分が夕方の実行で消えることがない。
        since = _local_midnight(config.parse_ts(state["last_recorded_ts"]))
    else:
        since = _local_midnight(
            now.astimezone(config.LOCAL_TZ) - timedelta(days=FIRST_RUN_DAYS))
    return since, now


def already_recorded_today(state: dict | None, now: datetime) -> bool:
    if not state:
        return False
    return state.get("last_recorded_date") == config.local_date(now)


def _max_activity_ts(digest: dict) -> datetime | None:
    """ダイジェスト内の最も新しい作業時刻（aware datetime）。無ければ None。"""
    latest: datetime | None = None
    for day in digest.get("days", []):
        for pr in day["projects"]:
            t = config.parse_ts(pr["stats"]["last_ts"])
            if latest is None or t > latest:
                latest = t
    return latest


def session_files(projects_dir: Path, exclude: set[str]) -> list[Path]:
    files: list[Path] = []
    if not projects_dir.exists():
        return files
    for child in projects_dir.iterdir():
        if not child.is_dir() or child.name in exclude:
            continue
        files.extend(sorted(child.glob("*.jsonl")))
    return files


def build_digest(now: datetime, state_path: Path = config.STATE_PATH,
                 projects_dir: Path = config.PROJECTS_DIR) -> dict | None:
    """対象期間の作業をダイジェスト化して返す。任意の時間に何度でも呼べる。
    前回記録以降に新しい作業が無ければ None（＝何もしない）を返す。"""
    state = load_state(state_path)
    since, until = compute_window(state, now)
    files = session_files(projects_dir, config.EXCLUDE_PROJECT_DIRS)
    digest = bucket_activity(iter_records(files), since, until)

    last_ts = None
    if state and state.get("last_recorded_ts"):
        last_ts = config.parse_ts(state["last_recorded_ts"])

    if last_ts is not None:
        # 前回記録より後の作業が1件も無ければスキップ（同日再実行でも無駄に
        # 再要約・再表示しない）。
        latest = _max_activity_ts(digest)
        if latest is None or latest <= last_ts:
            return None
    elif not digest["days"]:
        # 初回で対象作業が無ければスキップ。
        return None

    digest["until_ts"] = until.astimezone(config.LOCAL_TZ).isoformat()
    return digest


def main() -> int:
    """ダイジェストを stdout に JSON 出力。記録不要なら空 days で終了コード 0。"""
    now = datetime.now(config.LOCAL_TZ)
    digest = build_digest(now)
    if digest is None:
        print(json.dumps({"days": [], "skipped": True}))
        return 0
    print(json.dumps(digest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
