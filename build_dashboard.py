#!/usr/bin/env python3
"""
LeetCode class dashboard builder.

Usage:
  python build_dashboard.py
  python build_dashboard.py --csv students.csv        # if the sheet can't be downloaded
  python build_dashboard.py --sheet "<google sheet url>" --out dashboard.html

Needs only Python 3.8+ (standard library). Open dashboard.html in any browser.
Re-run the script any time to refresh the numbers.
"""
import argparse, csv, io, json, re, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

DEFAULT_SHEET = "https://docs.google.com/spreadsheets/d/1iNjo4Sq5zUpeJ6UT2NhSu49mUePS445gCkNwE8vMyjk/edit?usp=sharing"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"

QUERY = """query($u:String!){
  matchedUser(username:$u){ username profile{ ranking userAvatar }
    submitStatsGlobal{ acSubmissionNum{ difficulty count } } }
  allQuestionsCount{ difficulty count } }"""


def http(url, data=None, headers=None, timeout=25):
    h = {"User-Agent": UA}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def load_rows(sheet_url, csv_path):
    if csv_path:
        text = open(csv_path, encoding="utf-8-sig").read()
    else:
        m = re.search(r"/d/([\w-]+)", sheet_url)
        if not m:
            sys.exit("Could not read the sheet id from the URL.")
        gid = re.search(r"gid=(\d+)", sheet_url)
        url = f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv"
        if gid:
            url += f"&gid={gid.group(1)}"
        try:
            text = http(url).decode("utf-8-sig")
        except Exception as e:
            sys.exit(f"Could not download the sheet ({e}).\nSet sharing to 'Anyone with the link: Viewer', "
                     "or File > Download > CSV and run with --csv file.csv")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        sys.exit("Sheet is empty.")
    head = [h.strip().lower() for h in rows[0]]

    def find(*keys, avoid=()):
        for i, h in enumerate(head):
            if any(k in h for k in keys) and not any(a in h for a in avoid):
                return i
        return None

    c_lc = find("leetcode", "leet", "profile", "link")
    c_usn = find("usn", "roll", "reg")
    c_name = find("name", avoid=("usn", "leetcode", "user"))
    if c_lc is None:
        sys.exit(f"No LeetCode column found. Headers seen: {rows[0]}")
    out = []
    for r in rows[1:]:
        get = lambda i: r[i].strip() if i is not None and i < len(r) else ""
        if not any(x.strip() for x in r):
            continue
        out.append({"name": get(c_name), "usn": get(c_usn).upper(), "link": get(c_lc)})
    return out


def username_from(link):
    link = link.strip()
    if not link:
        return ""
    m = re.search(r"leetcode\.(?:com|cn)/(?:u/|profile/)?([^/?#\s]+)", link, re.I)
    return (m.group(1) if m else link.lstrip("@")).strip("/")


def fetch_stats(user):
    body = json.dumps({"query": QUERY, "variables": {"u": user}}).encode()
    hdr = {"Content-Type": "application/json", "Referer": "https://leetcode.com/" + user}
    for attempt in range(3):
        try:
            d = json.loads(http("https://leetcode.com/graphql", body, hdr))["data"]
            mu = d["matchedUser"]
            if not mu:
                return {"error": "Profile not found"}
            ac = {x["difficulty"]: x["count"] for x in mu["submitStatsGlobal"]["acSubmissionNum"]}
            tot = {x["difficulty"]: x["count"] for x in d["allQuestionsCount"]}
            return {
                "solved": ac.get("All", 0), "easy": ac.get("Easy", 0),
                "medium": ac.get("Medium", 0), "hard": ac.get("Hard", 0),
                "tAll": tot.get("All", 0), "tEasy": tot.get("Easy", 0),
                "tMedium": tot.get("Medium", 0), "tHard": tot.get("Hard", 0),
                "rank": mu["profile"].get("ranking"), "avatar": mu["profile"].get("userAvatar"),
            }
        except Exception as e:
            err = str(e)
            time.sleep(1.5 * (attempt + 1))
    return {"error": err}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", default=DEFAULT_SHEET)
    ap.add_argument("--csv")
    ap.add_argument("--out", default="dashboard.html")
    a = ap.parse_args()

    rows = load_rows(a.sheet, a.csv)
    print(f"{len(rows)} students found. Fetching LeetCode stats...")

    def work(s):
        u = username_from(s["link"])
        s["username"] = u
        s.update(fetch_stats(u) if u else {"error": "No profile link"})
        print(f"  {s['usn'] or s['name'] or u}: {s.get('solved', s.get('error'))}")
        return s

    with ThreadPoolExecutor(6) as ex:
        data = list(ex.map(work, rows))

    html = TEMPLATE.replace("__DATA__", json.dumps(data)).replace(
        "__STAMP__", datetime.now().strftime("%d %b %Y, %H:%M"))
    open(a.out, "w", encoding="utf-8").write(html)
    ok = sum(1 for s in data if "error" not in s)
    print(f"Done. {ok}/{len(data)} profiles fetched. Open {a.out} in your browser.")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LeetCode Class Dashboard</title>
<style>
:root{--bg:#f4f5f7;--card:#fff;--tx:#1a1a1a;--mut:#6b7280;--chip:#f5f5f5;--bd:#e5e7eb;
--e:#00b8a3;--m:#ffa116;--h:#ef4743;--ok:#16a34a}
@media(prefers-color-scheme:dark){:root{--bg:#16181d;--card:#22252c;--tx:#f1f1f1;--mut:#9aa0aa;--chip:#2c3039;--bd:#343843}}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--tx)}
header{padding:20px 24px 8px}h1{margin:0;font-size:22px}.sub{color:var(--mut);font-size:13px;margin-top:4px}
.bar{display:flex;flex-wrap:wrap;gap:10px;padding:12px 24px;position:sticky;top:0;background:var(--bg);z-index:5}
input,select,button{font:inherit;padding:8px 12px;border:1px solid var(--bd);border-radius:8px;background:var(--card);color:var(--tx)}
input{flex:1;min-width:200px}button{cursor:pointer}
.stats{display:flex;gap:10px;flex-wrap:wrap;padding:0 24px 8px}
.pill{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:8px 14px;font-size:13px}
.pill b{font-size:16px;display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px;padding:8px 24px 32px}
.card{background:var(--card);border-radius:14px;padding:14px 16px;border:1px solid var(--bd);position:relative}
.top{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.pos{width:30px;height:30px;border-radius:50%;background:var(--chip);display:grid;place-items:center;font-weight:700;font-size:13px;flex:none}
.card:nth-child(-n+3) .pos{background:#ffe08a;color:#6b4a00}
.who{min-width:0}.nm{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.us{font-size:12px;color:var(--mut)}.us a{color:var(--mut)}
.body{display:flex;align-items:center;gap:14px}
.ring{position:relative;width:130px;height:130px;flex:none}
.ring svg{width:100%;height:100%}
.mid{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center}
.mid .n{font-size:30px;font-weight:700;line-height:1}.mid .n small{font-size:12px;font-weight:400;color:var(--mut)}
.mid .s{font-size:12px;color:var(--ok);margin-top:4px}
.chips{flex:1;display:flex;flex-direction:column;gap:7px}
.chip{background:var(--chip);border-radius:8px;text-align:center;padding:6px 4px;font-size:12px}
.chip b{display:block;font-size:14px}
.err{color:var(--h);font-size:13px;padding:30px 0;text-align:center;flex:1}
.hidden{display:none}
</style></head><body>
<header><h1>Dr.TTIT, CSE(AI&ML)</h1><h1>3rd sem DSA OA</h1><h1>LeetCode Class Dashboard</h1><div class="sub">Data fetched __STAMP__ &middot; click a name to open the profile</div></header>
<div class="bar">
<input id="q" placeholder="Search name, USN or username...">
<select id="sort">
<option value="solved">Sort: Total solved</option><option value="easy">Easy</option>
<option value="medium">Medium</option><option value="hard">Hard</option>
<option value="rank">LeetCode rank</option><option value="name">Name</option><option value="usn">USN</option>
</select>
<button id="dir" title="Toggle order">&darr; High to low</button>
<select id="flt"><option value="all">All students</option><option value="zero">Solved 0</option><option value="err">Profile issues</option></select>
</div>
<div class="stats" id="stats"></div>
<div class="grid" id="grid"></div>
<script>
const DATA=__DATA__;
let desc=true;
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function arc(i,frac,color,bg){
  const r=52,C=2*Math.PI*r,seg=C*0.25,gap=C*0.02,rot=135+i*90;
  const len=Math.max(0,seg-gap);
  const f=Math.min(1,frac)*len;
  const t=`rotate(${rot} 65 65)`;
  return `<circle cx="65" cy="65" r="${r}" fill="none" stroke="${color}" stroke-opacity=".18" stroke-width="7" stroke-linecap="round" stroke-dasharray="${len} ${C}" transform="${t}"/>`+
  (f>0?`<circle cx="65" cy="65" r="${r}" fill="none" stroke="${color}" stroke-width="7" stroke-linecap="round" stroke-dasharray="${f} ${C}" transform="${t}"/>`:"");
}
function card(s,i){
  const link=`https://leetcode.com/u/${encodeURIComponent(s.username)}/`;
  const head=`<div class="top"><div class="pos">${i+1}</div><div class="who">
  <div class="nm">${esc(s.name||s.username||"(no name)")}</div>
  <div class="us">${esc(s.usn)}${s.usn&&s.username?" &middot; ":""}${s.username?`<a href="${link}" target="_blank" rel="noopener">@${esc(s.username)}</a>`:""}</div></div></div>`;
  if(s.error) return `<div class="card">${head}<div class="body"><div class="err">${esc(s.error)}</div></div></div>`;
  const ring=`<div class="ring"><svg viewBox="0 0 130 130">${arc(0,s.easy/s.tEasy,"#00b8a3")}${arc(1,s.medium/s.tMedium,"#ffa116")}${arc(2,s.hard/s.tHard,"#ef4743")}</svg>
  <div class="mid"><div class="n">${s.solved}<small>/${s.tAll}</small></div><div class="s">&#10003; Solved</div></div></div>`;
  const ch=(l,c,a,b)=>`<div class="chip"><span style="color:${c};font-weight:600">${l}</span><b>${a}/${b}</b></div>`;
  return `<div class="card">${head}<div class="body">${ring}<div class="chips">${ch("Easy","var(--e)",s.easy,s.tEasy)}${ch("Med.","var(--m)",s.medium,s.tMedium)}${ch("Hard","var(--h)",s.hard,s.tHard)}</div></div></div>`;
}
function render(){
  const q=$("q").value.trim().toLowerCase(),k=$("sort").value,f=$("flt").value;
  let a=DATA.filter(s=>(s.name+" "+s.usn+" "+s.username).toLowerCase().includes(q));
  if(f==="zero")a=a.filter(s=>!s.error&&s.solved===0);
  if(f==="err")a=a.filter(s=>s.error);
  const txt=k==="name"||k==="usn";
  a.sort((x,y)=>{
    let r;
    if(txt)r=(x[k]||"").localeCompare(y[k]||"",undefined,{numeric:true});
    else{
      const nx=x.error?null:(x[k]??null),ny=y.error?null:(y[k]??null);
      if(nx===null&&ny===null)return 0;if(nx===null)return 1;if(ny===null)return -1;
      r=k==="rank"?ny-nx:nx-ny;           // lower rank number = better
    }
    return desc?-r:r;
  });
  $("grid").innerHTML=a.map(card).join("")||'<div class="sub" style="padding:20px">No matches.</div>';
}
function stats(){
  const ok=DATA.filter(s=>!s.error),tot=ok.reduce((n,s)=>n+s.solved,0);
  const P=(l,v)=>`<div class="pill"><b>${v}</b>${l}</div>`;
  $("stats").innerHTML=P("Students",DATA.length)+P("Profiles loaded",ok.length)+P("Total solved",tot)+
   P("Average solved",ok.length?(tot/ok.length).toFixed(1):0)+P("Not started",ok.filter(s=>s.solved===0).length);
}
$("q").oninput=render;$("sort").onchange=render;$("flt").onchange=render;
$("dir").onclick=()=>{desc=!desc;$("dir").innerHTML=desc?"&darr; High to low":"&uarr; Low to high";render()};
stats();render();
</script></body></html>
"""

if __name__ == "__main__":
    main()
