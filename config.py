"""パス・定数・時刻ユーティリティの一元管理。"""
import os
from datetime import datetime
from pathlib import Path

KIROKU_DIR = Path(__file__).resolve().parent

# 要約用の claude -p はこの専用ディレクトリを cwd にして実行する。
# その結果 ~/.claude/projects/ に作られる専用プロジェクトだけを除外することで、
# kiroku 本体の開発記録は報告対象に含めつつ、ツール自身の要約呼び出しは
# レポートに載らないようにする（自己言及ループとノイズの回避）。
SUMMARIZER_CWD = KIROKU_DIR / ".summarizer"


def encode_project_dir(path) -> str:
    """絶対パスを Claude Code の ~/.claude/projects/ 内ディレクトリ名へ符号化する。
    Claude Code は cwd の絶対パスの `/` と `.` をすべて `-` に置換した名前で
    セッションログを保存する。どのユーザー名・配置先でも正しく除外できるよう、
    ハードコードせず実際のパスから計算する。"""
    return str(path).replace("/", "-").replace(".", "-")


# 要約用 cwd に対応する projects ディレクトリ名（環境に依らず自動計算）。
SUMMARIZER_PROJECT_DIR = encode_project_dir(SUMMARIZER_CWD)
EXCLUDE_PROJECT_DIRS = {SUMMARIZER_PROJECT_DIR}

_home = os.environ.get("KIROKU_HOME")
KIROKU_OUT_DIR = Path(_home) if _home else KIROKU_DIR

PROJECTS_DIR = Path(os.environ["KIROKU_PROJECTS_DIR"]) if os.environ.get(
    "KIROKU_PROJECTS_DIR") else (Path.home() / ".claude" / "projects")

ENTRIES_PATH = KIROKU_OUT_DIR / "entries.json"
STATE_PATH = KIROKU_OUT_DIR / "state.json"
HTML_PATH = KIROKU_OUT_DIR / "作業報告書.html"
LOG_PATH = KIROKU_OUT_DIR / "kiroku.log"

# システムのローカルタイムゾーン（JST 前提）
LOCAL_TZ = datetime.now().astimezone().tzinfo

# 要約に失敗した日は state.json の pending_dates に「その日を再要約しようとした
# 実行回数」として記録し、次回以降の実行で対象期間に呼び戻す。
# 何度やっても失敗する日を毎回呼び戻すと claude 呼び出しが無駄に増えるため、
# 回数と経過日数の両方で打ち切る。
PENDING_MAX_RUNS = 3
PENDING_MAX_AGE_DAYS = 14


def parse_ts(s: str) -> datetime:
    """jsonl の ISO タイムスタンプ（末尾 Z 含む）を aware datetime に変換。"""
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def local_date(dt: datetime) -> str:
    """aware datetime をローカル時刻の YYYY-MM-DD 文字列にする。"""
    return dt.astimezone(LOCAL_TZ).strftime("%Y-%m-%d")
