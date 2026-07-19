#!/usr/bin/env python3
"""ARC-AGI-3 local game player + not defteri.

Solda oyun (sadece numarali aksiyon butonlari, ipucu YOK).
Sagda o oyuna ait not defteri -> notes/<oyun>.txt olarak kaydolur.

Calistir:  cd ARC-AGI-3-Agents && uv run python ../player/server.py
Tarayici:  http://localhost:8000
"""
import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

os.environ.setdefault("OPERATION_MODE", "offline")
os.environ.setdefault(
    "ENVIRONMENTS_DIR", "/home/adem/Desktop/AGI/environment_files"
)
os.environ.setdefault("MPLBACKEND", "agg")

from arc_agi import Arcade  # noqa: E402
from arcengine import GameAction, ActionInput  # noqa: E402

# Her tipten 1 oyun (1 click + 1 keyboard + 1 keyboard_click + 1 none).
# SABIT karisik sira, hangisinin hangi tip oldugu belli olmasin diye.
# En ustte click oyunu YOK.
GAMES = [
    "g50t",  # keyboard
    "lf52",  # click  (uzerinde calisilan, svy 3)
    "ft09",  # none
    "m0r0",  # keyboard_click
]

NOTES_DIR = "/home/adem/Desktop/AGI/player/notes"
os.makedirs(NOTES_DIR, exist_ok=True)

COLOR_MAP = {
    0: "#FFFFFF", 1: "#CCCCCC", 2: "#999999", 3: "#666666",
    4: "#333333", 5: "#000000", 6: "#E53AA3", 7: "#FF7BCC",
    8: "#F93C31", 9: "#1E93FF", 10: "#88D8F1", 11: "#FFDC00",
    12: "#FF851B", 13: "#921231", 14: "#4FCC30", 15: "#A356D6",
}

ARC = Arcade()
_LOCK = threading.Lock()
ENVS = {}


def list_games():
    # Sabit sirali, sadece secili 10 oyun. (base, base) doner.
    return [[g, g] for g in GAMES]


def frame_payload(fr):
    grids = [[[int(v) for v in row] for row in grid] for grid in fr.frame]
    return {
        "grids": grids,
        "state": fr.state.name if hasattr(fr.state, "name") else str(fr.state),
        "levels_completed": getattr(fr, "levels_completed", 0),
        "win_levels": getattr(fr, "win_levels", None),
        "available_actions": list(getattr(fr, "available_actions", []) or []),
    }


def notes_target_level(game):
    """Txt'deki en yuksek 'SEVIYE N' -> 0-index'li seviye. Yoksa 0."""
    txt = read_notes(game)
    nums = [int(m) for m in re.findall(r"SEVIYE\s+(\d+)", txt)]
    return (max(nums) - 1) if nums else 0


def jump_level(env, target_idx):
    """Oyunu target_idx seviyesine atlat ve o seviyenin frame'ini dondur.
    set_level _action_count'u sifirlar; RESET'te full_reset olmasin diye
    1 yapip level_reset ile hedef seviyeyi render ettiriyoruz."""
    g = env._game
    try:
        g.set_level(target_idx)
    except Exception:
        return env._last_response  # aralik disi -> seviye 0'da kal
    g._action_count = 1
    g._score = target_idx
    fr = g.perform_action(ActionInput(id=GameAction.RESET), raw=True)
    fr.guid = env._guid
    fr.game_id = env.environment_info.game_id
    env._set_last_response(fr)
    return fr


def make_and_reset(game):
    with _LOCK:
        env = ARC.make(game)
        if env is None:
            return None
        ENVS[game] = env
        fr = env.reset()
        target = notes_target_level(game)   # txt'de kalinan seviye
        if target > 0:
            fr = jump_level(env, target)
        return frame_payload(fr)


def do_step(game, action_int, x=None, y=None):
    with _LOCK:
        env = ENVS.get(game)
        if env is None:
            env = ARC.make(game)
            ENVS[game] = env
            env.reset()
        name = "RESET" if action_int == 0 else f"ACTION{action_int}"
        action = GameAction[name]
        data = {"x": int(x), "y": int(y)} if action_int == 6 else None
        return frame_payload(env.step(action, data))


def notes_path(game):
    safe = "".join(c for c in game if c.isalnum() or c in "-_")
    return os.path.join(NOTES_DIR, f"{safe}.txt")


def read_notes(game):
    p = notes_path(game)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return f.read()
    return ""


def write_notes(game, text):
    with open(notes_path(game), "w", encoding="utf-8") as f:
        f.write(text)


HTML = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>ARC-AGI-3 Player + Notlar</title>
<style>
  :root{color-scheme:dark}
  *{box-sizing:border-box}
  body{margin:0;background:#0d0f14;color:#e6e6e6;font:14px system-ui,sans-serif;height:100vh;display:flex;flex-direction:column;overflow:hidden}
  #top{display:flex;align-items:center;gap:14px;padding:8px 14px;background:#151822;border-bottom:1px solid #262b38;flex-wrap:wrap}
  select{background:#1b1f2b;color:#e6e6e6;border:1px solid #3a4256;border-radius:6px;padding:6px 10px;font-size:14px}
  .badge{padding:4px 10px;border-radius:6px;background:#1b1f2b;border:1px solid #2a3040;font-size:13px}
  .win{background:#14361c;border-color:#2f7d3f;color:#7CFC9E}
  .over{background:#3a1414;border-color:#7d2f2f;color:#ff8a8a}
  #wrap{flex:1;display:flex;overflow:hidden}
  #left{flex:0 0 auto;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;padding:18px;border-right:1px solid #262b38}
  #board{display:grid;background:#000;border:2px solid #333;image-rendering:pixelated}
  .cell{width:15px;height:15px;display:flex;align-items:center;justify-content:center;font:10px/1 ui-monospace,monospace;font-weight:700;user-select:none}
  #btns{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;max-width:600px}
  button{background:#1b1f2b;color:#cfe;border:1px solid #3a4256;border-radius:8px;padding:10px 16px;cursor:pointer;font-size:15px;font-weight:600;min-width:52px}
  button:hover{background:#2a3350;border-color:#4a6cff}
  button.avail{border-color:#4a6cff;background:#212a45}
  button.reset{color:#ffb0b0;border-color:#5a3040}
  #hint{font-size:12px;color:#7a869a}
  #right{flex:1;display:flex;flex-direction:column;min-width:0}
  #notesHead{padding:8px 14px;background:#151822;border-bottom:1px solid #262b38;display:flex;justify-content:space-between;align-items:center;font-size:13px;color:#8aa}
  #notes{flex:1;width:100%;background:#0a0c11;color:#d8e0ea;border:0;outline:0;resize:none;padding:14px;font:14px/1.6 ui-monospace,monospace}
  #save{color:#6b7688;font-size:12px}
</style></head>
<body>
<div id="top">
  <select id="gamesel"><option value="">— oyun sec —</option></select>
  <span id="title" class="badge">oyun secilmedi</span>
  <span id="mode" class="badge">MOD: NOT ✍</span>
  <span id="hud"></span>
</div>
<div id="wrap">
  <div id="left">
    <div id="board"></div>
    <div id="btns"></div>
    <div id="hint">0 = RESET (sabit) &nbsp;·&nbsp; grid'e sol tik = ACTION6 (sabit) &nbsp;·&nbsp; 1 2 3 4 5 7 = kesfet.<br><b>F3</b> = NOT / OYUN modu degistir. OYUN modunda 0 1 2 3 4 5 7 tuslari aksiyon olur (6 = grid'e tik).</div>
  </div>
  <div id="right">
    <div id="notesHead"><span>NOT DEFTERI (otomatik kaydedilir)</span><span id="save"></span></div>
    <textarea id="notes" placeholder="1- Ne goruyorsun? Ne oldu? Buraya yaz. Enter = yeni numarali satir."></textarea>
  </div>
</div>
<script>
const COLORS = %COLORS%;
let curGame=null, curActions=[], curLevel=null;
const notes=document.getElementById('notes');

async function api(path,body){
  const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
  return r.json();
}
async function loadGames(){
  const r=await fetch('/api/games'); const games=await r.json();
  const sel=document.getElementById('gamesel');
  games.forEach(([base,full])=>{
    const o=document.createElement('option'); o.value=base; o.textContent=base; sel.appendChild(o);
  });
  sel.onchange=()=>{ if(sel.value) selectGame(sel.value); };
}
async function selectGame(base){
  curGame=base;
  document.getElementById('title').textContent=base+' (yukleniyor...)';
  // notlari yukle
  const nr=await fetch('/api/notes?game='+encodeURIComponent(base));
  const nt=await nr.json();
  notes.value=(nt.text&&nt.text.length)?nt.text:'===== SEVIYE 1 =====\n1- ';
  curLevel=null;                 // yeni oyun: taban seviye, baslik atma
  const p=await api('/api/make',{game:base});
  render(p);
  setMode('notes');
}

// --- MOD: NOT (klavye txt'ye yazar) / OYUN (0-7 tuslari aksiyon) ---
let mode='notes';
function setMode(m){
  mode=m;
  const badge=document.getElementById('mode');
  if(m==='notes'){ notes.focus(); placeCursorEnd(); badge.textContent='MOD: NOT ✍ (F3=oyun)'; badge.className='badge'; }
  else { notes.blur(); badge.textContent='MOD: OYUN 🎮 (F3=not)'; badge.className='badge win'; }
}
document.addEventListener('keydown',e=>{
  if(e.key==='F3'){ e.preventDefault(); setMode(mode==='notes'?'game':'notes'); return; }
  if(mode==='game' && curGame){
    if(['0','1','2','3','4','5','7'].includes(e.key)){ e.preventDefault(); doAction(parseInt(e.key)); }
  }
});
function txtColor(hex){
  // arka plan koyuysa acik yazi, aciksa koyu yazi
  const r=parseInt(hex.slice(1,3),16), g=parseInt(hex.slice(3,5),16), b=parseInt(hex.slice(5,7),16);
  const lum=(0.299*r+0.587*g+0.114*b)/255;
  return lum>0.55 ? 'rgba(0,0,0,.75)' : 'rgba(255,255,255,.85)';
}
function render(p){
  if(!p||!p.grids){document.getElementById('title').textContent='HATA';return;}
  curActions=p.available_actions||[];
  // seviye atladiysak nota bosluk + baslik dus
  const lvl=p.levels_completed||0;
  if(curLevel!==null && lvl>curLevel) onLevelUp(lvl);
  curLevel=lvl;
  document.getElementById('title').textContent=curGame;
  // sadece SON kare (nihai durum)
  const grid=p.grids[p.grids.length-1], n=grid.length;
  const b=document.getElementById('board');
  b.innerHTML=''; b.style.gridTemplateColumns=`repeat(${n},15px)`;
  grid.forEach((row,y)=>row.forEach((v,x)=>{
    const c=document.createElement('div'); c.className='cell';
    const bg=COLORS[v]||'#f0f';
    c.style.background=bg;
    c.textContent=v;                 // hucrenin uzerine sayi (0-15)
    c.style.color=txtColor(bg);      // arka plana gore kontrast yazi rengi
    c.onclick=()=>doAction(6,x,y);
    b.appendChild(c);
  }));
  // butonlar: 0=RESET (sabit) + 1,2,3,4,5,7 (anlamsiz numara). 6 = grid'e sol tik.
  const bb=document.getElementById('btns'); bb.innerHTML='';
  const rb=document.createElement('button'); rb.textContent='0'; rb.className='reset'; rb.title='RESET (sabit)';
  rb.onclick=()=>doAction(0); bb.appendChild(rb);
  [1,2,3,4,5,7].forEach(a=>{
    const btn=document.createElement('button'); btn.textContent=a;
    if(curActions.includes(a)) btn.className='avail';
    btn.onclick=()=>doAction(a);
    bb.appendChild(btn);
  });
  const st=p.state, hud=document.getElementById('hud');
  let cls=st==='WIN'?'badge win':(st==='GAME_OVER'?'badge over':'badge');
  const anim=p.grids.length>1?`<span class="badge">animasyon: ${p.grids.length} kare</span>`:'';
  hud.innerHTML=`<span class="${cls}">${st}</span>`
    +`<span class="badge">Seviye: ${p.levels_completed}/${p.win_levels??'?'}</span>`
    +anim
    +`<span class="badge">gecerli: [${curActions.join(', ')}]</span>`;
}
async function doAction(a,x,y){
  if(!curGame)return;
  // once nota makine-okur token dus:  [A0] [A1]..[A5] [A7]  ve  [A6@x,y]
  const tok = a===6?`[A6@${x},${y}]` : `[A${a}]`;
  logToken(tok);
  const p=await api('/api/step',{game:curGame,action:a,x:x,y:y});
  render(p);
}
function logToken(tok){
  // Her aksiyon YENI numarali satira, token satirin BASINA.
  let v=notes.value;
  const lines=v.split('\n');
  const last=lines[lines.length-1];
  if(/^\s*\d+-\s*$/.test(last)){
    // son satir bos numarali satir -> token'i onun basina koy
    lines[lines.length-1]=last.replace(/\s*$/,'')+' '+tok+' ';
    notes.value=lines.join('\n');
  } else {
    if(v.length && !v.endsWith('\n')) v+='\n';
    v+=nextNum(v)+'- '+tok+' ';
    notes.value=v;
  }
  placeCursorEnd();
  saveNotes();
}
function onLevelUp(lvl){
  // 4-5 satir bosluk + "SEVIYE N" baslik + yeni numarali satir
  let v=notes.value;
  if(v.length && !v.endsWith('\n')) v+='\n';
  v+='\n\n\n\n===== SEVIYE '+(lvl+1)+' =====\n';
  v+=nextNum(v)+'- ';
  notes.value=v;
  placeCursorEnd(); saveNotes();
}
function nextNum(v){
  // numara her SEVIYE basliginda 1'den baslar: son SEVIYE satirindan sonrasini say
  const lines=v.split('\n');
  let start=0;
  for(let i=lines.length-1;i>=0;i--){ if(/SEVIYE/.test(lines[i])){ start=i+1; break; } }
  const m=lines.slice(start).filter(l=>/^\s*\d+\s*-/.test(l));
  return m.length+1;
}
function placeCursorEnd(){ notes.selectionStart=notes.selectionEnd=notes.value.length; }
// Enter -> yeni numarali satir
notes.addEventListener('keydown',e=>{
  if(e.key==='Enter'){
    e.preventDefault();
    const v=notes.value, s=notes.selectionStart;
    const ins='\n'+nextNum(v)+'- ';
    notes.value=v.slice(0,s)+ins+v.slice(notes.selectionEnd);
    notes.selectionStart=notes.selectionEnd=s+ins.length;
    saveNotes();
  }
});
let saveT=null;
notes.addEventListener('input',saveNotes);
function saveNotes(){
  if(!curGame)return;
  document.getElementById('save').textContent='kaydediliyor...';
  clearTimeout(saveT);
  saveT=setTimeout(async()=>{
    await api('/api/notes',{game:curGame,text:notes.value});
    document.getElementById('save').textContent='kaydedildi ✓';
  },350);
}
loadGames();
</script>
</body></html>
"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            page = HTML.replace("%COLORS%", json.dumps(COLOR_MAP))
            self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
        elif parsed.path == "/api/games":
            self._send(200, json.dumps(list_games()).encode())
        elif parsed.path == "/api/notes":
            q = parse_qs(parsed.query)
            game = (q.get("game") or [""])[0]
            self._send(200, json.dumps({"text": read_notes(game)}).encode())
        else:
            self._send(404, b"{}")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        try:
            if self.path == "/api/make":
                p = make_and_reset(body["game"])
            elif self.path == "/api/step":
                p = do_step(body["game"], int(body["action"]),
                            body.get("x"), body.get("y"))
            elif self.path == "/api/notes":
                write_notes(body["game"], body.get("text", ""))
                p = {"ok": True}
            else:
                self._send(404, b"{}")
                return
            self._send(200, json.dumps(p).encode())
        except Exception as e:
            self._send(200, json.dumps({"error": str(e)}).encode())


if __name__ == "__main__":
    port = int(os.environ.get("PLAYER_PORT", "8000"))
    print(f"ARC-AGI-3 Player + Notlar -> http://localhost:{port}")
    print("Notlar klasoru:", NOTES_DIR)
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
