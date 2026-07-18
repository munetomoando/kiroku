import json
import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # claude-work
KIROKU = ROOT / "kiroku"


def _chmod_x(p: Path):
    p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def test_run_script_end_to_end(tmp_path, monkeypatch):
    # 疑似 projects ディレクトリを用意
    projects = tmp_path / "projects"
    sess = projects / "-Users-munetomoando-claude-work-foo"
    sess.mkdir(parents=True)
    (sess / "s.jsonl").write_text(
        json.dumps({"type": "user", "timestamp": "2026-07-17T01:00:00.000Z",
                    "cwd": "/Users/munetomoando/claude-work/foo",
                    "isSidechain": False,
                    "message": {"role": "user", "content": "テスト指示"}}) + "\n",
        encoding="utf-8")

    # config のパスを一時ディレクトリへ向ける
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["KIROKU_CLAUDE_BIN"] = str(KIROKU / "tests" / "fake_claude.sh")
    env["KIROKU_PYTHON"] = "/Users/munetomoando/claude-work/kiroku/.venv/bin/python"
    # gather/render が参照するパスを環境変数で上書きできるようにしてある前提
    env["KIROKU_PROJECTS_DIR"] = str(projects)
    env["KIROKU_HOME"] = str(tmp_path)  # entries/state/html をここへ
    env["KIROKU_OPEN"] = "0"  # テスト中はブラウザを開かない

    _chmod_x(KIROKU / "run-kiroku.sh")
    _chmod_x(KIROKU / "tests" / "fake_claude.sh")

    subprocess.run(["bash", str(KIROKU / "run-kiroku.sh")],
                   env=env, check=True, cwd=str(tmp_path))

    # HTML が生成され、プロジェクト見出しと日付が入っていること（構造の確認）。
    # fake_claude の要約キーは実日付/実プロジェクトと一致しないため要約文は空でよい。
    # 要約が空でも entries.json は追記され HTML は生成される。
    html = (tmp_path / "作業報告書.html").read_text(encoding="utf-8")
    assert "foo" in html          # プロジェクト見出し
    assert "2026年7月17日" in html  # 対象日
    assert (tmp_path / "state.json").exists()
