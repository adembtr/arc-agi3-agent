#!/usr/bin/env python3
"""Canli gozlem — KAZANAN yontem (I: yanlis-eleme + odul) SPACE ile adim adim.

Sol: oyun.  Sag: W agirliklari (canli/elenen aksiyonlar) + odul + arsiv.
SPACE = ajan bir adim atar.

Calistir:  cd denme && uv run --project ../ARC-AGI-3-Agents python live.py
Tarayici:  http://localhost:8005
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "infra"))
from env import Env                       # noqa: E402
from transition import Mind               # noqa: E402
import strategies2                        # noqa: E402
import perception as P                    # noqa: E402

COLOR_MAP = {
    0: "#FFFFFF", 1: "#CCCCCC", 2: "#999999", 3: "#666666",
    4: "#333333", 5: "#000000", 6: "#E53AA3", 7: "#FF7BCC",
    8: "#F93C31", 9: "#1E93FF", 10: "#88D8F1", 11: "#FFDC00",
    12: "#FF851B", 13: "#921231", 14: "#4FCC30", 15: "#A356D6",
}
GAMES = ["vc33", "lf52", "m0r0", "g50t", "cd82", "ft09", "tn36", "s5i5"]
_LOCK = threading.Lock()


class Live:
    def __init__(self, game="vc33"):
        self.start(game)

    def start(self, game):
        self.game = game
        self.env = Env(game)
        self.mind = Mind()
        self.env.shapes = self.mind.shapes
        self.strat = strategies2.MACROS["I_wrong_elim_reward"](self.env, self.mind, seed=0)
        self.obs = self.env.reset()
        self.step_i = 0
        self.last = {"aksiyon": "-", "sonuc": "-", "odul": 0}
        self.max_level = 0

    def step(self):
        cand = self.strat.choose(self.obs)
        if cand is None:
            kind, a, x, y = "press", (self.obs["avail"][0] if self.obs["avail"] else 0), None, None
            k = -1
        elif len(cand) == 4:
            kind, a, x, y = cand; k = -1
        else:
            kind, a, k, x, y = cand
        before = self.obs
        obs2 = self.env.step(kind, a, x, y)
        res = self.mind.observe(a, f"[A{a}]", before["grid"], obs2["grid"])
        self.strat.update(before, cand, obs2, res)
        self.step_i += 1
        # sonuc ozeti
        structural = any(c["effect"] != 0 for c in res["changes"])
        leveled = obs2["level"] > before["level"]
        new_state = obs2["fp"] != before["fp"]
        if leveled:
            sonuc = "★ SEVIYE ATLADI"
        elif not structural:
            sonuc = "✗ ETKI YOK (yanlis -> W dustu)"
        elif not new_state:
            sonuc = "↩ geri dondu"
        else:
            sonuc = "✓ yeni durum"
        lbl = (f"tik@({x},{y}) [token K{k}]" if kind == "click" else f"tus A{a}")
        self.last = {"aksiyon": lbl, "sonuc": sonuc}
        self.max_level = max(self.max_level, obs2["level"])
        self.obs = obs2
        return self.snapshot()

    def snapshot(self):
        o = self.obs
        # W tablosu: elenen ve canli aksiyonlar
        W = self.strat.W
        rows = []
        for ident, w in sorted(W.items(), key=lambda kv: kv[1]):
            if isinstance(ident, tuple):     # ("A",n) tus
                name = f"tuş A{ident[1]}"
            else:
                name = f"şekil-token K{ident}"
            rows.append({"ad": name, "w": round(w, 3),
                         "durum": "ELENDI" if w < 0.05 else ("zayif" if w < 0.5 else "canli")})
        val = self.strat.value
        vrows = [{"ad": (f"tuş A{i[1]}" if isinstance(i, tuple) else f"K{i}"),
                  "deger": round(v, 2)} for i, v in sorted(val.items(), key=lambda kv: -kv[1]) if v > 0][:6]
        return {
            "game": self.game, "grid": o["grid"], "state": o["state"],
            "level": o["level"], "adim": self.step_i, "max_level": self.max_level,
            "avail": o["avail"], "nesne": len(o["objs"]),
            "last": self.last, "W": rows[:16], "degerler": vrows,
            "arsiv": len(self.strat.archive), "elenen": sum(1 for r in rows if r["durum"] == "ELENDI"),
        }


SES = Live("vc33")

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>Kazanan Yontem — Canli</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}
body{margin:0;background:#0d0f14;color:#e6e6e6;font:13px system-ui,sans-serif;height:100vh;
 display:grid;grid-template-columns:1fr 380px;grid-template-rows:auto 1fr;
 grid-template-areas:"top top" "game side";overflow:hidden}
#top{grid-area:top;display:flex;gap:12px;align-items:center;padding:8px 12px;background:#151822;border-bottom:1px solid #262b38;flex-wrap:wrap}
#game{grid-area:game;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;padding:12px;overflow:auto}
#side{grid-area:side;border-left:1px solid #262b38;padding:12px;overflow:auto}
h2{font-size:12px;text-transform:uppercase;color:#7a9;margin:14px 0 6px}
.badge{padding:3px 9px;border-radius:6px;background:#1b1f2b;border:1px solid #2a3040;font-size:12px}
.win{background:#14361c;border-color:#2f7d3f;color:#7CFC9E}.over{background:#3a1414;border-color:#7d2f2f;color:#ff8a8a}
#board{display:grid;background:#000;border:2px solid #333}
.cell{width:11px;height:11px;display:flex;align-items:center;justify-content:center;font:7px/1 monospace}
select,button{background:#1b1f2b;color:#cfe;border:1px solid #3a4256;border-radius:6px;padding:6px 12px;font-size:13px;cursor:pointer}
.spacebtn{background:#1b2540;font-weight:700}
table{width:100%;border-collapse:collapse;font-size:12px}
td{padding:2px 5px;border-bottom:1px solid #1c2130}
.ELENDI{color:#ff6a6a}.zayif{color:#FFDC00}.canli{color:#7CFC9E}
kbd{background:#222a3a;border:1px solid #3a4460;border-radius:4px;padding:1px 6px}
</style></head><body>
<div id="top">
 <select id="gamesel"></select>
 <span id="hud"></span>
 <span style="flex:1"></span>
 <button class="spacebtn" onclick="step()">SPACE ▶ adım</button>
 <button onclick="run10()">▶▶ 10 adım</button>
 <button onclick="reset()">yeni oyun</button>
</div>
<div id="game">
 <div id="board"></div>
 <div id="lastact" class="badge"></div>
 <div class="badge" style="color:#8aa"><kbd>SPACE</kbd> = ajan bir adım · kazanan yöntem: yanlış-eleme + ödül</div>
</div>
<div id="side">
 <h2>🎯 Son Hamle</h2><div id="last"></div>
 <h2>⚖ W AĞIRLIKLARI (elenen/canlı aksiyonlar)</h2><div id="wtab"></div>
 <h2>💎 ÖĞRENİLEN DEĞER (ödül kredisi)</h2><div id="vtab" class="badge">-</div>
</div>
<script>
const COLORS=%COLORS%;
async function api(p,b){const r=await fetch(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})});return r.json();}
async function get(){return (await fetch('/api/state')).json();}
function lum(h){if(!h)return 0;return(0.299*parseInt(h.slice(1,3),16)+0.587*parseInt(h.slice(3,5),16)+0.114*parseInt(h.slice(5,7),16))/255;}
function render(s){
 const hud=document.getElementById('hud');
 let cls=s.state==='WIN'?'badge win':(s.state==='GAME_OVER'?'badge over':'badge');
 hud.innerHTML=`<span class="${cls}">${s.state}</span> <span class="badge" ${s.max_level>0?'style="background:#14361c;color:#7CFC9E"':''}>Seviye ${s.level} (max ${s.max_level})</span> <span class="badge">adım ${s.adim}</span> <span class="badge">${s.nesne} nesne</span> <span class="badge">elenen ${s.elenen}</span> <span class="badge">arşiv ${s.arsiv}</span>`;
 const g=s.grid,n=g.length,b=document.getElementById('board');
 b.style.gridTemplateColumns=`repeat(${n},11px)`;b.innerHTML='';
 for(let y=0;y<n;y++)for(let x=0;x<g[y].length;x++){const v=g[y][x];const c=document.createElement('div');c.className='cell';c.style.background=COLORS[v]||'#f0f';c.textContent=v;c.style.color=lum(COLORS[v])>0.55?'rgba(0,0,0,.6)':'rgba(255,255,255,.75)';b.appendChild(c);}
 const L=s.last;
 document.getElementById('lastact').textContent=`${L.aksiyon} → ${L.sonuc}`;
 document.getElementById('last').innerHTML=`<div><b>${L.aksiyon}</b></div><div style="color:${L.sonuc.includes('★')?'#7CFC9E':L.sonuc.includes('✗')?'#ff6a6a':'#cfe'}">${L.sonuc}</div>`;
 let wt='<table>';s.W.forEach(r=>{wt+=`<tr><td>${r.ad}</td><td style="text-align:right">${r.w}</td><td class="${r.durum}">${r.durum}</td></tr>`;});wt+='</table>';
 document.getElementById('wtab').innerHTML=wt;
 const vt=s.degerler;
 document.getElementById('vtab').innerHTML=vt.length?vt.map(v=>`${v.ad}: <b style="color:#FFDC00">${v.deger}</b>`).join(' · '):'<span style="color:#6b7688">henüz ödül yok</span>';
}
async function step(){render(await api('/api/step'));}
async function run10(){for(let i=0;i<10;i++)render(await api('/api/step'));}
async function reset(){render(await api('/api/reset',{game:document.getElementById('gamesel').value}));}
document.addEventListener('keydown',e=>{if(e.code==='Space'){e.preventDefault();step();}});
(async()=>{const sel=document.getElementById('gamesel');%GAMES%.forEach(g=>{const o=document.createElement('option');o.value=g;o.textContent=g;sel.appendChild(o);});sel.onchange=()=>reset();render(await get());})();
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str): body = body.encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            self._send(200, PAGE.replace("%COLORS%", json.dumps(COLOR_MAP)).replace("%GAMES%", json.dumps(GAMES)), "text/html; charset=utf-8")
        elif p == "/api/state":
            with _LOCK: self._send(200, json.dumps(SES.snapshot()))
        else: self._send(404, b"{}")
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        global SES
        with _LOCK:
            try:
                if self.path == "/api/step":
                    self._send(200, json.dumps(SES.step()))
                elif self.path == "/api/reset":
                    SES.start(body.get("game", SES.game))
                    self._send(200, json.dumps(SES.snapshot()))
                else: self._send(404, b"{}")
            except Exception as e:
                import traceback; traceback.print_exc()
                self._send(200, json.dumps({"error": str(e)}))


if __name__ == "__main__":
    port = int(os.environ.get("LIVE_PORT", "8005"))
    print(f"Kazanan yontem canli -> http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
