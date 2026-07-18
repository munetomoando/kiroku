"""entries.json 追記と HTML 全再生成、state 更新。"""
import json
import os
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


def atomic_write_json(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def merge_entries(existing: dict, digest: dict, summary: dict) -> dict:
    """digest の統計と summary を突き合わせて新エントリを作り、日付降順でマージ。"""
    by_date = {e["date"]: e for e in existing.get("entries", [])}
    for day in digest.get("days", []):
        date = day["date"]
        projects = []
        for pr in day["projects"]:
            proj = pr["project"]
            s = summary.get(date, {}).get(proj, {})
            projects.append({
                "project": proj,
                "summary": s.get("summary", ""),
                "bullets": s.get("bullets", []),
                "stats": pr["stats"],
            })
        by_date[date] = {"date": date, "projects": projects}
    entries = sorted(by_date.values(), key=lambda e: e["date"], reverse=True)
    return {"entries": entries}


def update_state(path: Path, until_ts: str, today: str) -> None:
    atomic_write_json(path, {"last_recorded_ts": until_ts,
                             "last_recorded_date": today})


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


def render_html(entries: dict) -> str:
    entry_list = entries.get("entries", [])
    anchors = month_anchor_dates(entries)
    # date -> ym（この日付が月アンカーなら id を振る）
    anchor_by_date = {d: ym for ym, d in anchors.items()}
    # 月ナビは降順
    months_desc = sorted(anchors.keys(), reverse=True)

    nav = "\n".join(
        f'    <a class="month-btn" href="#m-{ym}">{_fmt_month_ja(ym)}</a>'
        for ym in months_desc
    )

    sections = []
    for e in entry_list:
        date = e["date"]
        anchor_id = f' id="m-{anchor_by_date[date]}"' if date in anchor_by_date else ""
        proj_html = []
        for pr in e["projects"]:
            st = pr["stats"]
            bullets = "\n".join(
                f"          <li>{escape(b)}</li>" for b in pr.get("bullets", [])
            )
            bullets_block = f"        <ul class=\"topics\">\n{bullets}\n        </ul>" if bullets else ""
            stat_line = (
                f"指示 {st['user_turns']}回・応答 {st['assistant_turns']}回"
                f"／{_fmt_time(st['first_ts'])}〜{_fmt_time(st['last_ts'])}"
            )
            proj_html.append(
                f'      <div class="project">\n'
                f'        <h3>{escape(pr["project"])}</h3>\n'
                f'        <p class="summary">{escape(pr.get("summary", ""))}</p>\n'
                f'{bullets_block}\n'
                f'        <p class="stats">{escape(stat_line)}</p>\n'
                f'      </div>'
            )
        sections.append(
            f'    <section class="day"{anchor_id}>\n'
            f'      <h2>{_fmt_date_ja(date)}</h2>\n'
            + "\n".join(proj_html) +
            f'\n    </section>'
        )

    body_sections = "\n".join(sections)
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
nav.months {{ position:sticky; top:0; background:var(--bg); padding:.8rem 1.5rem;
  border-bottom:1px solid var(--line); display:flex; flex-wrap:wrap; gap:.4rem; z-index:10; }}
.month-btn {{ text-decoration:none; color:var(--accent); border:1px solid var(--line);
  border-radius:999px; padding:.2rem .8rem; font-size:.85rem; background:#fff; }}
.month-btn:hover {{ background:var(--accent); color:#fff; }}
main {{ max-width:820px; margin:0 auto; padding:1.5rem; }}
.day {{ padding:1.2rem 0 1.6rem; border-bottom:1px solid var(--line); scroll-margin-top:4rem; }}
.day > h2 {{ font-size:1.25rem; margin:0 0 .8rem; color:var(--accent); }}
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
  <p>Claude Code の日々の作業記録。最新の記録が上に積み上がります（最終更新: {generated}）。</p>
</header>
<nav class="months">
{nav}
</nav>
<main>
{body_sections}
</main>
<footer>著者: {escape(config.AUTHOR)}</footer>
</body>
</html>
"""
