"""entries.json 追記と HTML 全再生成、state 更新。"""
import json
import os
import sys
from datetime import datetime
from html import escape
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


def load_state_dict(path: Path) -> dict:
    """state.json を読む。無い／壊れていれば空 dict。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def atomic_write_json(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


FALLBACK_SUFFIX = "（自動要約なし）"
# fallback フラグ導入前に書かれた entries.json のプレースホルダ文言。
# これらも「守るべき要約」とは見なさない。
LEGACY_FALLBACK_MARKERS = (FALLBACK_SUFFIX, "（自動要約は生成できませんでした）")


def _is_fallback(project_entry: dict) -> bool:
    if project_entry.get("fallback"):
        return True
    text = project_entry.get("summary") or ""
    return any(m in text for m in LEGACY_FALLBACK_MARKERS)


def _fallback_entry(pr: dict) -> dict:
    """要約が得られなかったとき: digest の prompts を箇条書きにした最小の中身。"""
    return {
        "summary": f"{pr['project']} で作業を行いました{FALLBACK_SUFFIX}。",
        "bullets": [str(p) for p in (pr.get("prompts") or [])]
                   or ["（記録された指示なし）"],
        "fallback": True,
    }


def merge_entries(existing: dict, digest: dict, summary: dict) -> dict:
    """digest の統計と summary を突き合わせて新エントリを作り、日付降順でマージ。

    同じ日は毎回作り直される（同日に複数回実行しても朝の分が消えないための仕様）。
    そのため、要約が一過性の理由で失敗すると、前回までに生成できていた要約まで
    プレースホルダで上書きされてしまう。ここでは要約が得られなかった場合に限り、
    既存の（プレースホルダでない）要約を残し、統計だけを新しい値に更新する。"""
    by_date = {e["date"]: e for e in existing.get("entries", [])}
    for day in digest.get("days", []):
        date = day["date"]
        prev = {p.get("project"): p
                for p in by_date.get(date, {}).get("projects", [])}
        projects = []
        for pr in day["projects"]:
            proj = pr["project"]
            s = summary.get(date, {}).get(proj)
            if s is None:
                # モデル応答がこのプロジェクトを丸ごと省略した／その日の要約が
                # 全試行で失敗した場合。
                old = prev.get(proj)
                if old is not None and not _is_fallback(old):
                    entry = {"summary": old.get("summary") or "",
                             "bullets": [str(b) for b in (old.get("bullets") or [])],
                             "fallback": False}
                else:
                    entry = _fallback_entry(pr)
            else:
                entry = {
                    "summary": s.get("summary") or "",
                    "bullets": [str(b) for b in (s.get("bullets") or [])
                                if b is not None],
                    "fallback": False,
                }
            projects.append({"project": proj, **entry, "stats": pr["stats"]})
        by_date[date] = {"date": date, "projects": projects}
    entries = sorted(by_date.values(), key=lambda e: e["date"], reverse=True)
    return {"entries": entries}


def failed_dates(digest: dict, merged: dict) -> list[str]:
    """今回要約し直した日のうち、フォールバックのままだった日。
    要約を試していない日（needs_summary=False）は対象外。"""
    by_date = {e["date"]: e for e in merged.get("entries", [])}
    out = []
    for day in digest.get("days", []):
        if not day.get("needs_summary", True):
            continue
        entry = by_date.get(day["date"])
        if entry and any(p.get("fallback") for p in entry["projects"]):
            out.append(day["date"])
    return out


def next_pending(digest: dict, merged: dict, prev: dict) -> dict[str, int]:
    """次回に持ち越す再要約待ち。{日付: これまでに試した実行回数}。
    今回成功した日は消え、失敗した日は回数が1増える。上限に達したら諦める
    （何度やっても失敗する日を毎回呼び戻して claude を消費しないため）。"""
    out: dict[str, int] = {}
    for date in failed_dates(digest, merged):
        before = prev.get(date)
        count = (before if isinstance(before, int)
                 and not isinstance(before, bool) else 0) + 1
        if count < config.PENDING_MAX_RUNS:
            out[date] = count
    return out


def update_state(path: Path, until_ts: str, today: str,
                 pending: dict[str, int] | None = None) -> None:
    atomic_write_json(path, {"last_recorded_ts": until_ts,
                             "last_recorded_date": today,
                             "pending_dates": pending or {}})


def month_anchor_dates(entries: dict) -> dict:
    """"YYYY-MM" → その月で最も古い date（アンカーを張る対象）。"""
    anchors: dict[str, str] = {}
    for e in entries.get("entries", []):
        ym = e["date"][:7]
        if ym not in anchors or e["date"] < anchors[ym]:
            anchors[ym] = e["date"]
    return anchors


def _fmt_date_ja(date: str) -> str:
    y, m, d = date.split("-")
    return f"{int(y)}年{int(m)}月{int(d)}日"


def _fmt_month_ja(ym: str) -> str:
    y, m = ym.split("-")
    return f"{int(y)}年{int(m)}月"


def _fmt_time(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts).strftime("%H:%M")
    except ValueError:
        return ""


def _render_day(e: dict) -> str:
    """1日分のセクション HTML。"""
    proj_html = []
    for pr in e["projects"]:
        st = pr["stats"]
        bullets = "\n".join(
            f"            <li>{escape(str(b))}</li>" for b in pr.get("bullets", [])
            if b is not None
        )
        bullets_block = f"          <ul class=\"topics\">\n{bullets}\n          </ul>" if bullets else ""
        stat_line = (
            f"指示 {st['user_turns']}回・応答 {st['assistant_turns']}回"
            f"／{_fmt_time(st['first_ts'])}〜{_fmt_time(st['last_ts'])}"
        )
        proj_html.append(
            f'        <div class="project">\n'
            f'          <h3>{escape(pr["project"])}</h3>\n'
            f'          <p class="summary">{escape(str(pr.get("summary") or ""))}</p>\n'
            f'{bullets_block}\n'
            f'          <p class="stats">{escape(stat_line)}</p>\n'
            f'        </div>'
        )
    return (
        f'      <section class="day">\n'
        f'        <h2>{_fmt_date_ja(e["date"])}</h2>\n'
        + "\n".join(proj_html) +
        f'\n      </section>'
    )


def render_html(entries: dict) -> str:
    entry_list = entries.get("entries", [])  # すでに日付降順
    # 月ごとにグループ化（各月内の日は降順）
    months: dict[str, list[str]] = {}
    for e in entry_list:
        months.setdefault(e["date"][:7], []).append(_render_day(e))
    months_desc = sorted(months.keys(), reverse=True)

    # 年でグループ化したナビ（年→その年の月ボタン、いずれも降順）
    years: dict[str, list[str]] = {}
    for ym in months_desc:
        years.setdefault(ym[:4], []).append(ym)
    nav_parts = []
    for y in sorted(years.keys(), reverse=True):
        btns = "\n".join(
            f'      <a class="month-btn" href="#m-{ym}">{int(ym[5:7])}月</a>'
            for ym in years[y]
        )
        nav_parts.append(
            f'    <div class="year-group">\n'
            f'      <span class="year-label">{int(y)}年</span>\n'
            f'{btns}\n'
            f'    </div>'
        )
    nav = "\n".join(nav_parts)

    # 本体: 月ごとに <details>。最新の月だけ open（古い月は折りたたみ）。
    blocks = []
    for i, ym in enumerate(months_desc):
        open_attr = " open" if i == 0 else ""
        days_html = "\n".join(months[ym])
        blocks.append(
            f'    <details class="month" id="m-{ym}"{open_attr}>\n'
            f'      <summary>{_fmt_month_ja(ym)}</summary>\n'
            f'{days_html}\n'
            f'    </details>'
        )
    body = "\n".join(blocks)
    generated = entry_list[0]["date"] if entry_list else ""
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>作業報告書</title>
<style>
:root {{ --bg:#faf9f7; --fg:#2b2b2b; --sub:#6b6b6b; --line:#e5e2dc; --accent:#8a6d3b; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:-apple-system,"Hiragino Sans","Yu Gothic",sans-serif;
  background:var(--bg); color:var(--fg); line-height:1.7; }}
header {{ padding:2rem 1.5rem 1rem; border-bottom:1px solid var(--line); }}
header h1 {{ margin:0 0 .3rem; font-size:1.6rem; }}
header p {{ margin:0; color:var(--sub); font-size:.9rem; }}
nav.years {{ position:sticky; top:0; background:var(--bg); padding:.6rem 1.5rem;
  border-bottom:1px solid var(--line); max-height:34vh; overflow-y:auto; z-index:10; }}
.year-group {{ display:flex; flex-wrap:wrap; gap:.4rem; align-items:center;
  padding:.25rem 0; }}
.year-label {{ font-weight:600; font-size:.85rem; color:var(--fg);
  min-width:3.6em; }}
.month-btn {{ text-decoration:none; color:var(--accent); border:1px solid var(--line);
  border-radius:999px; padding:.15rem .7rem; font-size:.82rem; background:#fff; }}
.month-btn:hover {{ background:var(--accent); color:#fff; }}
main {{ max-width:820px; margin:0 auto; padding:1.5rem; }}
details.month {{ border-bottom:2px solid var(--line); scroll-margin-top:5rem; }}
details.month > summary {{ cursor:pointer; list-style:none; font-size:1.2rem;
  font-weight:600; color:var(--accent); padding:.9rem 0; position:sticky; top:3rem;
  background:var(--bg); }}
details.month > summary::-webkit-details-marker {{ display:none; }}
details.month > summary::before {{ content:"▸ "; font-size:.85em; }}
details.month[open] > summary::before {{ content:"▾ "; }}
.day {{ padding:1.1rem 0 1.4rem; border-top:1px solid var(--line); }}
.day > h2 {{ font-size:1.15rem; margin:0 0 .8rem; }}
.project {{ margin:0 0 1.1rem; padding-left:.8rem; border-left:3px solid var(--line); }}
.project h3 {{ margin:0 0 .3rem; font-size:1.02rem; }}
.summary {{ margin:.2rem 0 .5rem; }}
.topics {{ margin:.2rem 0 .5rem; padding-left:1.2rem; }}
.topics li {{ margin:.1rem 0; }}
.stats {{ margin:.2rem 0 0; color:var(--sub); font-size:.8rem; }}
footer {{ text-align:center; color:var(--sub); font-size:.8rem; padding:2rem 1rem; }}
</style>
</head>
<body>
<header>
  <h1>作業報告書</h1>
  <p>Claude Code の日々の作業記録。最新の記録が上に積み上がります（最終更新: {generated}）。
  古い月は折りたたまれています。上のボタンで各月へ移動できます。</p>
</header>
<nav class="years">
{nav}
</nav>
<main>
{body}
</main>
<footer>kiroku — Claude Code 作業報告書</footer>
<script>
function kirokuOpenTarget() {{
  var h = location.hash.replace('#', '');
  if (!h) return;
  var el = document.getElementById(h);
  if (el && el.tagName === 'DETAILS') {{ el.open = true; el.scrollIntoView(); }}
}}
window.addEventListener('DOMContentLoaded', kirokuOpenTarget);
window.addEventListener('hashchange', kirokuOpenTarget);
</script>
</body>
</html>
"""


def write_report(digest: dict, summary: dict, *, entries_path: Path,
                 html_path: Path, state_path: Path) -> None:
    # summary が空（その日の要約が全滅）でも merge_entries が
    # プロジェクト単位でフォールバックを組み立て、既存の要約は温存する。
    existing = load_entries(entries_path)
    merged = merge_entries(existing, digest, summary)
    html = render_html(merged)
    atomic_write_json(entries_path, merged)
    tmp_html = html_path.with_suffix(".html.tmp")
    tmp_html.write_text(html, encoding="utf-8")
    os.replace(tmp_html, html_path)
    until_ts = digest.get("until_ts", "")
    today = until_ts[:10] if until_ts else ""
    prev_pending = (load_state_dict(state_path).get("pending_dates") or {})
    update_state(state_path, until_ts, today,
                 next_pending(digest, merged, prev_pending))


def main() -> int:
    """stdin から {"digest":..., "summary":...} を読み、報告書を書き出す。"""
    payload = json.loads(sys.stdin.read())
    digest = payload.get("digest", {"days": []})
    summary = payload.get("summary", {})
    if not digest.get("days"):
        return 0
    write_report(digest, summary, entries_path=config.ENTRIES_PATH,
                 html_path=config.HTML_PATH, state_path=config.STATE_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
