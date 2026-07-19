#!/usr/bin/env python3
"""shape_inspector.py — SEKIL TOKENIZER denetcisi.

6 oyunu birden yukler, TUM sekilleri ORTAK tokenizerdan gecirir, KUMELERE gore
gorsel dizer. "Ayni sekiller ayni kumede mi, farkli sekiller yanlis birlesmis mi"
gozle dogrulamak icin. Esik URL'den ayarlanir:  http://localhost:8002/?t=0.22

Calistir:  cd ARC-AGI-3-Agents && uv run python ../agent/shape_inspector.py
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

os.environ.setdefault("OPERATION_MODE", "offline")
os.environ.setdefault("ENVIRONMENTS_DIR", "/home/adem/Desktop/AGI/environment_files")
os.environ.setdefault("MPLBACKEND", "agg")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import perception as P            # noqa: E402
from transition import ShapeVocab  # noqa: E402
from arc_agi import Arcade        # noqa: E402

COLOR_MAP = {
    0: "#FFFFFF", 1: "#CCCCCC", 2: "#999999", 3: "#666666",
    4: "#333333", 5: "#000000", 6: "#E53AA3", 7: "#FF7BCC",
    8: "#F93C31", 9: "#1E93FF", 10: "#88D8F1", 11: "#FFDC00",
    12: "#FF851B", 13: "#921231", 14: "#4FCC30", 15: "#A356D6",
}
GAMES = ["lf52", "g50t", "ft09", "m0r0", "vc33", "cd82"]
_ARC = Arcade()
_GRIDS = {}


def game_grid(game):
    if game not in _GRIDS:
        fr = _ARC.make(game).reset()
        _GRIDS[game] = [[int(v) for v in row] for row in fr.frame[-1]]
    return _GRIDS[game]


def collect(threshold):
    sv = ShapeVocab(threshold=threshold)
    clusters = {}     # k -> {sekiller:{(mask_key,color):{mask,h,w,color,adet,oyunlar}}, adet}
    total_obj = 0
    for game in GAMES:
        grid = game_grid(game)
        for o in P.find_objects(grid):
            total_obj += 1
            t = sv.token(o)
            k = sv.cluster_of(t)
            c = clusters.setdefault(k, {"kume": k, "sekiller": {}, "adet": 0})
            c["adet"] += 1
            mkey = (o.norm_mask, o.color)
            r0, c0, _, _ = o.bbox
            e = c["sekiller"].get(mkey)
            if e is None:
                c["sekiller"][mkey] = {
                    "mask": [[r - r0, cc - c0] for (r, cc) in o.cells],
                    "h": o.height, "w": o.width, "color": o.color,
                    "boyut": o.size, "adet": 1, "oyunlar": {game}}
            else:
                e["adet"] += 1
                e["oyunlar"].add(game)
    # duzenle
    def pack(clusters):
        out = []
        for k, c in sorted(clusters.items(), key=lambda kv: -kv[1]["adet"]):
            sek = sorted(c["sekiller"].values(), key=lambda s: -s["boyut"])
            out.append({"kume": k, "adet": c["adet"], "farkli": len(sek),
                        "sekiller": [{**s, "oyunlar": sorted(s["oyunlar"])} for s in sek]})
        return out

    # KATMAN 2: bilesik sekiller (ayni tokenizer, yeni sozluk)
    sv2 = ShapeVocab(threshold=threshold)
    clusters2 = {}
    total_comp = 0
    for game in GAMES:
        grid = game_grid(game)
        for o, nmem in P.find_compounds(grid):
            if nmem < 2:
                continue                # sadece GERCEK bilesikleri goster
            total_comp += 1
            t = sv2.token(o)
            k = sv2.cluster_of(t)
            c = clusters2.setdefault(k, {"sekiller": {}, "adet": 0})
            c["adet"] += 1
            r0, c0, _, _ = o.bbox
            mkey = (o.norm_mask, o.color)
            e = c["sekiller"].get(mkey)
            if e is None:
                c["sekiller"][mkey] = {
                    "mask": [[r - r0, cc - c0] for (r, cc) in o.cells],
                    "h": o.height, "w": o.width, "color": o.color,
                    "boyut": o.size, "uye": nmem, "adet": 1, "oyunlar": {game}}
            else:
                e["adet"] += 1
                e["oyunlar"].add(game)

    return {"esik": threshold, "oyunlar": GAMES, "toplam_nesne": total_obj,
            "kume_sayisi": len(clusters), "kumeler": pack(clusters),
            "bilesik_sayisi": total_comp, "kume2_sayisi": len(clusters2),
            "kumeler2": pack(clusters2)}


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>Sekil Tokenizer Denetci</title>
<style>
:root{color-scheme:dark}*{box-sizing:border-box}
body{margin:0;background:#0d0f14;color:#e6e6e6;font:13px system-ui,sans-serif;padding:14px}
h1{font-size:16px;margin:0 0 4px}
#top{position:sticky;top:0;background:#0d0f14;padding-bottom:10px;border-bottom:1px solid #262b38;margin-bottom:12px}
.badge{padding:3px 8px;border-radius:6px;background:#1b1f2b;border:1px solid #2a3040;font-size:12px;margin-right:6px}
.kume{border:1px solid #2a3040;border-radius:10px;padding:10px;margin-bottom:12px;background:#12151d}
.khead{font-weight:700;color:#7CFC9E;margin-bottom:8px}
.shapes{display:flex;flex-wrap:wrap;gap:10px}
.sh{display:flex;flex-direction:column;align-items:center;gap:3px;padding:6px;border:1px solid #222;border-radius:8px;background:#0a0c11;min-width:60px}
.sh small{color:#8aa;font-size:10px;text-align:center;line-height:1.3}
input{background:#1b1f2b;color:#cfe;border:1px solid #3a4256;border-radius:6px;padding:5px 8px;width:80px}
button{background:#1b2540;color:#cfe;border:1px solid #3a4256;border-radius:6px;padding:5px 12px;cursor:pointer}
</style></head><body>
<div id="top">
 <h1>🔬 Şekil Tokenizer Denetçisi</h1>
 <div id="stats"></div>
 <div style="margin-top:8px">
   benzerlik eşiği: <input id="t" type="number" step="0.02" min="0.05" max="1">
   <button onclick="reload()">yenile</button>
   <span class="badge">düşük eşik = çok küme (ayrık) · yüksek = az küme (birleşik)</span>
 </div>
</div>
<div id="body"></div>
<script>
const COLORS=%COLORS%;
function drawShape(cv,mask,h,w,color){
 const cell=Math.max(2,Math.min(12,Math.floor(48/Math.max(h,w||1))));
 cv.width=Math.max(1,w*cell);cv.height=Math.max(1,h*cell);
 cv.style.background='#000';cv.style.borderRadius='3px';
 const x=cv.getContext('2d');x.fillStyle=color||'#f0f';
 (mask||[]).forEach(p=>x.fillRect(p[1]*cell,p[0]*cell,cell,cell));
}
async function load(t){
 const r=await fetch('/api/data'+(t?('?t='+t):''));const d=await r.json();
 document.getElementById('t').value=d.esik;
 document.getElementById('stats').innerHTML=
   `<span class="badge">oyunlar: ${d.oyunlar.join(', ')}</span>`
  +`<span class="badge">${d.toplam_nesne} nesne</span>`
  +`<span class="badge">${d.kume_sayisi} KÜME</span>`
  +`<span class="badge">eşik ${d.esik}</span>`;
 const body=document.getElementById('body');body.innerHTML='';
 function renderClusters(list, comp){
   list.forEach(k=>{
     const div=document.createElement('div');div.className='kume';
     const hd=document.createElement('div');hd.className='khead';
     hd.textContent=`Küme K${k.kume} — ${k.adet} nesne · ${k.farkli} farklı şekil`;
     div.appendChild(hd);
     const sc=document.createElement('div');sc.className='shapes';
     k.sekiller.forEach(s=>{
       const box=document.createElement('div');box.className='sh';
       const cv=document.createElement('canvas');drawShape(cv,s.mask,s.h,s.w,COLORS[s.color]||'#888');
       const lb=document.createElement('small');
       const uye=comp?`<br><b style="color:#FFDC00">${s.uye} üye</b>`:'';
       lb.innerHTML=`${s.h}×${s.w} · renk${s.color}<br>${s.boyut}px ×${s.adet}${uye}<br>${s.oyunlar.join(',')}`;
       box.appendChild(cv);box.appendChild(lb);sc.appendChild(box);
     });
     div.appendChild(sc);body.appendChild(div);
   });
 }
 const h1=document.createElement('h2');h1.style.color='#7CFC9E';
 h1.textContent=`KATMAN 1 — temel şekiller (${d.kume_sayisi} küme)`;body.appendChild(h1);
 renderClusters(d.kumeler,false);
 const h2=document.createElement('h2');h2.style.color='#FFDC00';h2.style.marginTop='20px';
 h2.textContent=`KATMAN 2 — bileşik şekiller (${d.bilesik_sayisi} bileşik, ${d.kume2_sayisi} küme)`;body.appendChild(h2);
 renderClusters(d.kumeler2||[],true);
}
function reload(){load(document.getElementById('t').value);}
load();
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            self._send(200, PAGE.replace("%COLORS%", json.dumps(COLOR_MAP)),
                       "text/html; charset=utf-8")
        elif u.path == "/api/data":
            q = parse_qs(u.query)
            t = float((q.get("t") or ["0.22"])[0])
            self._send(200, json.dumps(collect(t)))
        else:
            self._send(404, b"{}")


if __name__ == "__main__":
    port = int(os.environ.get("INSPECT_PORT", "8002"))
    print(f"Sekil tokenizer denetci -> http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
