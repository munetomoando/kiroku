import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from kiroku import config

KIROKU = Path(__file__).resolve().parents[1]  # kiroku リポジトリのルート
ROOT = KIROKU.parent                          # `import kiroku` 用の親（PYTHONPATH）


def _chmod_x(p: Path):
    p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def test_run_script_end_to_end(tmp_path, monkeypatch):
    # 疑似 projects ディレクトリを用意
    projects = tmp_path / "projects"
    sess = projects / "-Users-munetomoando-claude-work-foo"
    sess.mkdir(parents=True)
    # 初回 2 日窓に確実に入るよう、記録は「2 時間前」の相対時刻にする
    # （固定日だとカレンダーが進むと窓から外れてしまうため）。
    rec_dt = datetime.now(timezone.utc) - timedelta(hours=2)
    ts = rec_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    local = rec_dt.astimezone(config.LOCAL_TZ)
    expected_ja = f"{local.year}年{local.month}月{local.day}日"
    (sess / "s.jsonl").write_text(
        json.dumps({"type": "user", "timestamp": ts,
                    "cwd": "/Users/munetomoando/claude-work/foo",
                    "isSidechain": False,
                    "message": {"role": "user", "content": "テスト指示"}}) + "\n",
        encoding="utf-8")

    # config のパスを一時ディレクトリへ向ける
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["KIROKU_CLAUDE_BIN"] = str(KIROKU / "tests" / "fake_claude.sh")
    env["KIROKU_PYTHON"] = sys.executable  # テストを実行中の Python（環境非依存）
    # gather/render が参照するパスを環境変数で上書きできるようにしてある前提
    env["KIROKU_PROJECTS_DIR"] = str(projects)
    env["KIROKU_HOME"] = str(tmp_path)  # entries/state/html をここへ
    env["KIROKU_OPEN"] = "0"  # テスト中はブラウザを開かない

    _chmod_x(KIROKU / "run-kiroku.sh")
    _chmod_x(KIROKU / "tests" / "fake_claude.sh")

    subprocess.run(["bash", str(KIROKU / "run-kiroku.sh")],
                   env=env, check=True, cwd=str(tmp_path))

    # HTML が生成され、見出し・日付に加えて要約本文まで反映されていること。
    html = (tmp_path / "作業報告書.html").read_text(encoding="utf-8")
    assert "foo" in html          # プロジェクト見出し
    assert expected_ja in html    # 対象日（相対時刻から算出）
    assert "テスト要約" in html   # 要約が entries.json 経由で HTML に載る
    assert "自動要約なし" not in html  # フォールバックに落ちていない
    assert (tmp_path / "state.json").exists()


def test_wakeup_via_symlink_resolves_real_script(tmp_path):
    # sleepwatcher は ~/.wakeup（wakeup.sh へのシンボリックリンク）として実行する。
    # その場合 $0 はリンク側のパスになるため、dirname "$0" では実体の場所を
    # 見失う。リンクをたどって本物の run-kiroku.sh を起動できること。
    link = tmp_path / ".wakeup"
    link.symlink_to(KIROKU / "wakeup.sh")
    _chmod_x(KIROKU / "wakeup.sh")

    projects = tmp_path / "projects"
    projects.mkdir()  # 空 → 記録対象なしで正常終了するはず

    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["KIROKU_PYTHON"] = sys.executable
    env["KIROKU_PROJECTS_DIR"] = str(projects)
    env["KIROKU_HOME"] = str(tmp_path)
    env["KIROKU_OPEN"] = "0"
    env["KIROKU_WAKE_DELAY"] = "0"  # テストでは復帰待ちを省略

    result = subprocess.run([str(link)], env=env, cwd=str(tmp_path),
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def _auto_run_env(tmp_path, projects):
    """自動実行テスト用の共通環境（open を偽物に差し替えて表示検出）。"""
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    open_log = tmp_path / "open_called.log"
    fake_open = fakebin / "open"
    fake_open.write_text(f'#!/usr/bin/env bash\necho "$@" >> "{open_log}"\n',
                         encoding="utf-8")
    _chmod_x(fake_open)
    env = dict(os.environ)
    env["PATH"] = f"{fakebin}{os.pathsep}{env['PATH']}"
    env["PYTHONPATH"] = str(ROOT)
    env["KIROKU_CLAUDE_BIN"] = str(KIROKU / "tests" / "fake_claude.sh")
    env["KIROKU_PYTHON"] = sys.executable
    env["KIROKU_PROJECTS_DIR"] = str(projects)
    env["KIROKU_HOME"] = str(tmp_path)
    env["KIROKU_AUTO"] = "1"  # 自動実行（sleepwatcher 経由相当）
    return env, open_log


def _seed_projects(tmp_path, rec_dt):
    projects = tmp_path / "projects"
    sess = projects / "-Users-munetomoando-claude-work-foo"
    sess.mkdir(parents=True)
    ts = rec_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    (sess / "s.jsonl").write_text(
        json.dumps({"type": "user", "timestamp": ts,
                    "cwd": "/Users/munetomoando/claude-work/foo",
                    "isSidechain": False,
                    "message": {"role": "user", "content": "テスト指示"}}) + "\n",
        encoding="utf-8")
    return projects


def test_auto_run_second_time_today_updates_but_does_not_open(tmp_path):
    # 自動実行では、その日すでに記録済みなら報告書は更新するが表示しない。
    now = datetime.now(timezone.utc)
    projects = _seed_projects(tmp_path, now - timedelta(hours=1))
    env, open_log = _auto_run_env(tmp_path, projects)
    # 今日すでに記録済み（2時間前に記録、その後1時間前に新しい作業あり）
    earlier = (now - timedelta(hours=2)).astimezone(config.LOCAL_TZ)
    (tmp_path / "state.json").write_text(json.dumps(
        {"last_recorded_ts": earlier.isoformat(),
         "last_recorded_date": earlier.strftime("%Y-%m-%d")}))

    subprocess.run(["bash", str(KIROKU / "run-kiroku.sh")],
                   env=env, check=True, cwd=str(tmp_path))

    assert (tmp_path / "作業報告書.html").exists()   # 更新はされる
    assert not open_log.exists()                     # 表示はされない


def test_auto_run_first_time_today_opens_report(tmp_path):
    # 自動実行でも、その日初めての記録なら表示する。
    now = datetime.now(timezone.utc)
    projects = _seed_projects(tmp_path, now - timedelta(hours=1))
    env, open_log = _auto_run_env(tmp_path, projects)
    # 前回記録は昨日 → 今日はまだ記録していない
    yesterday = (now - timedelta(days=1)).astimezone(config.LOCAL_TZ)
    (tmp_path / "state.json").write_text(json.dumps(
        {"last_recorded_ts": yesterday.isoformat(),
         "last_recorded_date": yesterday.strftime("%Y-%m-%d")}))

    subprocess.run(["bash", str(KIROKU / "run-kiroku.sh")],
                   env=env, check=True, cwd=str(tmp_path))

    assert (tmp_path / "作業報告書.html").exists()
    assert open_log.exists()                         # 表示される


def test_run_script_finds_claude_outside_minimal_path(tmp_path):
    # sleepwatcher / Dock 起動では PATH が最小限（/opt/homebrew/bin 等）になる。
    # claude をネイティブ版インストーラで入れると ~/.local/bin へ移るため、
    # PATH 頼みだと自動実行が全部失敗する（2026-08-07 に実際に発生）。
    # KIROKU_CLAUDE_BIN 未設定・PATH に claude なしでも見つけられること。
    now = datetime.now(timezone.utc)
    projects = _seed_projects(tmp_path, now - timedelta(hours=1))

    home = tmp_path / "home"
    localbin = home / ".local" / "bin"
    localbin.mkdir(parents=True)
    called = tmp_path / "claude_called.log"
    fake = localbin / "claude"
    fake.write_text(f'#!/usr/bin/env bash\necho called >> "{called}"\n'
                    f'exec "{KIROKU / "tests" / "fake_claude.sh"}" "$@"\n',
                    encoding="utf-8")
    _chmod_x(fake)
    _chmod_x(KIROKU / "tests" / "fake_claude.sh")

    env = {
        "PATH": "/usr/bin:/bin",          # claude を含まない最小 PATH
        "HOME": str(home),
        "PYTHONPATH": str(ROOT),
        "KIROKU_PYTHON": sys.executable,
        "KIROKU_PROJECTS_DIR": str(projects),
        "KIROKU_HOME": str(tmp_path),
        "KIROKU_OPEN": "0",
    }
    result = subprocess.run(["bash", str(KIROKU / "run-kiroku.sh")],
                            env=env, cwd=str(tmp_path),
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert called.exists(), (tmp_path / "kiroku.log").read_text(encoding="utf-8")


def test_wakeup_path_includes_user_local_bin():
    # wakeup.sh は PATH を明示的に組み立てる。ネイティブ版 claude の既定の
    # 置き場所（~/.local/bin）が抜けていると自動実行だけが静かに失敗する。
    text = (KIROKU / "wakeup.sh").read_text(encoding="utf-8")
    assert "$HOME/.local/bin" in text


def test_run_script_writes_log_under_kiroku_home(tmp_path):
    # ログ出力先が KIROKU_HOME を無視していると、テスト実行が本番の
    # kiroku.log に混ざり、障害調査で実行履歴が読めなくなる。
    projects = tmp_path / "projects"
    projects.mkdir()  # 空 → 記録対象なしで正常終了

    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["KIROKU_PYTHON"] = sys.executable
    env["KIROKU_PROJECTS_DIR"] = str(projects)
    env["KIROKU_HOME"] = str(tmp_path)
    env["KIROKU_OPEN"] = "0"

    before = (KIROKU / "kiroku.log").read_text(encoding="utf-8") \
        if (KIROKU / "kiroku.log").exists() else ""
    subprocess.run(["bash", str(KIROKU / "run-kiroku.sh")],
                   env=env, check=True, cwd=str(tmp_path))
    after = (KIROKU / "kiroku.log").read_text(encoding="utf-8") \
        if (KIROKU / "kiroku.log").exists() else ""

    assert (tmp_path / "kiroku.log").exists()
    assert after == before  # 本番のログには一切書かない
