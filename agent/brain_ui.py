#!/usr/bin/env python3
"""brain_ui.py — Ajani GOZLEMLEME arayuzu.

Orta = oyun.  Sol = GOZ (nesneler/sekiller).  Alt = EL (son aksiyon).
Sag = BEYIN (atomlar — SIFIRDAN baslar, gozledikce dolar).

SPACE = bir clock sinyali: ajan SIRADAKI adimini atar (kesif).
Kullanici grid'e tiklayip / rakam basip kendi de surebilir.

Calistir (arc_agi venv):
  cd ARC-AGI-3-Agents && uv run python ../agent/brain_ui.py
  http://localhost:8001
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import perception as P            # noqa: E402
from action import Hand, describe  # noqa: E402
from transition import Mind       # noqa: E402

COLOR_MAP = {
    0: "#FFFFFF", 1: "#CCCCCC", 2: "#999999", 3: "#666666",
    4: "#333333", 5: "#000000", 6: "#E53AA3", 7: "#FF7BCC",
    8: "#F93C31", 9: "#1E93FF", 10: "#88D8F1", 11: "#FFDC00",
    12: "#FF851B", 13: "#921231", 14: "#4FCC30", 15: "#A356D6",
}
GAMES = ["lf52", "g50t", "ft09", "m0r0"]

_LOCK = threading.Lock()


class Session:
    """Tek oturum: el + beyin + kesif durumu."""
    def __init__(self, game="lf52"):
        self.start(game)

    def start(self, game):
        self.game = game
        self.hand = Hand(game)
        self.mind = Mind()
        self.tried = set()             # denenmis basit aksiyonlar
        self.clicked_shapes = set()    # TIKLANMIS sekil-tokenlari (merak icin)
        self.boring = set()            # YENI olay uretmeyen konum kovalari (tekrarlama)
        self.prev_level = self.hand.last["levels_completed"]
        # HAFIZA: gorulen durumlar (fingerprint) — basa donusu (geri) anlamak icin
        self.start_fp = self._fp(self.hand.last["grid"])
        self.visited = {self.start_fp}
        self.back_actions = set()      # BASA donduren aksiyonlar (kacinilacak)
        # PLANLAYICI durumu
        self.expecting_target = False  # bir kargo tikladik, hedef bekliyoruz
        self.last_appeared = []        # son adimda BELIREN nesne merkezleri (x,y)
        self.last_click = None         # son tiklanan (x,y) — toggle tespiti icin
        self.roles = {}                # renk -> rol ("kargo","araba"...) davranistan
        self.last_hand = {"desc": "oyun basladi (RESET)", "touched": None,
                          "action": 0}

    @staticmethod
    def _fp(grid):
        return hash(tuple(tuple(row) for row in grid))

    @staticmethod
    def _appeared(before, after):
        """after'da olup before ile ORTUSMEYEN kucuk nesneler = BELIREN (hedef)."""
        B = P.find_objects(before)
        A = P.find_objects(after)
        out = []
        for a in A:
            if a.size > 40:
                continue
            if not any(len(a.cells & b.cells) > 0 for b in B):
                cy, cx = a.centroid
                out.append((int(round(cx)), int(round(cy))))
        return out

    # --- PLANLAYICI: hedef=kargolari birlestir. sec->hedef->uygula makinesi ---
    def next_explore(self):
        o = self.hand.last
        avail, grid, state = o["available"], o["grid"], o["state"]

        # 0) GAME_OVER / WIN -> devam edebilmek icin reset (mesru A0)
        if state in ("GAME_OVER", "WIN"):
            return ("press", 0, None, None)

        # 1) UYGULA: bir kargo tikladik ve HEDEF belirdi -> hedefe tikla (birlestir)
        #    AMA hedef, az once tikladigimiz yerdeyse bu TOGGLE'dir (dongu) -> atla
        if self.expecting_target and self.last_appeared:
            x, y = self.last_appeared[0]
            self.expecting_target = False
            lx, ly = self.last_click or (-99, -99)
            if abs(x - lx) + abs(y - ly) > 3:      # gercekten BASKA yerde belirdi
                return ("click", 6, x, y)
            # toggle: bu konumu sikici isaretle, baska sey dene
            self.boring.add((lx // 5, ly // 5))
        self.expecting_target = False

        # 2) SEC: birlestirilebilir KARGO (>=2 ayni sekil+renk, kucuk) tikla
        objs = P.find_objects(grid)
        groups = {}
        for ob in objs:
            if ob.size > 40:
                continue
            groups.setdefault((ob.color, ob.norm_mask), []).append(ob)
        # kargo adaylari: 2..8 arasi ayni sekil (dev izgaralar DEGIL). Once
        #    ogrenilmis "kargo" rolu olan renkler, sonra kucuk gruplar.
        cargo = [g for g in groups.values() if 2 <= len(g) <= 8]
        cargo.sort(key=lambda g: (0 if self.roles.get(g[0].color) == "kargo" else 1,
                                  len(g)))
        for grp in cargo:
            for ob in grp:
                cy, cx = ob.centroid
                if (int(cx) // 5, int(cy) // 5) in self.boring:
                    continue
                self.expecting_target = True   # tiklayinca hedef bekle
                return ("click", 6, int(round(cx)), int(round(cy)))

        # 3) denenmemis basit aksiyonlari dene (yonu ogren) — A0/geri HARIC
        for a in (1, 2, 3, 4, 5, 7):
            if a in avail and a not in self.tried and a not in self.back_actions:
                return ("press", a, None, None)

        # 4) yenilik: tiklanmamis tekil sekil (kesif)
        for ob in objs:
            if ob.size > 60:
                continue
            t = self.mind.shapes.token(ob)
            cy, cx = ob.centroid
            if t in self.clicked_shapes or (int(cx) // 5, int(cy) // 5) in self.boring:
                continue
            self.clicked_shapes.add(t)
            return ("click", 6, int(round(cx)), int(round(cy)))

        # 5) ILERI git (hareket) — A0 ASLA (olu degilse); nesneleri yaklastirmayi dene
        if self.mind.last_dead:
            return ("press", 0, None, None)
        for a in (1, 2, 3, 4):
            if a in avail and a not in self.back_actions:
                return ("press", a, None, None)
        return ("press", avail[0] if avail else 0, None, None)

    def do(self, kind, action, x, y):
        """Bir aksiyon uygula + beyin gozlesin."""
        before = self.hand.last["grid"]
        if action != 6:
            self.tried.add(action)
        if kind == "click":
            label = f"[A6@{x},{y}]"
            self.last_click = (int(x), int(y))
            obs = self.hand.click(x, y)
            touched = self._touched(before, x, y)
        else:
            label = f"[A{action}]"
            obs = self.hand.act(action)
            touched = None
        after = obs["grid"]
        res = self.mind.observe(action, label, before, after)
        # ust-duzey: seviye gecildi / WIN -> token
        if obs["levels_completed"] > self.prev_level or obs["state"] == "WIN":
            gt, gyeni = self.mind.record_goal(action, label)
            if gyeni:
                res["yeni_tokenlar"].append(gt)
            self.clicked_shapes = set()      # yeni seviye: merak sifirla
        self.prev_level = obs["levels_completed"]
        # HAFIZA + GERI ALGILAMA: bu aksiyon bizi BASA/onceki bir duruma dondurdu mu?
        before_fp = self._fp(before)
        new_fp = self._fp(after)
        if new_fp == self.start_fp and before_fp != self.start_fp:
            bt, byeni = self.mind.record_backward(action, label)   # A0 = geri
            if byeni:
                res["yeni_tokenlar"].append(bt)
            self.back_actions.add(action)      # bu aksiyon geri goturuyor -> kacin
        self.visited.add(new_fp)
        # PLANLAYICI: bu adimda BELIREN nesneler (hedef adaylari)
        self.last_appeared = self._appeared(before, after)
        # ROL ogren: birlesme olan renk = KARGO
        from transition import E_MERGE
        for c in res["changes"]:
            if c["effect"] == E_MERGE:
                self.roles[c["color"]] = "kargo"
        # MERAK: bir tik YENI olay uretmediyse o konumu "sikici" isaretle (tekrarlama)
        if kind == "click" and not res["yeni_tokenlar"]:
            self.boring.add((int(x) // 5, int(y) // 5))
        if action == 0:
            self.clicked_shapes = set(); self.boring = set()  # reset: taze kesif
        # el kaydi
        known = describe(action)
        yeni_desc = [f"#{t} {self.mind.events.info[t]['desc']}" for t in res["yeni_tokenlar"]]
        self.last_hand = {
            "desc": f"{label}  ({known.split('—')[0].strip() if '—' in known else known[:40]})",
            "touched": touched, "action": action,
            "yeni": yeni_desc, "olu": res["olu"],
        }
        return res

    def _touched(self, grid, x, y):
        """Tiklanan (x,y) hangi nesneye denk geldi?"""
        objs = P.find_objects(grid)
        for o in objs:
            if (y, x) in o.cells:
                return f"renk{o.color} nesne ({o.size} hucre)"
        # en yakin
        best, bo = None, None
        for o in objs:
            cy, cx = o.centroid
            d = abs(cy - y) + abs(cx - x)
            if best is None or d < best:
                best, bo = d, o
        return (f"bos alan (en yakin: renk{bo.color})" if bo else "bos alan")

    def snapshot(self):
        o = self.hand.last
        return {
            "game": self.game,
            "grid": o["grid"],
            "state": o["state"],
            "level": o["levels_completed"],
            "win_levels": o["win_levels"],
            "available": o["available"],
            "n_frames": o["n_frames"],
            "eye": self.mind.eye_tokens(o["grid"]),
            "hand": self.last_hand,
            "brain": self.mind.event_table(),
            "adim": self.mind.step,
        }


SES = Session("lf52")

PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<title>Ajan Gozlem</title><style>
:root{color-scheme:dark}*{box-sizing:border-box}
body{margin:0;background:#0d0f14;color:#e6e6e6;font:13px system-ui,sans-serif;height:100vh;
 display:grid;grid-template-columns:270px 1fr 340px;grid-template-rows:auto 1fr auto;
 grid-template-areas:"top top top" "eye game brain" "hand hand hand";overflow:hidden}
#top{grid-area:top;display:flex;gap:12px;align-items:center;padding:8px 12px;background:#151822;border-bottom:1px solid #262b38;flex-wrap:wrap}
#eye{grid-area:eye;border-right:1px solid #262b38;padding:10px;overflow:auto}
#game{grid-area:game;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px;padding:12px;overflow:auto}
#brain{grid-area:brain;border-left:1px solid #262b38;padding:10px;overflow:auto}
#hand{grid-area:hand;border-top:1px solid #262b38;padding:8px 12px;background:#0a0c11;min-height:70px}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:#7a9;margin:0 0 8px}
.badge{padding:3px 8px;border-radius:6px;background:#1b1f2b;border:1px solid #2a3040;font-size:12px}
.win{background:#14361c;border-color:#2f7d3f;color:#7CFC9E}.over{background:#3a1414;border-color:#7d2f2f;color:#ff8a8a}
#board{display:grid;background:#000;border:2px solid #333}
.cell{width:12px;height:12px;display:flex;align-items:center;justify-content:center;font:8px/1 monospace;font-weight:700}
select,button{background:#1b1f2b;color:#cfe;border:1px solid #3a4256;border-radius:6px;padding:5px 9px;font-size:13px;cursor:pointer}
button:hover{background:#2a3350}
.spacebtn{background:#1b2540;font-weight:700;padding:6px 16px}
.row{display:flex;gap:6px;flex-wrap:wrap}
table{width:100%;border-collapse:collapse;font-size:12px}
td{padding:3px 5px;border-bottom:1px solid #1c2130;vertical-align:top}
.cnt{color:#7CFC9E;font-weight:700;text-align:right;width:30px}
.new{background:#14361c}
.grp{display:flex;align-items:center;gap:6px;padding:3px 0;border-bottom:1px solid #171b26}
.sw{width:14px;height:14px;border-radius:3px;border:1px solid #333}
.muted{color:#6b7688}
kbd{background:#222a3a;border:1px solid #3a4460;border-radius:4px;padding:1px 6px;font-size:11px}
#nums button{min-width:34px}
</style></head><body>
<div id="top">
 <select id="gamesel"></select>
 <span id="hud"></span>
 <span style="flex:1"></span>
 <span class="badge">Adim: <b id="adim">0</b></span>
 <button class="spacebtn" onclick="step()">SPACE ▶ ajan adim</button>
 <button onclick="wipe()">beyni sifirla</button>
 <button onclick="reset()">oyunu resetle</button>
</div>

<div id="eye"><h2>👁 GÖZ — ne görüyor</h2><div id="eyebody"></div></div>

<div id="game">
 <div id="board"></div>
 <div class="row" id="nums"></div>
 <div class="muted"><kbd>SPACE</kbd> = ajan sıradaki adımı · grid'e tık / rakam = sen sür</div>
</div>

<div id="brain"><h2>🧠 BEYİN — olay-token (sayı, 0'dan)</h2><div id="brainbody"><span class="muted">henüz atom yok</span></div></div>

<div id="hand"><h2>✋ EL — son ne yaptı</h2><div id="handbody"></div></div>

<script>
const COLORS=%COLORS%;
async function api(p,b){const r=await fetch(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})});return r.json();}
async function get(){const r=await fetch('/api/state');return r.json();}

function render(s){
 document.getElementById('adim').textContent=s.adim;
 const hud=document.getElementById('hud');
 let cls=s.state==='WIN'?'badge win':(s.state==='GAME_OVER'?'badge over':'badge');
 hud.innerHTML=`<span class="${cls}">${s.state}</span> <span class="badge">Seviye ${s.level}/${s.win_levels??'?'}</span> <span class="badge">gecerli [${s.available.join(',')}]</span>`;
 // grid
 const g=s.grid,n=g.length,b=document.getElementById('board');
 b.style.gridTemplateColumns=`repeat(${n},12px)`;b.innerHTML='';
 for(let y=0;y<n;y++)for(let x=0;x<g[y].length;x++){const v=g[y][x];const c=document.createElement('div');c.className='cell';c.style.background=COLORS[v]||'#f0f';c.textContent=v;c.style.color=lum(COLORS[v])>0.55?'rgba(0,0,0,.7)':'rgba(255,255,255,.8)';c.onclick=()=>act(6,x,y);b.appendChild(c);}
 // eye — her sekil bir TOKEN (sayi) + gorsel numune
 const e=s.eye;const eb=document.getElementById('eyebody');
 eb.innerHTML=`<div class="badge">arka plan ${e.bg} · ${e.n} nesne · ${e.kume_sayisi} küme</div>`;
 e.sekiller.forEach(sk=>{
   const row=document.createElement('div');row.className='grp';
   const cv=document.createElement('canvas');drawShape(cv,sk.mask,sk.h,sk.w,COLORS[sk.renkler[0]]);
   const txt=document.createElement('div');txt.style.fontSize='11px';
   txt.innerHTML=`<b style="color:#7CFC9E">küme K${sk.token}</b> · <b>${sk.adet} nesne</b>`
     +` · <span style="color:#88D8F1">${sk.ornek_sayisi} token</span>`
     +`<br><span class="muted">${sk.h}×${sk.w} · ${sk.boyut}px · renk ${sk.renkler.join(',')}</span>`;
   row.appendChild(cv);row.appendChild(txt);eb.appendChild(row);
 });
 // hand
 const h=s.hand;let hh=`<div><b>${h.desc||'-'}</b></div>`;
 if(h.touched)hh+=`<div>değdiği: <b>${h.touched}</b></div>`;
 if(h.olu)hh+=`<div style="color:#ff8a8a">⚠ ETKİSİZ (ölü durum — reset gerekebilir)</div>`;
 if(h.yeni&&h.yeni.length)hh+=`<div style="color:#7CFC9E">yeni olay-token: ${h.yeni.join(' · ')}</div>`;
 document.getElementById('handbody').innerHTML=hh;
 // brain — olay tokenlari (sayisal)
 const t=s.brain;
 if(!t.length){document.getElementById('brainbody').innerHTML='<span class="muted">henüz olay-token yok (0)</span>';}
 else{let bt='<table>';t.forEach(a=>{bt+=`<tr><td class="cnt">${a.sayi}×</td><td><b style="color:#7CFC9E">#${a.token}</b> ${a.desc}<div class="muted">${a.aksiyon} · ilk: adım ${a.ilk_adim}</div></td></tr>`;});bt+='</table>';document.getElementById('brainbody').innerHTML=bt;}
 // num buttons
 const nb=document.getElementById('nums');nb.innerHTML='';
 [0,1,2,3,4,5,7].forEach(a=>{const btn=document.createElement('button');btn.textContent=a;if(s.available.includes(a)||a===0)btn.style.borderColor='#4a6cff';btn.onclick=()=>act(a);nb.appendChild(btn);});
}
function lum(hex){if(!hex)return 0;const r=parseInt(hex.slice(1,3),16),g=parseInt(hex.slice(3,5),16),b=parseInt(hex.slice(5,7),16);return(0.299*r+0.587*g+0.114*b)/255;}
function drawShape(cv,mask,h,w,color){
 // buyuk sekilleri kucult: en fazla ~46px, hucre 1..10px
 const cell=Math.max(1,Math.min(10,Math.floor(46/Math.max(h,w||1))));
 cv.width=Math.max(1,w*cell);cv.height=Math.max(1,h*cell);
 cv.style.background='#0a0c11';cv.style.border='1px solid #222';cv.style.borderRadius='3px';cv.style.flex='0 0 auto';
 const ctx=cv.getContext('2d');ctx.fillStyle=color||'#f0f';
 (mask||[]).forEach(p=>ctx.fillRect(p[1]*cell,p[0]*cell,cell,cell));
}

async function step(){render(await api('/api/step'));}
async function act(a,x,y){render(await api('/api/act',{action:a,x:x,y:y}));}
async function reset(){render(await api('/api/reset'));}
async function wipe(){render(await api('/api/wipe'));}
async function selGame(g){render(await api('/api/game',{game:g}));}

document.addEventListener('keydown',e=>{if(e.code==='Space'){e.preventDefault();step();}});
(async()=>{
 const sel=document.getElementById('gamesel');
 %GAMES%.forEach(g=>{const o=document.createElement('option');o.value=g;o.textContent=g;sel.appendChild(o);});
 sel.onchange=()=>selGame(sel.value);
 render(await get());
})();
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
            page = PAGE.replace("%COLORS%", json.dumps(COLOR_MAP)).replace("%GAMES%", json.dumps(GAMES))
            self._send(200, page, "text/html; charset=utf-8")
        elif p == "/api/state":
            with _LOCK: self._send(200, json.dumps(SES.snapshot()))
        else:
            self._send(404, b"{}")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        global SES
        with _LOCK:
            try:
                if self.path == "/api/step":
                    kind, a, x, y = SES.next_explore(); SES.do(kind, a, x, y)
                elif self.path == "/api/act":
                    a = int(body["action"])
                    if a == 6: SES.do("click", 6, int(body["x"]), int(body["y"]))
                    else: SES.do("press", a, None, None)
                elif self.path == "/api/reset":
                    SES.hand.reset(); SES.clicked_shapes = set()
                    SES.prev_level = SES.hand.last["levels_completed"]
                    SES.last_hand = {"desc": "RESET", "touched": None, "action": 0}
                elif self.path == "/api/wipe":
                    SES.mind = Mind(); SES.tried = set()
                elif self.path == "/api/game":
                    SES.start(body["game"])
                else:
                    self._send(404, b"{}"); return
                self._send(200, json.dumps(SES.snapshot()))
            except Exception as e:
                import traceback; traceback.print_exc()
                self._send(200, json.dumps({"error": str(e)}))


if __name__ == "__main__":
    port = int(os.environ.get("BRAIN_PORT", "8001"))
    print(f"Ajan gozlem -> http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
