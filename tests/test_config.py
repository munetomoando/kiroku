from datetime import datetime, timezone
from kiroku import config


def test_paths_under_kiroku_dir():
    assert config.KIROKU_DIR.name == "kiroku"
    assert config.ENTRIES_PATH == config.KIROKU_DIR / "entries.json"
    assert config.STATE_PATH == config.KIROKU_DIR / "state.json"
    assert config.HTML_PATH == config.KIROKU_DIR / "作業報告書.html"


def test_encode_project_dir_replaces_slash_and_dot():
    # Claude Code は cwd の絶対パスの `/` と `.` を `-` に置換した名前で保存する。
    enc = config.encode_project_dir("/Users/foo/claude-work/kiroku/.summarizer")
    assert enc == "-Users-foo-claude-work-kiroku--summarizer"


def test_kiroku_included_but_summarizer_excluded():
    # kiroku 本体の開発記録は含める。除外するのは要約用の専用プロジェクトだけ。
    # ユーザー名・配置先に依らず、実際のパスから符号化した名前で判定する。
    kiroku_dir_enc = config.encode_project_dir(config.KIROKU_DIR)
    assert kiroku_dir_enc not in config.EXCLUDE_PROJECT_DIRS
    assert config.SUMMARIZER_PROJECT_DIR in config.EXCLUDE_PROJECT_DIRS
    assert config.SUMMARIZER_PROJECT_DIR == config.encode_project_dir(
        config.KIROKU_DIR / ".summarizer")
    assert config.SUMMARIZER_CWD == config.KIROKU_DIR / ".summarizer"


def test_parse_ts_returns_aware_datetime():
    dt = config.parse_ts("2026-07-17T00:30:00.000Z")
    assert dt.tzinfo is not None
    assert dt.astimezone(timezone.utc).hour == 0


def test_local_date_converts_utc_to_local():
    # 2026-07-17T16:00Z は JST では 2026-07-18 01:00
    dt = config.parse_ts("2026-07-17T16:00:00.000Z")
    # ローカルが JST の環境で YYYY-MM-DD が繰り上がることを確認
    assert config.local_date(dt) in ("2026-07-17", "2026-07-18")
