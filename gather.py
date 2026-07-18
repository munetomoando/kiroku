"""jsonl 走査・抽出・日付×プロジェクト束ね・ダイジェスト生成。"""
import json
from pathlib import Path
from typing import Iterator


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
