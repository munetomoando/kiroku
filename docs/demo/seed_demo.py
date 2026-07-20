"""README 用スクリーンショットのための架空デモデータ生成。

実データには利用者のプロジェクト名と作業内容がそのまま載るため、公開用の
スクリーンショットは完全に架空のデータから生成する。既存の
kiroku.render.render_html() をそのまま使うので、UI を変えても同じ手順で
撮り直せる。

使い方:
    python3 docs/demo/seed_demo.py /tmp/demo.html
"""
import sys
import types
from pathlib import Path

# kiroku は `kiroku.render` として import する。リポジトリのディレクトリ名が
# 常に `kiroku` とは限らない（GitHub の「Download ZIP」は `kiroku-main` に、
# `git clone <url> myfork` は任意の名前に展開される）ため、ディレクトリ名に
# 依存する sys.path 挿入ではなくパッケージを明示的に紐付ける。副次的に、
# 任意のユーザーディレクトリを sys.path に追加せずに済む利点もある。
# docs/demo/seed_demo.py → parents[0]=demo, [1]=docs, [2]=リポジトリ本体。
_repo = Path(__file__).resolve().parents[2]
_pkg = types.ModuleType("kiroku")
_pkg.__path__ = [str(_repo)]
sys.modules.setdefault("kiroku", _pkg)

from kiroku.render import render_html  # noqa: E402

# 架空のプロジェクト名。実在のものと衝突しないよう一般的な語だけで構成する。
DEMO_PROJECTS = ("shop-api", "landing-page", "data-pipeline", "docs-site")


def _stats(first: str, last: str, user: int, assistant: int) -> dict:
    return {"first_ts": first, "last_ts": last,
            "user_turns": user, "assistant_turns": assistant}


def build_demo_entries() -> dict:
    """架空の作業記録を日付降順で返す。

    月ボタンと年グループが写る必要があるため、必ず 2 か月以上にまたがらせる。
    """
    return {"entries": [
        {"date": "2026-07-18", "projects": [
            {"project": "shop-api",
             "summary": "注文 API のレスポンスが遅い件を調査し、原因が N+1 クエリで"
                        "あることを特定した。関連テーブルを事前読み込みする形に"
                        "書き換え、一覧取得の応答時間が 1.8 秒から 0.2 秒に短縮した。"
                        "回帰を防ぐためクエリ本数を検証するテストも追加している。",
             "bullets": [
                 "注文一覧 API のスロークエリログを確認し、N+1 クエリを特定",
                 "関連テーブルの事前読み込みへ書き換え",
                 "応答時間 1.8 秒 → 0.2 秒を計測で確認",
                 "発行クエリ本数を検証する回帰テストを追加",
             ],
             "stats": _stats("2026-07-18T09:42:00+09:00",
                             "2026-07-18T12:15:00+09:00", 14, 96)},
            {"project": "docs-site",
             "summary": "API リファレンスの生成が CI で失敗していたため、"
                        "型定義の読み込み順を修正した。あわせて古いエンドポイントの"
                        "記述を削除している。",
             "bullets": [
                 "CI のドキュメント生成失敗のログを確認",
                 "型定義の読み込み順を修正してビルドを復旧",
                 "廃止済みエンドポイントの記述を削除",
             ],
             "stats": _stats("2026-07-18T14:03:00+09:00",
                             "2026-07-18T15:20:00+09:00", 6, 38)},
        ]},
        {"date": "2026-07-17", "projects": [
            {"project": "landing-page",
             "summary": "トップページのファーストビューを作り直した。見出しと"
                        "申し込みボタンの間にあった余白を詰め、スマートフォンでも"
                        "スクロールせずにボタンが見えるようにした。画像の遅延読み込みも"
                        "入れ、表示開始までの時間を改善している。",
             "bullets": [
                 "ファーストビューの見出しとボタンの余白を調整",
                 "375px 幅でボタンが折り返さないことを確認",
                 "ヒーロー画像以外を遅延読み込みに変更",
                 "Lighthouse のスコアを 72 から 91 へ改善",
             ],
             "stats": _stats("2026-07-17T10:05:00+09:00",
                             "2026-07-17T13:48:00+09:00", 21, 134)},
        ]},
        {"date": "2026-07-15", "projects": [
            {"project": "data-pipeline",
             "summary": "日次バッチが月初にだけ失敗する問題を追跡した。月をまたぐ"
                        "集計期間の計算で前月の末日がずれていたことが原因で、"
                        "境界値のテストを先に書いてから修正した。",
             "bullets": [
                 "失敗が月初に集中していることをログから確認",
                 "集計期間の計算で前月末日がずれる条件を再現",
                 "境界値（月末・うるう年）のテストを追加",
                 "日付計算を修正し、過去 3 か月分を再実行して検証",
             ],
             "stats": _stats("2026-07-15T11:20:00+09:00",
                             "2026-07-15T17:02:00+09:00", 18, 112)},
            {"project": "shop-api",
             "summary": "在庫数の更新で競合が起きうる箇所に排他制御を入れた。"
                        "同時購入を模したテストを書き、在庫がマイナスにならないことを"
                        "確認している。",
             "bullets": [
                 "在庫更新の競合条件を整理",
                 "行ロックによる排他制御を実装",
                 "同時購入を模した並行テストを追加",
             ],
             "stats": _stats("2026-07-15T18:10:00+09:00",
                             "2026-07-15T19:30:00+09:00", 8, 51)},
        ]},
        {"date": "2026-06-29", "projects": [
            {"project": "landing-page",
             "summary": "問い合わせフォームのバリデーションを見直した。"
                        "エラー文言を入力欄のすぐ下に出す形に変え、何を直せばよいかが"
                        "分かるようにしている。",
             "bullets": [
                 "エラー表示の位置を入力欄の直下へ変更",
                 "汎用的な文言を具体的な指示に書き換え",
                 "スクリーンリーダー向けに aria-describedby を付与",
             ],
             "stats": _stats("2026-06-29T13:30:00+09:00",
                             "2026-06-29T16:12:00+09:00", 12, 74)},
        ]},
        {"date": "2026-06-27", "projects": [
            {"project": "data-pipeline",
             "summary": "取り込み処理のリトライを指数バックオフに変更した。"
                        "外部 API が一時的に落ちた際に処理全体が止まらなくなった。",
             "bullets": [
                 "リトライ間隔を固定から指数バックオフへ変更",
                 "上限回数と最大待ち時間を設定",
                 "外部 API 障害を模したテストを追加",
             ],
             "stats": _stats("2026-06-27T09:15:00+09:00",
                             "2026-06-27T11:40:00+09:00", 9, 63)},
        ]},
    ]}


def write_demo_html(out_path: Path) -> None:
    """デモ HTML を指定パスにだけ書き出す（実データには触れない）。"""
    out_path.write_text(render_html(build_demo_entries()), encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <出力先HTMLパス>", file=sys.stderr)
        return 2
    out = Path(argv[1]).resolve()
    write_demo_html(out)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
