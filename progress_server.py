#!/usr/bin/env python3
"""kiroku 実行中に、円形リングのローディング画面を localhost で表示する極小サーバ。

Dock ランチャーから起動される。run-kiroku.sh をサブプロセスで実行しつつ、
段階ファイル(KIROKU_STAGE_FILE)を読んで進捗率を計算し、ブラウザに SVG リングで
表示する。完了したら同じタブを報告書へ切り替える。127.0.0.1 限定・stdlib のみ。

    python3 progress_server.py --run-script <path> --report <path> --url-file <path>
"""
import argparse
import http.server
import json
import os
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path

_DAY_RE = re.compile(r"（(\d+)日中\s*(\d+)日目）")


def stage_to_fraction(text: str) -> float:
    """段階テキストから進捗率(0〜1)を推定する。要約フェーズは日数で按分。"""
    if "収集" in text:
        return 0.08
    m = _DAY_RE.search(text)
    if m:
        total = max(int(m.group(1)), 1)
        i = int(m.group(2))
        return 0.12 + 0.78 * ((i - 1 + 0.5) / total)   # 要約を 0.12〜0.90 に配分
    if "報告書" in text or "作成" in text:
        return 0.95
    if "完了" in text:
        return 1.0
    return 0.10


class _State:
    def __init__(self) -> None:
        self.stage = "作業を収集しています…"
        self.fraction = 0.03
        self.done = False
        self.lock = threading.Lock()

    def update(self, stage: str, fraction: float, done: bool = False) -> None:
        with self.lock:
            self.stage = stage
            self.fraction = max(self.fraction, fraction)   # 逆行させない
            if done:
                self.done = True

    def snapshot(self) -> dict:
        with self.lock:
            return {"stage": self.stage, "fraction": round(self.fraction, 4),
                    "done": self.done}


def run_pipeline(run_script: str, stage_file: str, state: _State) -> None:
    """run-kiroku.sh を実行し、段階ファイルを監視して state を更新する。"""
    env = dict(os.environ)
    env["KIROKU_OPEN"] = "0"                 # 本体側のファイルオープンは抑止
    env["KIROKU_STAGE_FILE"] = stage_file
    try:
        proc = subprocess.Popen(["bash", run_script], env=env,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    except OSError:
        state.update("完了", 1.0, done=True)
        return
    while proc.poll() is None:
        try:
            text = Path(stage_file).read_text(encoding="utf-8").strip()
        except OSError:
            text = ""
        if text:
            state.update(text, stage_to_fraction(text))
        time.sleep(0.3)
    state.update("完了", 1.0, done=True)


LOADING_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>kiroku 実行中…</title>
<style>
:root{ --bg:#f6f4f0; --card:#ffffff; --fg:#2b2b2b; --sub:#8a8377;
  --track:#e7e2d9; --g1:#d9a24a; --g2:#8a6d3b; --shadow:rgba(60,45,20,.14); }
@media (prefers-color-scheme: dark){
  :root{ --bg:#17150f; --card:#211d15; --fg:#f3efe6; --sub:#b7ad9a;
    --track:#3a3327; --g1:#e6b25a; --g2:#b0894a; --shadow:rgba(0,0,0,.5); } }
*{ box-sizing:border-box; }
html,body{ height:100%; margin:0; }
body{ display:flex; align-items:center; justify-content:center;
  background:radial-gradient(120% 120% at 50% 0%, var(--bg), color-mix(in srgb,var(--bg) 70%, #000 6%));
  font-family:-apple-system,"Hiragino Sans","Yu Gothic",sans-serif; color:var(--fg); }
.card{ background:var(--card); border-radius:28px; padding:48px 56px;
  box-shadow:0 24px 60px -20px var(--shadow); text-align:center;
  animation:rise .5s cubic-bezier(.2,.8,.2,1) both; }
@keyframes rise{ from{ opacity:0; transform:translateY(14px) scale(.98); } to{ opacity:1; transform:none; } }
.brand{ font-size:.82rem; letter-spacing:.16em; color:var(--sub);
  text-transform:uppercase; margin-bottom:22px; }
.brand b{ color:var(--fg); font-weight:700; letter-spacing:0; }
.ring-wrap{ position:relative; width:168px; height:168px; margin:0 auto; }
svg{ width:100%; height:100%; transform:rotate(-90deg); }
.track{ fill:none; stroke:var(--track); stroke-width:12; }
.bar{ fill:none; stroke:url(#grad); stroke-width:12; stroke-linecap:round;
  transition:stroke-dashoffset .45s cubic-bezier(.3,.7,.2,1);
  filter:drop-shadow(0 0 6px color-mix(in srgb,var(--g1) 55%, transparent)); }
.center{ position:absolute; inset:0; display:flex; flex-direction:column;
  align-items:center; justify-content:center; }
.pct{ font-size:2.4rem; font-weight:700; font-variant-numeric:tabular-nums;
  letter-spacing:-.02em; }
.dot{ width:7px; height:7px; border-radius:50%;
  background:linear-gradient(var(--g1),var(--g2)); margin-top:6px;
  animation:pulse 1.1s ease-in-out infinite; }
@keyframes pulse{ 0%,100%{ opacity:.35; transform:scale(.8);} 50%{ opacity:1; transform:scale(1.15);} }
.stage{ margin-top:24px; font-size:1.02rem; color:var(--fg); min-height:1.5em; }
.hint{ margin-top:8px; font-size:.8rem; color:var(--sub); }
</style>
</head>
<body>
<div class="card">
  <div class="brand">記 &nbsp;<b>kiroku</b></div>
  <div class="ring-wrap">
    <svg viewBox="0 0 120 120">
      <defs>
        <linearGradient id="grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color="var(--g1)"/>
          <stop offset="1" stop-color="var(--g2)"/>
        </linearGradient>
      </defs>
      <circle class="track" cx="60" cy="60" r="52"/>
      <circle class="bar" id="bar" cx="60" cy="60" r="52"/>
    </svg>
    <div class="center"><div class="pct" id="pct">0%</div><div class="dot"></div></div>
  </div>
  <div class="stage" id="stage">準備しています…</div>
  <div class="hint">作業報告書を生成しています</div>
</div>
<script>
const R=52, C=2*Math.PI*R;
const bar=document.getElementById('bar'), pct=document.getElementById('pct'), stage=document.getElementById('stage');
bar.style.strokeDasharray=C; bar.style.strokeDashoffset=C;
function setFrac(f){ bar.style.strokeDashoffset=C*(1-Math.max(0,Math.min(1,f))); pct.textContent=Math.round(f*100)+'%'; }
async function tick(){
  try{
    const r=await fetch('/status',{cache:'no-store'});
    const s=await r.json();
    setFrac(s.fraction); if(s.stage) stage.textContent=s.stage;
    if(s.done){ setFrac(1); pct.textContent='100%'; stage.textContent='完了'; setTimeout(()=>location.replace('/report'), 550); return; }
  }catch(e){}
  setTimeout(tick, 300);
}
tick();
</script>
</body>
</html>
"""


def make_handler(report_path: str, state: _State, on_report):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):    # アクセスログは出さない
            pass

        def _send(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
            except BrokenPipeError:
                pass

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._send(200, "text/html; charset=utf-8", LOADING_HTML.encode("utf-8"))
            elif path == "/status":
                self._send(200, "application/json; charset=utf-8",
                           json.dumps(state.snapshot()).encode("utf-8"))
            elif path == "/report":
                try:
                    data = Path(report_path).read_bytes()
                except OSError:
                    data = "<h1>まだ報告書がありません</h1>".encode("utf-8")
                self._send(200, "text/html; charset=utf-8", data)
                on_report()          # 報告書を配った → 終了を予約
            else:
                self._send(404, "text/plain; charset=utf-8", b"not found")

    return Handler


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-script", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--url-file", required=True)
    ap.add_argument("--max-seconds", type=int, default=1200)
    args = ap.parse_args()

    state = _State()
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), None)

    def shutdown_soon(delay):
        # 複数のタイマーが張られても最も早いものが serve_forever を止める。
        # httpd.shutdown() は多重呼び出しでも安全（別スレッドから呼ぶこと）。
        # デーモンにして、終了後に未発火タイマーがプロセスを生かし続けないようにする。
        t = threading.Timer(delay, httpd.shutdown)
        t.daemon = True
        t.start()

    httpd.RequestHandlerClass = make_handler(
        args.report, state, on_report=lambda: shutdown_soon(3.0))

    port = httpd.server_address[1]
    Path(args.url_file).write_text(f"http://127.0.0.1:{port}/", encoding="utf-8")

    stage_file = tempfile.mktemp(prefix="kiroku_stage_")

    def pipeline_then_guard():
        run_pipeline(args.run_script, stage_file, state)
        shutdown_soon(120.0)   # 報告書が取得されなければ 120 秒後に自動終了

    threading.Thread(target=pipeline_then_guard, daemon=True).start()
    _guard = threading.Timer(args.max_seconds, httpd.shutdown)   # 安全ネット
    _guard.daemon = True
    _guard.start()

    try:
        httpd.serve_forever()
    finally:
        try:
            os.remove(stage_file)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
