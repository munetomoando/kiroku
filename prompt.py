"""claude -p 用プロンプト生成と応答パース、フォールバック要約。"""
import json
import re


def build_prompt(digest: dict) -> str:
    lines = [
        "あなたは作業報告書の編集者です。以下は Claude Code の作業ログを",
        "日付×プロジェクトごとに抽出したものです。各プロジェクトについて、",
        "その日に行った作業の要約文（2〜4文の自然な日本語）と、主なトピックの",
        "箇条書き（3〜6項目）を作成してください。",
        "",
        "出力は次の形式の JSON のみとし、前後に説明文やコードフェンスを付けても",
        "構いませんが、必ず有効な JSON を含めてください:",
        '{"YYYY-MM-DD": {"プロジェクト名": {"summary": "...", "bullets": ["...", "..."]}}}',
        "",
        "=== 作業ログ ===",
    ]
    for day in digest.get("days", []):
        lines.append(f"\n## {day['date']}")
        for pr in day["projects"]:
            st = pr["stats"]
            lines.append(f"\n### プロジェクト: {pr['project']}")
            lines.append(
                f"統計: ユーザー指示 {st['user_turns']}回 / 応答 {st['assistant_turns']}回"
                f" / {st['first_ts']}〜{st['last_ts']}"
            )
            if pr["prompts"]:
                lines.append("ユーザー指示:")
                for t in pr["prompts"]:
                    lines.append(f"- {t}")
            if pr["highlights"]:
                lines.append("アシスタントの応答抜粋:")
                for t in pr["highlights"][:8]:
                    lines.append(f"- {t[:200]}")
    return "\n".join(lines)


def parse_summary(text: str) -> dict:
    """テキストから JSON を抽出。フェンス付き・裸のどちらも対応。失敗時は {}。"""
    # ```json ... ``` を優先
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = []
    if m:
        candidates.append(m.group(1))
    # 最初の { から最後の } まで
    first, last = text.find("{"), text.rfind("}")
    if first != -1 and last != -1 and last > first:
        candidates.append(text[first:last + 1])
    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return {}


def fallback_summary(digest: dict) -> dict:
    """要約失敗時: prompts を箇条書きにした最小要約を組み立てる。"""
    out: dict = {}
    for day in digest.get("days", []):
        day_map = out.setdefault(day["date"], {})
        for pr in day["projects"]:
            bullets = list(pr["prompts"]) or ["（記録された指示なし）"]
            day_map[pr["project"]] = {
                "summary": f"{pr['project']} で作業を行いました（自動要約は生成できませんでした）。",
                "bullets": bullets,
            }
    return out
