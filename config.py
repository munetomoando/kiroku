"""パス・定数・時刻ユーティリティの一元管理。"""
from datetime import datetime
from pathlib import Path

KIROKU_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = Path.home() / ".claude" / "projects"

# kiroku 自身のセッションディレクトリ名は報告対象から除外
EXCLUDE_PROJECT_DIRS = {"-Users-munetomoando-claude-work-kiroku"}

ENTRIES_PATH = KIROKU_DIR / "entries.json"
STATE_PATH = KIROKU_DIR / "state.json"
HTML_PATH = KIROKU_DIR / "作業報告書.html"
LOG_PATH = KIROKU_DIR / "kiroku.log"

AUTHOR = "安藤至大"

# システムのローカルタイムゾーン（JST 前提）
LOCAL_TZ = datetime.now().astimezone().tzinfo


def parse_ts(s: str) -> datetime:
    """jsonl の ISO タイムスタンプ（末尾 Z 含む）を aware datetime に変換。"""
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def local_date(dt: datetime) -> str:
    """aware datetime をローカル時刻の YYYY-MM-DD 文字列にする。"""
    return dt.astimezone(LOCAL_TZ).strftime("%Y-%m-%d")
