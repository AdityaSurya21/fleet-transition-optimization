"""
Builds an animated, self-contained HTML deck from the model results.

Run:  python make_deck.py data out deck/fleet_transition_deck.html
      (out/ is the folder fleet_transition_solver.py writes: results.json and solution.csv)
Every number, chart and animation is driven by the data files and the solver output.
"""
import json
import re
import sys
import pandas as pd

DATA, RES, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
r = json.load(open(f"{RES}/results.json"))
sol = pd.read_csv(f"{RES}/solution.csv")
YEARS = [int(y) for y in r["per_year"]]
PY = {int(k): v for k, v in r["per_year"].items()}

dem = pd.read_csv(f"{DATA}/demand.csv"); dem.columns = ["Y", "S", "D", "km"]
caps = pd.read_csv(f"{DATA}/carbon_emissions.csv"); caps.columns = ["Y", "cap"]
fuels = pd.read_csv(f"{DATA}/fuels.csv"); fuels.columns = ["F", "Y", "co2", "p", "u"]
veh = pd.read_csv(f"{DATA}/vehicles.csv"); veh.columns = ["ID", "T", "S", "Y", "cost", "rng", "D"]
vf = pd.read_csv(f"{DATA}/vehicles_fuels.csv"); vf.columns = ["ID", "F", "cons"]
prof = pd.read_csv(f"{DATA}/cost_profiles.csv"); prof.columns = ["age", "res", "ins", "mnt"]

tot_dem = dem.groupby("Y").km.sum()
cap_full = caps.set_index("Y").cap
CONS = {(a.ID, a.F): a.cons for a in vf.itertuples()}
FU = {(a.F, a.Y): a for a in fuels.itertuples()}
V = veh.set_index("ID")

# solver bound (if the log is there)
lb, gap = r.get("lower_bound"), (r["gap"] * 100 if r.get("gap") is not None else None)
if lb is None:
  try:
    log = open(f"{RES}/solver_log.txt").read()
    lb = float(re.search(r"Dual bound\s+([\d.]+)", log).group(1))
    gap = float(re.search(r"Gap\s+([\d.]+)%", log).group(1))
  except Exception:
    pass

bs = sol[sol.Type != "Use"].groupby(["Year", "Type"]).Num_Vehicles.sum().unstack().reindex(YEARS).fillna(0)

trucks = []
for t, fu in [("Diesel", "B20"), ("Diesel", "HVO"), ("LNG", "LNG"), ("LNG", "BioLNG"), ("BEV", "Electricity")]:
    vid = f"{t}_S1_2023"
    f = FU[fu, 2023]
    trucks.append({"t": t, "fuel": fu, "price": int(V.cost[vid]), "perkm": round(CONS[vid, fu] * f.p, 3),
                   "co2": round(CONS[vid, fu] * f.co2, 3), "route": int(V.D[vid][1])})

bev_price = {int(y): int(V.cost[f"BEV_S1_{y}"]) for y in YEARS}
bev_route = {int(y): int(V.D[f"BEV_S1_{y}"][1]) for y in YEARS}

g23 = dem[dem.Y == 2023].set_index(["S", "D"]).km
D = {
    "years": YEARS,
    "bev": [PY[y]["fleet"].get("BEV", 0) for y in YEARS],
    "lng": [PY[y]["fleet"].get("LNG", 0) for y in YEARS],
    "dsl": [PY[y]["fleet"].get("Diesel", 0) for y in YEARS],
    "km": {f: [PY[y]["km_by_fuel"].get(f, 0) for y in YEARS] for f in ["LNG", "BioLNG", "Electricity", "B20", "HVO"]},
    "em": [PY[y]["emissions"] for y in YEARS],
    "cap": [r["cap"][str(y)] for y in YEARS],
    "cost": {k: [PY[y]["cost"][k] for y in YEARS] for k in ["buy", "insurance", "maintenance", "fuel", "resale"]},
    "buys": bs["Buy"].astype(int).tolist(), "sells": bs["Sell"].astype(int).tolist(),
    "demIdx": [tot_dem[y] / tot_dem[2023] * 100 for y in range(2023, 2039)],
    "capIdx": [cap_full[y] / cap_full[2023] * 100 for y in range(2023, 2039)],
    "dem0": float(tot_dem[2023]), "dem1": float(tot_dem[2038]),
    "cap0": float(cap_full[2023]), "cap1": float(cap_full[2038]),
    "trucks": trucks, "bevPrice": bev_price, "bevRoute": bev_route,
    "resale": prof.res.tolist(), "runcum": (prof.ins + prof.mnt).cumsum().tolist(),
    "grid": {s: {d: float(g23[s, d]) for d in ["D1", "D2", "D3", "D4"]} for s in ["S1", "S2", "S3", "S4"]},
    "total": r["total_cost"], "lb": lb, "gap": gap, "nModels": len(veh),
}

HTML = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>Fleet transition: the lowest-cost path to a zero-emission truck fleet</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#0e1a23;--bg2:#13232f;--card:#172a37;--line:#253b4b;--ink:#eef1ec;--mut:#93a6b4;--acc:#f0a23b;
--bev:#2bb39a;--lng:#4a82d0;--bio:#9cc4f2;--dsl:#e0674a;--cap:#ff7a59;--hd:'Space Grotesk',Inter,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:#070d12;overflow:hidden;font-family:Inter,'Segoe UI',Arial,sans-serif;color:var(--ink)}
#stage{position:absolute;left:50%;top:50%;width:1920px;height:1080px;transform-origin:center;overflow:hidden;background:radial-gradient(ellipse at 30% 20%,#13283a,#0b151d 70%)}
.slide{position:absolute;inset:0;padding:96px 128px 140px;opacity:0;visibility:hidden;transform:scale(1.06);filter:blur(12px);
 transition:opacity .8s,visibility .8s,transform 1s cubic-bezier(.2,.8,.2,1),filter .8s}
.slide.active{opacity:1;visibility:visible;transform:none;filter:none}
.slide > :not(.bggrid):not(.scene):not(.road):not(.footer){position:relative;z-index:2}
#fx{position:absolute;left:0;top:0;width:1920px;height:1080px}
.aurora{position:absolute;inset:-300px;opacity:.75;pointer-events:none}
.aurora i{position:absolute;border-radius:50%;width:1000px;height:760px;animation:blob 24s ease-in-out infinite alternate}
.aurora i:nth-child(1){background:radial-gradient(closest-side,#16506ecc,#16506e00);left:-120px;top:-120px}
.aurora i:nth-child(2){background:radial-gradient(closest-side,#1f8a7877,#1f8a7800);right:-60px;top:380px;animation-duration:30s}
.aurora i:nth-child(3){background:radial-gradient(closest-side,#f0a23b40,#f0a23b00);left:700px;bottom:-260px;animation-duration:36s}
.aurora i:nth-child(4){background:radial-gradient(closest-side,#4a82d055,#4a82d000);left:1200px;top:-300px;width:700px;height:600px;animation-duration:20s}
@keyframes blob{0%{transform:translate(0,0) scale(1)}50%{transform:translate(320px,160px) scale(1.3)}100%{transform:translate(-240px,260px) scale(.85)}}
#spot{position:absolute;width:760px;height:760px;margin:-380px 0 0 -380px;border-radius:50%;background:radial-gradient(circle,#f0a23b1f,transparent 62%);pointer-events:none;left:-999px;top:-999px;z-index:3}
h2{background:linear-gradient(100deg,#eef1ec 0%,#eef1ec 40%,#ffd08a 50%,#eef1ec 60%,#eef1ec 100%);background-size:260% 100%;-webkit-background-clip:text;background-clip:text;color:transparent;animation:shine 7s linear infinite}
.active h2.in{animation:rise .8s cubic-bezier(.2,.8,.2,1) backwards,shine 7s linear infinite}
@keyframes shine{from{background-position:130% 0}to{background-position:-130% 0}}
h1 .word{text-shadow:0 0 40px #4a82d055}
.big{text-shadow:0 0 36px rgba(240,162,59,.22)}
.card,.rule,.phase{will-change:transform;box-shadow:0 18px 50px #00000040}
.card{background:rgba(23,42,55,.82)}
.meter .tr i{position:relative;overflow:hidden}
.meter .tr i:after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,transparent,#ffffff70,transparent);transform:translateX(-100%);animation:sweep 3s ease-in-out infinite;animation-delay:calc(var(--d) + 1.2s)}
@keyframes sweep{55%,100%{transform:translateX(100%)}}
.gauge i,.mixbar i{background-image:repeating-linear-gradient(-45deg,rgba(255,255,255,.16) 0 12px,transparent 12px 24px)!important;background-size:34px 34px!important;animation:stripes .9s linear infinite}
@keyframes stripes{to{background-position:34px 0}}
.scanwrap{position:relative}
.scan{position:absolute;top:40px;bottom:0;width:160px;left:0;background:linear-gradient(90deg,transparent,#f0a23b66,transparent);opacity:0;pointer-events:none;z-index:3}
.active .scan{animation:scan 1.5s .8s ease-in-out both}
@keyframes scan{0%{opacity:0;left:0}10%,85%{opacity:1}100%{opacity:0;left:calc(100% - 160px)}}
.months{position:absolute;left:0;right:0;top:0;height:30px}
.months span{position:absolute;width:60px;margin-left:-30px;text-align:center;font-size:22px;color:#4c6474;font-family:'JetBrains Mono',monospace}
.active .months span{animation:mon 6s linear infinite;animation-delay:var(--d)}
@keyframes mon{0%{color:#ffd08a;transform:scale(1.4);text-shadow:0 0 14px #f0a23b}10%,100%{color:#4c6474;transform:none;text-shadow:none}}
/* scenery */
.scene{position:absolute;left:0;right:0;bottom:0;height:520px;overflow:hidden;pointer-events:none;z-index:0}
.loop{position:absolute;left:0;bottom:0;width:3840px}
.active .loop{animation:loopx var(--t) linear infinite}
@keyframes loopx{to{transform:translateX(-1920px)}}
.sunb{position:absolute;right:220px;top:30px;width:150px;height:150px;border-radius:50%;background:radial-gradient(circle,#ffe2a8,#f0a23b 60%,#f0a23b00 72%);box-shadow:0 0 120px 40px #f0a23b40;animation:sunp 4s ease-in-out infinite}
@keyframes sunp{50%{box-shadow:0 0 170px 70px #f0a23b55;transform:scale(1.05)}}
.cloud{position:absolute;height:40px;border-radius:40px;background:#c9d6df14;filter:blur(2px)}
.active .cloud{animation:cloud var(--t) linear infinite;animation-delay:var(--d)}
@keyframes cloud{from{transform:translateX(2100px)}to{transform:translateX(-600px)}}
.win{animation:twk 3s ease-in-out infinite}
@keyframes twk{0%,100%{opacity:.15}50%{opacity:1}}
.blades{animation:spin 3.2s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.bggrid{position:absolute;inset:0;z-index:0;background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);background-size:80px 80px;opacity:.1;pointer-events:none}
.active .bggrid{animation:pan 30s linear infinite}
@keyframes pan{to{background-position:80px 80px}}
h1{font-family:var(--hd);font-size:104px;line-height:1.02;font-weight:700;letter-spacing:-1px}
h2{font-family:var(--hd);font-size:60px;line-height:1.1;font-weight:700;max-width:1660px;position:relative}
.eyebrow{font-size:24px;letter-spacing:4px;text-transform:uppercase;color:var(--acc);font-weight:600;margin-bottom:16px;position:relative}
.mut{color:var(--mut)}
.card{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:30px;position:relative}
.big{font-family:var(--hd);font-weight:700;line-height:1}
.mono{font-family:'JetBrains Mono',Consolas,monospace}
.footer{position:absolute;left:128px;right:128px;bottom:52px;display:flex;justify-content:space-between;font-size:22px;color:#5f7686}
/* entrance animations, replay every time a slide becomes active */
.active .in{animation:rise .8s cubic-bezier(.2,.8,.2,1) backwards;animation-delay:var(--d,0s)}
.active .pop{animation:pop .6s cubic-bezier(.3,1.6,.5,1) backwards;animation-delay:var(--d,0s)}
.active .fadein{animation:fade 1s both;animation-delay:var(--d,0s)}
.active .left{animation:fromleft .9s cubic-bezier(.2,.8,.2,1) backwards;animation-delay:var(--d,0s)}
@keyframes rise{from{opacity:0;transform:translateY(40px)}to{opacity:1;transform:none}}
@keyframes pop{from{opacity:0;transform:scale(.4)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes fromleft{from{opacity:0;transform:translateX(-80px)}to{opacity:1;transform:none}}
.draw{stroke-dasharray:1;stroke-dashoffset:1}
.active .draw{animation:draw var(--t,1.8s) ease-out both;animation-delay:var(--d,0s)}
@keyframes draw{to{stroke-dashoffset:0}}
/* ---------- cover ---------- */
.road{position:absolute;left:0;right:0;bottom:0;height:300px}
.lane{position:absolute;left:0;right:0;top:150px;height:8px;background:repeating-linear-gradient(90deg,#3b5263 0 70px,transparent 70px 130px)}
.active .lane{animation:lane .6s linear infinite}
@keyframes lane{to{background-position:-130px 0}}
.rtruck{position:absolute;top:30px;left:-420px;width:380px;height:150px}
.active .rtruck{animation:drive 9s linear infinite;animation-delay:var(--d)}
@keyframes drive{to{transform:translateX(2400px)}}
.rtruck .body{animation:recolor 9s linear infinite;animation-delay:var(--d)}
@keyframes recolor{0%,46%{fill:var(--lng)}54%,100%{fill:var(--bev)}}
.rtruck .puff{animation:puff 9s linear infinite;animation-delay:var(--d)}
@keyframes puff{0%{opacity:.7}45%{opacity:.7}52%,100%{opacity:0}}
.rtruck .bolt{animation:bolt 9s linear infinite;animation-delay:var(--d)}
@keyframes bolt{0%,48%{opacity:0}56%,100%{opacity:1}}
.smoke{animation:smoke 1.2s linear infinite}
@keyframes smoke{from{transform:translate(0,0) scale(.5);opacity:.8}to{transform:translate(-80px,-40px) scale(1.6);opacity:0}}
.word{display:inline-block}
/* ---------- squeeze ---------- */
.ax{font-size:24px;fill:var(--mut)}
.chartlab{font-size:30px;font-weight:700;font-family:var(--hd)}
/* ---------- dilemma ---------- */
.tcard{flex:1;display:flex;flex-direction:column;gap:14px;padding:26px 30px}
.meter{display:flex;align-items:center;gap:16px;font-size:24px}
.meter b{width:150px;color:var(--mut);font-weight:500}
.meter .tr{flex:1;height:22px;background:#0e1c26;border-radius:11px;overflow:hidden}
.meter .tr i{display:block;height:100%;border-radius:11px;width:var(--w);transform-origin:left}
.active .meter .tr i{animation:growx 1.2s cubic-bezier(.2,.8,.2,1) both;animation-delay:var(--d,0s)}
@keyframes growx{from{transform:scaleX(0)}to{transform:scaleX(1)}}
.meter span{width:110px;text-align:right;font-family:'JetBrains Mono',monospace}
.dots{display:flex;gap:10px;flex:1}.dots i{width:40px;height:22px;border-radius:6px;background:#0e1c26}
.verdict{position:absolute;top:24px;right:24px;font-size:22px;font-weight:700;padding:8px 16px;border-radius:30px;transform:rotate(4deg)}
.subrow{font-size:22px;color:var(--mut);margin-top:-6px}
/* ---------- year in the life ---------- */
.track{position:relative;height:250px;margin-top:40px}
.trackline{position:absolute;left:0;right:0;top:150px;height:6px;background:var(--line);border-radius:3px}
.trackfill{position:absolute;left:0;top:150px;height:6px;background:linear-gradient(90deg,var(--acc),var(--bev));border-radius:3px;width:0}
.active .trackfill{animation:fill 6s linear infinite}
@keyframes fill{from{width:0}to{width:100%}}
.ytruck{position:absolute;top:66px;left:0;width:150px;height:80px;margin-left:-75px}
.active .ytruck{animation:ymove 6s linear infinite}
@keyframes ymove{from{left:0}to{left:100%}}
.milestone{position:absolute;top:126px;width:54px;height:54px;margin-left:-27px;border-radius:50%;border:5px solid var(--bg);display:flex;align-items:center;justify-content:center;font-weight:700}
.mlab{position:absolute;top:196px;width:460px;margin-left:-230px;text-align:center;font-size:26px}
.rules{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-top:40px}
.rule{display:flex;gap:16px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px 20px}
.active .rule{animation:flip .7s cubic-bezier(.2,.8,.2,1) backwards;animation-delay:var(--d)}
@keyframes flip{from{opacity:0;transform:perspective(800px) rotateX(-90deg)}to{opacity:1;transform:none}}
.rn{width:48px;height:48px;border-radius:50%;background:var(--acc);color:#1a1205;font-weight:700;display:flex;align-items:center;justify-content:center;font-size:24px;flex:none}
.rule p{font-size:24px;line-height:1.25}.rule p b{display:block;font-size:26px;font-family:var(--hd)}
/* ---------- narrowing ---------- */
.g44{display:grid;grid-template-columns:70px repeat(4,190px);grid-auto-rows:132px;gap:14px;align-items:center}
.gl{font-size:28px;font-weight:700;color:var(--mut);text-align:center}
.cell{height:132px;border-radius:16px;background:var(--card);border:1px solid var(--line);display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:30px;font-family:var(--hd);font-weight:700}
.cell small{font-size:20px;color:var(--mut);font-family:Inter;font-weight:500}
.active .cell.off{animation:dim 1s 2.2s both}
@keyframes dim{to{opacity:.18;transform:scale(.88)}}
.active .cell.on{animation:glow 1.2s 2.2s both, pulse 2s 3.4s ease-in-out infinite}
@keyframes glow{to{background:var(--acc);color:#1a1205;transform:scale(1.08);box-shadow:0 0 50px #f0a23b88}}
@keyframes pulse{0%,100%{box-shadow:0 0 30px #f0a23b66;background:var(--acc);color:#1a1205;transform:scale(1.08)}50%{box-shadow:0 0 70px #f0a23bbb;background:var(--acc);color:#1a1205;transform:scale(1.1)}}
.cell.on small{color:inherit;opacity:.7}
.kept li,.drop li{font-size:28px;line-height:1.55;list-style:none;padding-left:44px;position:relative}
.kept li:before{content:"✓";position:absolute;left:0;color:var(--bev);font-weight:700}
.drop li:before{content:"✕";position:absolute;left:0;color:var(--dsl);font-weight:700}
/* ---------- model + code ---------- */
.term{display:flex;align-items:center;gap:18px;font-size:28px;padding:11px 22px;border-radius:14px;background:#0f1f2a;border-left:10px solid var(--c)}
.term .mono{font-size:26px}
.term .op{font-family:var(--hd);font-size:40px;width:30px;color:var(--c)}
.cons{font-size:24px;padding:7px 0;border-bottom:1px dashed var(--line);display:flex;justify-content:space-between;gap:20px}
.cons .mono{font-size:24px;color:var(--ink)}
.term-code{background:#081118;border:1px solid var(--line);border-radius:18px;padding:28px 30px;font-family:'JetBrains Mono',monospace;font-size:22px;line-height:1.6;position:relative;overflow:hidden}
.term-code .bar{position:absolute;top:0;left:0;right:0;height:44px;border-bottom:1px solid var(--line);display:flex;gap:10px;align-items:center;padding-left:18px}
.term-code .bar i{width:14px;height:14px;border-radius:50%}
.tl{display:block;white-space:pre;overflow:hidden;max-width:0}
.active .tl{animation:type var(--t) steps(var(--n)) both;animation-delay:var(--d)}
@keyframes type{to{max-width:calc(var(--n)*1ch + 2px)}}
.k{color:#f0a23b}.c{color:#6f8899}.n{color:#73d9c2}.s{color:#c7a6ff}
.solved{display:flex;align-items:center;gap:18px;margin-top:20px;font-size:30px;font-weight:700;color:var(--bev)}
/* ---------- simulation ---------- */
.ctrl{display:flex;align-items:center;gap:22px;margin-top:22px}
.btn{width:76px;height:76px;border-radius:50%;background:var(--acc);border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;flex:none}
.btn:hover{filter:brightness(1.1)}
input[type=range]{flex:1;accent-color:var(--acc);height:10px;cursor:pointer}
.yr{font-family:var(--hd);font-size:120px;font-weight:700;line-height:.9;width:330px}
.lot{display:grid;grid-template-columns:repeat(10,1fr);gap:10px 8px}
.slot{height:56px;transition:color .6s,opacity .6s,transform .4s}
.slot svg{width:100%;height:100%}
.slot.e{color:#20394a;opacity:.6}.slot.lng{color:var(--lng)}.slot.bio{color:var(--bio)}.slot.bev{color:var(--bev)}
.slot.chg{animation:bump .6s}
@keyframes bump{40%{transform:scale(1.35)}}
.gauge{height:46px;background:#0e1c26;border-radius:12px;position:relative;overflow:visible}
.gauge i{position:absolute;left:0;top:0;bottom:0;border-radius:12px;transition:width .7s cubic-bezier(.2,.8,.2,1),background .5s}
.capm{position:absolute;top:-14px;bottom:-14px;width:5px;background:var(--cap);border-radius:3px;transition:left .7s}
.capm:after{content:"cap";position:absolute;top:10px;left:12px;font-size:20px;color:var(--cap);font-weight:700}
.mixbar{height:46px;display:flex;border-radius:12px;overflow:hidden;background:#0e1c26}
.mixbar i{height:100%;transition:width .7s cubic-bezier(.2,.8,.2,1)}
.caption{font-family:var(--hd);font-size:36px;font-weight:700;min-height:92px;line-height:1.25}
.caption.flash{animation:capin .7s}
@keyframes capin{from{opacity:0;transform:translateY(16px)}}
.kv{display:flex;justify-content:space-between;align-items:baseline;font-size:26px}
.kv b{font-family:var(--hd);font-size:46px}
.legend{display:flex;gap:26px;font-size:22px;color:var(--mut)}
.legend span{display:flex;align-items:center;gap:8px}.legend i{width:20px;height:20px;border-radius:5px;display:inline-block}
/* ---------- results ---------- */
.wf rect.bar{transform-box:fill-box;transform-origin:bottom}
.wf rect.neg{transform-origin:top}
.active .wf rect.bar{animation:gy .8s cubic-bezier(.2,.8,.2,1) both;animation-delay:var(--d)}
@keyframes gy{from{transform:scaleY(0)}to{transform:scaleY(1)}}
.phase{flex:1;padding:22px 24px;border-radius:16px;background:var(--card);border-top:8px solid var(--c)}
.phase p{font-size:22px;color:var(--mut)}.phase b{display:block;font-family:var(--hd);font-size:28px;margin:4px 0}
.next{display:grid;grid-template-columns:1fr 1fr;gap:22px}
.next .card p{font-size:26px;color:#c9d4dc;line-height:1.4}.next .card b{font-family:var(--hd);font-size:30px;color:var(--acc);display:block;margin-bottom:8px}
#nav{position:fixed;right:20px;bottom:16px;display:flex;gap:8px;z-index:5}
#nav button{background:#1b2f3d;color:#cfd9e0;border:1px solid #2c4557;border-radius:10px;width:44px;height:38px;font-size:18px;cursor:pointer}
#bar{position:fixed;left:0;bottom:0;height:5px;background:var(--acc);transition:width .5s;z-index:5}
@media (prefers-reduced-motion:reduce){*{animation-duration:.01s!important;animation-iteration-count:1!important}}
</style></head><body>
<svg width="0" height="0" style="position:absolute"><defs>
<symbol id="truck" viewBox="0 0 120 64"><rect x="2" y="6" width="78" height="40" rx="5" fill="currentColor"/><path d="M84 18h18l14 14v14H84z" fill="currentColor" opacity=".8"/>
<rect x="92" y="22" width="12" height="9" rx="2" fill="#0e1a23" opacity=".55"/><circle cx="22" cy="50" r="9" fill="#0b141b" stroke="currentColor" stroke-width="3"/>
<circle cx="62" cy="50" r="9" fill="#0b141b" stroke="currentColor" stroke-width="3"/><circle cx="100" cy="50" r="9" fill="#0b141b" stroke="currentColor" stroke-width="3"/></symbol>
</defs></svg>
<div id="stage">
<div class="aurora"><i></i><i></i><i></i><i></i></div><canvas id="fx"></canvas><div id="spot"></div>

<!-- 1 COVER -->
<section data-fx="stars" class="slide" data-notes="Introduce the problem from the Shell.ai Hackathon 2024: plan a truck fleet's move to zero emissions at the lowest possible cost. The trucks on screen change from LNG to electric, which is exactly what our optimizer ends up recommending.">
 <div class="bggrid"></div>
 <p class="eyebrow in" style="--d:.1s">Shell.ai Hackathon 2024 · Fleet transition challenge</p>
 <h1 id="title" style="max-width:1400px"></h1>
 <p class="in" style="--d:1.1s;font-size:34px;color:#c3cfd8;max-width:1250px;margin-top:34px;line-height:1.45">An optimization model that decides which trucks to buy, how to run them, and when to sell them, while staying under a carbon cap that shrinks every year.</p>
 <p class="in mono" style="--d:1.4s;font-size:26px;color:var(--acc);margin-top:34px">Mixed-integer linear programming · Python · PuLP + HiGHS</p>
 <div class="scene" id="scene1"></div><div class="road" style="z-index:1"><div class="lane"></div><div id="roadTrucks"></div></div>
</section>

<!-- 2 SQUEEZE -->
<section data-fx="co2" class="slide" data-notes="Freight demand grows about 47 percent while the carbon budget falls about 79 percent. In 2023 the cap equals what an all-diesel fleet would emit, so the fleet has to change what it runs on.">
 <div class="bggrid"></div>
 <p class="eyebrow in">The big problem</p>
 <h2 class="in" style="--d:.1s">A fleet must move more freight every year on a shrinking carbon budget</h2>
 <div style="display:flex;gap:50px;margin-top:40px">
  <div style="width:1150px;position:relative"><svg id="sq" width="1150" height="640" viewBox="0 0 1150 640"></svg></div>
  <div style="flex:1;display:flex;flex-direction:column;gap:22px">
   <div class="card pop" style="--d:.6s"><p class="big" style="font-size:96px;color:var(--lng)"><span class="cnt" data-to="47" data-pre="+" data-suf="%"></span></p><p style="font-size:26px;margin-top:8px">freight demand<br><span class="mut" id="demtxt"></span></p></div>
   <div class="card pop" style="--d:1.2s"><p class="big" style="font-size:96px;color:var(--cap)"><span class="cnt" data-to="79" data-pre="−" data-suf="%"></span></p><p style="font-size:26px;margin-top:8px">carbon budget<br><span class="mut" id="captxt"></span></p></div>
   <div class="card pop" style="--d:1.8s;display:flex;gap:24px"><div><p class="big" style="font-size:64px"><span class="cnt" data-to="16"></span></p><p class="mut" style="font-size:22px">years</p></div><div><p class="big" style="font-size:64px"><span class="cnt" data-to="__NMODELS__"></span></p><p class="mut" style="font-size:22px">truck models</p></div><div><p class="big" style="font-size:64px"><span class="cnt" data-to="5"></span></p><p class="mut" style="font-size:22px">fuels</p></div></div>
  </div>
 </div>
</section>

<!-- 3 DILEMMA -->
<section data-fx="network" class="slide" data-notes="This is the core trade-off. Diesel is cheapest to buy but the dirtiest. LNG has the cheapest fuel per km. BEV is clean but costs 2.2 times as much and, in 2023, only covers short D1 routes. HVO and BioLNG are cleaner fuels for the same trucks, at a higher price per km.">
 <div class="bggrid"></div>
 <p class="eyebrow in">The dilemma</p>
 <h2 class="in" style="--d:.1s">Cheap to buy, cheap to run, or clean: no truck wins on everything</h2>
 <div id="tcards" style="display:flex;gap:28px;margin-top:44px"></div>
 <p class="in mut" style="--d:2.2s;font-size:24px;margin-top:22px">Size S1 trucks, 2023. <span style="color:var(--acc)">BEVs get cheaper and gain range every year:</span> <span id="bevtrend"></span></p>
</section>

<!-- 4 YEAR IN THE LIFE + RULES -->
<section data-fx="network" class="slide" data-notes="Every year has the same rhythm. On 1 January we buy, during the year we pick a fuel and a route bucket for each truck and drive up to its range, and on 31 December we sell. Eight rules from the problem statement limit every one of these choices.">
 <div class="bggrid"></div>
 <p class="eyebrow in">Decisions and rules</p>
 <h2 class="in" style="--d:.1s">Every year: buy, drive, sell, within eight rules</h2>
 <div class="track in" style="--d:.3s">
  <div class="months" id="months"></div><div class="trackline"></div><div class="trackfill"></div>
  <svg class="ytruck" viewBox="0 0 120 64" style="color:var(--bev)"><use href="#truck"/></svg>
  <div class="milestone" style="left:0;background:var(--acc);color:#1a1205">1</div>
  <div class="milestone" style="left:50%;background:var(--lng)">2</div>
  <div class="milestone" style="left:100%;background:var(--bev)">3</div>
  <p class="mlab" style="left:190px"><b style="color:var(--acc);font-family:var(--hd);font-size:34px">1 Jan · BUY</b><br><span class="mut">which models, how many</span></p>
  <p class="mlab" style="left:50%"><b style="color:var(--lng);font-family:var(--hd);font-size:34px">USE</b><br><span class="mut">fuel × route bucket × <span class="mono" id="odo">0</span> km</span></p>
  <p class="mlab" style="left:calc(100% - 190px)"><b style="color:var(--bev);font-family:var(--hd);font-size:34px">31 Dec · SELL</b><br><span class="mut">which trucks, how many</span></p>
 </div>
 <div class="rules" id="rules" style="margin-top:110px"></div>
</section>

<!-- 5 NARROWING -->
<section data-fx="network" class="slide" data-notes="To keep the problem small enough to explain and solve quickly, we keep only size S1 and the two shortest distance buckets: 2 of the 16 demand cells. Everything else stays: all 16 years, all fuels, all eight rules and the full cost formula. The carbon cap is scaled to our share of demand, about 20 percent.">
 <div class="bggrid"></div>
 <p class="eyebrow in">Narrowing down</p>
 <h2 class="in" style="--d:.1s">We solve 2 of the 16 demand cells and keep every rule</h2>
 <div style="display:flex;gap:80px;margin-top:40px;align-items:flex-start">
  <div class="in scanwrap" style="--d:.3s"><div class="scan"></div><p class="mut" style="font-size:24px;margin-bottom:14px">2023 demand, km per year (size × max daily distance)</p><div class="g44" id="g44"></div></div>
  <div style="flex:1;display:flex;flex-direction:column;gap:26px">
   <div class="card left kept" style="--d:3.0s"><p style="font-family:var(--hd);font-size:32px;color:var(--bev);margin-bottom:10px">Kept</p><ul id="keptl"></ul></div>
   <div class="card left drop" style="--d:3.4s"><p style="font-family:var(--hd);font-size:32px;color:var(--dsl);margin-bottom:10px">Left for later</p><ul><li>Sizes S2–S4</li><li>Distance buckets D3–D4</li><li>Fuel price uncertainty (median prices used)</li></ul></div>
  </div>
 </div>
</section>

<!-- 6 MODEL + CODE -->
<section data-fx="code" class="slide" data-notes="The model is a mixed-integer linear program. The objective adds up the exact cost formula from the problem statement, and each rule becomes one line of PuLP. The 3-year version solves in under a second; the full 16 years takes about five minutes.">
 <div class="bggrid"></div>
 <p class="eyebrow in">Model and code</p>
 <h2 class="in" style="--d:.1s">One objective, a handful of constraints, about 150 lines of Python</h2>
 <div style="display:flex;gap:40px;margin-top:36px">
  <div style="width:760px;flex:none;display:flex;flex-direction:column;gap:10px">
   <p class="in mut" style="--d:.3s;font-size:24px">MINIMISE total cost =</p>
   <div class="term left" style="--c:var(--acc);--d:.5s"><span class="op">Σ</span><span class="mono">price · buy</span><span class="mut" style="margin-left:auto;font-size:22px">buying</span></div>
   <div class="term left" style="--c:var(--lng);--d:.8s"><span class="op">+</span><span class="mono">price · (ins%+mnt%)<sub>age</sub> · fleet</span><span class="mut" style="margin-left:auto;font-size:22px">upkeep</span></div>
   <div class="term left" style="--c:var(--dsl);--d:1.1s"><span class="op">+</span><span class="mono">km · consumption · fuel price</span><span class="mut" style="margin-left:auto;font-size:22px">fuel</span></div>
   <div class="term left" style="--c:var(--bev);--d:1.4s"><span class="op">−</span><span class="mono">price · resale%<sub>age</sub> · sell</span><span class="mut" style="margin-left:auto;font-size:22px">resale</span></div>
   <p class="in mut" style="--d:1.7s;font-size:24px;margin-top:14px">SUBJECT TO</p>
   <div class="in" style="--d:1.9s">
    <div class="cons"><span class="mono">fleet<sub>t</sub> = fleet<sub>t−1</sub> − sell<sub>t−1</sub></span><span class="mut">fleet balance</span></div>
    <div class="cons"><span class="mono">Σ km<sub>b,t</sub> ≥ demand<sub>b,t</sub></span><span class="mut">meet demand</span></div>
    <div class="cons"><span class="mono">km ≤ range · use, Σ use ≤ fleet</span><span class="mut">capacity</span></div>
    <div class="cons"><span class="mono">Σ km · cons · CO₂ ≤ cap<sub>t</sub></span><span class="mut">carbon</span></div>
    <div class="cons"><span class="mono">Σ sell<sub>t</sub> ≤ 0.2 · Σ fleet<sub>t</sub></span><span class="mut">20% sell limit</span></div>
   </div>
  </div>
  <div style="flex:1;min-width:0">
   <div class="term-code in" style="--d:.4s"><div class="bar"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i><i style="background:#28c840"></i><span class="mut" style="font-size:20px;margin-left:12px">fleet_model.py · simplified excerpt</span></div>
    <div id="code" style="margin-top:40px"></div>
   </div>
   <div class="solved fadein" id="solved"></div>
  </div>
 </div>
</section>

<!-- 7 SIMULATION -->
<section data-fx="road" class="slide" data-notes="This is the optimal plan replayed year by year. Watch the parking lot: it starts all LNG. Around 2027 the carbon gauge hits the cap and some trucks switch to BioLNG fuel. From 2030 battery-electric trucks take over, and by 2034 the fleet is fully electric with zero emissions. The cost counter adds up to 29.84 million dollars.">
 <div class="bggrid"></div>
 <p class="eyebrow in">The optimal plan, year by year</p>
 <div style="display:flex;gap:60px;margin-top:6px">
  <div style="width:900px">
   <div style="display:flex;align-items:flex-end;gap:30px"><p class="yr" id="yr">2023</p><p class="caption" id="cap" style="flex:1"></p></div>
   <div class="legend" style="margin:22px 0 18px"><span><i style="background:var(--lng)"></i>LNG truck</span><span><i style="background:var(--bio)"></i>LNG truck on BioLNG</span><span><i style="background:var(--bev)"></i>Battery electric</span><span><i style="background:#20394a"></i>empty slot</span></div>
   <div class="lot" id="lot"></div>
   <div class="ctrl"><button class="btn" id="play" aria-label="Play or pause"><svg width="34" height="34" viewBox="0 0 24 24" id="playic"><path d="M7 4l13 8-13 8z" fill="#1a1205"/></svg></button>
    <input type="range" id="scrub" min="0" max="15" value="0" aria-label="Year"></div>
  </div>
  <div style="flex:1;display:flex;flex-direction:column;gap:24px">
   <div class="card"><div class="kv"><span>CO₂ this year</span><b id="emv">0</b></div><div class="gauge" style="margin-top:34px"><i id="emg"></i><div class="capm" id="capm"></div></div><p class="mut" style="font-size:22px;margin-top:18px" id="emnote"></p></div>
   <div class="card"><div class="kv"><span>Distance driven, by fuel</span><b id="kmv">0</b></div><div class="mixbar" id="mix" style="margin-top:20px"><i style="background:var(--lng)"></i><i style="background:var(--bio)"></i><i style="background:var(--bev)"></i></div></div>
   <div class="card" style="display:flex;gap:30px">
    <div style="flex:1"><p class="mut" style="font-size:22px">Bought / sold</p><p class="big" style="font-size:52px;margin-top:6px"><span id="bv" style="color:var(--acc)">0</span><span class="mut"> / </span><span id="sv" style="color:var(--bev)">0</span></p></div>
    <div style="flex:1.4"><p class="mut" style="font-size:22px">Cumulative cost</p><p class="big" style="font-size:52px;margin-top:6px" id="cc">$0</p></div>
   </div>
   <svg id="mini" width="790" height="150" viewBox="0 0 790 150"></svg>
  </div>
 </div>
</section>

<!-- 8 RESULTS -->
<section data-fx="confetti" class="slide" data-notes="Buying trucks is the biggest cost, and resale brings back almost half of it. An independent checker found zero rule violations. The solver stopped at its time limit but proved that no plan can cost less than the lower bound shown, so ours is within about 2 percent of the best possible.">
 <div class="bggrid"></div>
 <p class="eyebrow in">Results</p>
 <h2 class="in" style="--d:.1s" id="costh"></h2>
 <div style="display:flex;gap:44px;margin-top:30px">
  <svg id="wf" class="wf" width="1060" height="520" viewBox="0 0 1060 520"></svg>
  <div style="flex:1;display:flex;flex-direction:column;gap:22px">
   <div class="card pop" style="--d:2.4s"><p class="big" style="font-size:88px;color:var(--bev)"><span class="cnt" data-to="0"></span></p><p style="font-size:26px">rule violations, found by an independent checker</p></div>
   <div class="card pop" style="--d:2.8s"><p class="big" style="font-size:88px;color:var(--lng)">≤ <span class="cnt" id="gapc" data-dec="1" data-suf="%"></span></p><p style="font-size:26px" id="lbtxt"></p></div>
  </div>
 </div>
 <div style="display:flex;gap:18px;margin-top:24px" id="phases"></div>
</section>

<!-- 9 NEXT -->
<section data-fx="stars" class="slide" data-notes="Close with how this scales up and what we would add next. The main takeaway: a compact MILP turns a net-zero target into a concrete, lowest-cost plan for every year.">
 <div class="bggrid"></div>
 <p class="eyebrow in">Next steps</p>
 <h2 class="in" style="--d:.1s">From the mini model to the full challenge</h2>
 <div class="next" style="margin-top:44px">
  <div class="card in" style="--d:.3s"><b>Scale up</b><p>Add S2–S4 and D3–D4 by changing two lists. The model grows about 8×, so use a longer time limit or rolling-horizon solving.</p></div>
  <div class="card in" style="--d:.5s"><b>Fuel price risk</b><p>Price uncertainty reaches ±30%. Solve over price scenarios, or with a robust model, so the plan survives price shocks.</p></div>
  <div class="card in" style="--d:.7s"><b>End of horizon</b><p>The model doesn't value trucks still owned in 2038. A salvage value stops it from buying just before the end.</p></div>
  <div class="card in" style="--d:.9s"><b>Faster solving</b><p>Aggregate trucks by drivetrain and add symmetry-breaking cuts, so the full-size problem solves in minutes.</p></div>
 </div>
 <p class="in" style="--d:1.3s;font-family:var(--hd);font-size:42px;margin-top:50px;max-width:1500px;line-height:1.3">A compact MILP turns a net-zero target into a <span style="color:var(--bev)">concrete, lowest-cost plan</span> for every year.</p>
 <div class="scene" id="scene2" style="height:300px;opacity:.75"></div><div class="road" style="height:170px;transform:scale(.7);transform-origin:bottom left;width:143%;z-index:1"><div class="lane" style="top:120px"></div><div id="roadTrucks2"></div></div>
</section>
</div>
<div id="bar"></div>
<div id="nav"><button id="prev" aria-label="Previous slide">◀</button><button id="next" aria-label="Next slide">▶</button></div>

<script>
const D = __DATA__;
const NS = "http://www.w3.org/2000/svg";
const $ = id => document.getElementById(id);
const fmtM = x => (x/1e6).toFixed(2) + "M";
const el = (tag, attrs, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

/* ---------- cover ---------- */
$("title").innerHTML = "Decarbonising a truck fleet at the lowest cost".split(" ").map((w, i) =>
  `<span class="word in" style="--d:${0.25 + i*0.09}s">${w}</span>`).join(" ");
function roadTrucks(host, n, top) {
  let h = "";
  for (let i = 0; i < n; i++) {
    const d = -(i * 9 / n);
    h += `<svg class="rtruck" style="--d:${d}s;top:${top}px" viewBox="0 0 380 150">
      <g class="puff">${[0,1,2].map(k => `<circle class="smoke" cx="10" cy="${70-k*6}" r="12" fill="#8aa0ae" style="animation-delay:${k*0.4}s"/>`).join("")}</g>
      <rect class="body" x="20" y="20" width="240" height="96" rx="12"/>
      <path class="body" d="M270 50h56l44 42v24H270z" opacity=".85"/>
      <rect x="296" y="62" width="34" height="24" rx="4" fill="#0e1a23" opacity=".5"/>
      <path class="bolt" d="M150 34 L116 74 h26 l-12 32 l40-46 h-28 z" fill="#f2f7ef"/>
      ${[70,190,330].map(x => `<circle cx="${x}" cy="124" r="22" fill="#0b141b" stroke="#5c7383" stroke-width="6"/>`).join("")}
    </svg>`;
  }
  host.innerHTML = h;
}
roadTrucks($("roadTrucks"), 3, 30); roadTrucks($("roadTrucks2"), 3, 0);

/* ---------- squeeze chart ---------- */
(function () {
  const s = $("sq"), W = 1150, H = 640, L = 80, R = 40, T = 40, B = 70, pw = W-L-R, ph = H-T-B, ymax = 160;
  const X = i => L + pw*i/15, Y = v => T + ph*(1 - v/ymax);
  for (let k = 0; k <= 4; k++) { const v = 40*k; el("line", {x1:L, x2:W-R, y1:Y(v), y2:Y(v), stroke:css("--line"), "stroke-width":1.5}, s);
    const t = el("text", {x:L-14, y:Y(v)+8, "text-anchor":"end", class:"ax"}, s); t.textContent = v; }
  for (let i = 0; i < 16; i += 3) { const t = el("text", {x:X(i), y:H-B+40, "text-anchor":"middle", class:"ax"}, s); t.textContent = 2023+i; }
  const t0 = el("text", {x:L, y:T-12, class:"ax"}, s); t0.textContent = "Index, 2023 = 100";
  const pd = D.demIdx.map((v,i)=>`${X(i)},${Y(v)}`).join(" "), pc = D.capIdx.map((v,i)=>`${X(i)},${Y(v)}`).join(" ");
  el("polygon", {points: pd + " " + D.capIdx.map((v,i)=>`${X(i)},${Y(v)}`).reverse().join(" "), fill:css("--acc"), "fill-opacity":.16, class:"fadein", style:"--d:2s"}, s);
  el("polyline", {points:pd, fill:"none", stroke:css("--lng"), "stroke-width":7, "stroke-linecap":"round", "stroke-linejoin":"round", pathLength:1, class:"draw", style:"--d:.4s"}, s);
  el("polyline", {points:pc, fill:"none", stroke:css("--cap"), "stroke-width":7, "stroke-linecap":"round", "stroke-linejoin":"round", pathLength:1, class:"draw", style:"--d:.4s"}, s);
  const a = el("text", {x:X(15)-10, y:Y(D.demIdx[15])-24, "text-anchor":"end", class:"chartlab fadein", fill:css("--lng"), style:"--d:2s"}, s); a.textContent = "Demand " + D.demIdx[15].toFixed(0);
  const b = el("text", {x:X(15)-10, y:Y(D.capIdx[15])-24, "text-anchor":"end", class:"chartlab fadein", fill:css("--cap"), style:"--d:2s"}, s); b.textContent = "Carbon cap " + D.capIdx[15].toFixed(0);
  const g = el("text", {x:X(10), y:(Y(D.demIdx[10])+Y(D.capIdx[10]))/2+10, "text-anchor":"middle", class:"chartlab fadein", fill:css("--acc"), style:"--d:2.6s"}, s); g.textContent = "the gap to close";
  $("demtxt").textContent = `${(D.dem0/1e6).toFixed(1)}M → ${(D.dem1/1e6).toFixed(1)}M km / year`;
  $("captxt").textContent = `${(D.cap0/1e6).toFixed(1)}M → ${(D.cap1/1e6).toFixed(1)}M kg CO₂`;
})();

/* ---------- dilemma cards ---------- */
(function () {
  const col = {Diesel: css("--dsl"), LNG: css("--lng"), BEV: css("--bev")};
  const mp = Math.max(...D.trucks.map(t=>t.price)), mk = Math.max(...D.trucks.map(t=>t.perkm)), mc = Math.max(...D.trucks.map(t=>t.co2));
  const verdict = {Diesel:["cheapest to buy", "#5a2418"], LNG:["cheapest to run", "#16304f"], BEV:["zero emission", "#0d3d34"]};
  let h = "", k = 0;
  for (const type of ["Diesel", "LNG", "BEV"]) {
    const rows = D.trucks.filter(t => t.t === type), c = col[type];
    h += `<div class="card tcard in" style="--d:${0.3 + k*0.25}s">
      <p class="verdict pop" style="--d:${1.6 + k*0.2}s;background:${c};color:${verdict[type][1]}">${verdict[type][0]}</p>
      <svg viewBox="0 0 120 64" style="width:170px;height:90px;color:${c}"><use href="#truck"/></svg>
      <p style="font-family:var(--hd);font-size:44px;font-weight:700">${type}</p>
      <div class="meter"><b>Price</b><div class="tr"><i style="--w:${rows[0].price/mp*100}%;background:${css("--acc")};--d:${0.8+k*0.2}s"></i></div><span>$${(rows[0].price/1000).toFixed(0)}k</span></div>`;
    rows.forEach((r, j) => {
      h += `<p class="subrow">fuel: ${r.fuel}</p>
      <div class="meter"><b>$ per km</b><div class="tr"><i style="--w:${r.perkm/mk*100}%;background:${css("--acc")};--d:${1+k*0.2+j*0.1}s"></i></div><span>$${r.perkm.toFixed(2)}</span></div>
      <div class="meter"><b>kg CO₂/km</b><div class="tr"><i style="--w:${Math.max(r.co2/mc*100,0.01)}%;background:${css("--cap")};--d:${1.1+k*0.2+j*0.1}s"></i></div><span>${r.co2.toFixed(2)}</span></div>`;
    });
    h += `<div class="meter"><b>Max route</b><div class="dots">${[1,2,3,4].map(d=>`<i style="background:${d<=rows[0].route?c:''}"></i>`).join("")}</div><span>D${rows[0].route}</span></div></div>`;
    k++;
  }
  $("tcards").innerHTML = h;
  $("bevtrend").textContent = `$${(D.bevPrice[2023]/1000).toFixed(0)}k, D1 only in 2023 → $${(D.bevPrice[2032]/1000).toFixed(0)}k, up to D4 by 2032`;
})();

/* ---------- rules ---------- */
$("rules").innerHTML = [["Size match","S1 trucks serve S1 demand"],["Distance","A Dx truck serves D1…Dx"],["Carbon cap","Yearly CO₂ ≤ limit"],["Demand","Every cell fully met"],
  ["Buy year","Model 20xx only in 20xx"],["10-year life","Sold by end of year 10"],["Timing","Buy 1 Jan, sell 31 Dec"],["Sell limit","≤ 20% of fleet per year"]]
  .map(([a,b],i)=>`<div class="rule" style="--d:${0.6+i*0.12}s"><span class="rn">${i+1}</span><p><b>${a}</b><span class="mut">${b}</span></p></div>`).join("");

/* ---------- narrowing grid ---------- */
(function () {
  let h = "<span></span>" + ["D1","D2","D3","D4"].map(d=>`<p class="gl">${d}</p>`).join("");
  for (const s of ["S1","S2","S3","S4"]) {
    h += `<p class="gl">${s}</p>`;
    for (const d of ["D1","D2","D3","D4"]) {
      const on = s === "S1" && (d === "D1" || d === "D2");
      h += `<div class="cell pop ${on ? "on" : "off"}" style="--d:${0.4 + Math.random()*0.8}s">${(D.grid[s][d]/1e6).toFixed(2)}M<small>km</small></div>`;
    }
  }
  $("g44").innerHTML = h;
  const share = (D.grid.S1.D1 + D.grid.S1.D2) / D.dem0 * 100;
  $("keptl").innerHTML = ["All 16 years, 2023–2038", "All 3 drivetrains and 5 fuels", "All 8 rules and the full cost formula", `Carbon cap scaled to our share of demand (~${share.toFixed(0)}%)`].map(x=>`<li>${x}</li>`).join("");
})();

/* ---------- code typewriter ---------- */
(function () {
  const lines = [
    ['<span class="k">for</span> t <span class="k">in</span> YEARS:', 'for t in YEARS:'],
    ['    <span class="c"># rule 4: meet demand in every bucket</span>', '    # rule 4: meet demand in every bucket'],
    ['    <span class="k">for</span> b <span class="k">in</span> BUCKETS:', '    for b in BUCKETS:'],
    ['        m += lpSum(km[a] <span class="k">for</span> a <span class="k">in</span> A[b, t]) >= D[t, b]', '        m += lpSum(km[a] for a in A[b, t]) >= D[t, b]'],
    ['    <span class="c"># rule 3: carbon cap</span>', '    # rule 3: carbon cap'],
    ['    m += lpSum(km[a] * co2[a] <span class="k">for</span> a <span class="k">in</span> A[t]) <= CAP[t]', '    m += lpSum(km[a] * co2[a] for a in A[t]) <= CAP[t]'],
    ['    <span class="c"># rule 8: sell at most 20% of the fleet</span>', '    # rule 8: sell at most 20% of the fleet'],
    ['    m += (lpSum(sell[v, t] <span class="k">for</span> v <span class="k">in</span> V)', '    m += (lpSum(sell[v, t] for v in V)'],
    ['          <= <span class="n">0.2</span> * lpSum(fleet[v, t] <span class="k">for</span> v <span class="k">in</span> V))', '          <= 0.2 * lpSum(fleet[v, t] for v in V))'],
    ['', ''],
    ['m.solve(HiGHS(timeLimit=<span class="n">300</span>, gapRel=<span class="n">0.005</span>))', 'm.solve(HiGHS(timeLimit=300, gapRel=0.005))'],
  ];
  let d = 0.8, h = "";
  for (const [html, plain] of lines) {
    const n = Math.max(plain.length, 1), t = Math.max(n * 0.011, 0.12);
    h += `<span class="tl" style="--n:${n};--t:${t}s;--d:${d}s">${html || " "}</span>`;
    d += t + 0.08;
  }
  $("code").innerHTML = h;
  const sv = $("solved"); sv.style.setProperty("--d", (d + 0.2) + "s");
  sv.innerHTML = `<svg width="44" height="44" viewBox="0 0 24 24"><circle cx="12" cy="12" r="11" fill="${css("--bev")}"/><path d="M6.5 12.5l3.5 3.5 7.5-8" stroke="#0e1a23" stroke-width="2.6" fill="none"/></svg> Solved · total cost $${fmtM(D.total)}`;
})();

/* ---------- simulation ---------- */
const SIM = (function () {
  const lot = $("lot"), N = 60;
  lot.innerHTML = Array.from({length:N}, () => `<div class="slot e"><svg viewBox="0 0 120 64"><use href="#truck"/></svg></div>`).join("");
  const slots = [...lot.children];
  const capMax = Math.max(...D.cap) * 1.05;
  const cum = []; let acc = 0;
  D.years.forEach((y,i) => { acc += ["buy","insurance","maintenance","fuel","resale"].reduce((s,k)=>s+D.cost[k][i],0); cum.push(acc); });
  const firstBev = D.bev.findIndex(b => b > 0), allBev = D.lng.findIndex((l,i) => i > 0 && l === 0 && D.bev[i] > 0);
  const firstBind = D.em.findIndex((e,i) => e >= D.cap[i]*0.99);
  const bioShare = D.years.map((_,i) => { const a = D.km.LNG[i] + D.km.BioLNG[i]; return a ? D.km.BioLNG[i]/a : 0; });
  function caption(i) {
    if (i >= D.years.length - 1) return `Zero emissions. Total cost $${fmtM(D.total)}`;
    if (i >= allBev) return "100% battery electric: emissions are zero";
    if (i >= firstBev) return "Battery electric trucks take over as they get cheaper and gain range";
    if (i >= firstBind) return "The carbon cap bites: trucks blend in cleaner BioLNG";
    return "All LNG: the cheapest fuel per km while the cap is loose";
  }
  // mini timeline chart
  const m = $("mini"), W = 790, H = 150, L = 10, R = 10, T = 14, B = 26, pw = W-L-R, ph = H-T-B;
  const X = i => L + pw*i/15, Y = v => T + ph*(1 - v/capMax);
  el("polyline", {points: D.cap.map((v,i)=>`${X(i)},${Y(v)}`).join(" "), fill:"none", stroke:css("--cap"), "stroke-width":3, "stroke-dasharray":"8 6"}, m);
  el("polyline", {points: D.em.map((v,i)=>`${X(i)},${Y(v)}`).join(" "), fill:"none", stroke:css("--lng"), "stroke-width":4}, m);
  [0,5,10,15].forEach(i => { const t = el("text", {x:X(i), y:H-2, "text-anchor": i===0?"start":i===15?"end":"middle", class:"ax", style:"font-size:20px"}, m); t.textContent = D.years[i]; });
  const cur = el("line", {x1:X(0), x2:X(0), y1:T, y2:H-B, stroke:css("--acc"), "stroke-width":3}, m);
  const dot = el("circle", {cx:X(0), cy:Y(D.em[0]), r:8, fill:css("--acc")}, m);
  const lt = el("text", {x:W-R, y:T+6, "text-anchor":"end", class:"ax", style:"font-size:20px"}, m); lt.textContent = "CO₂ (solid) vs cap (dashed)";
  let i = 0, timer = null, lastCap = "";
  function show(k) {
    i = k; $("scrub").value = k; $("yr").textContent = D.years[k];
    const bev = D.bev[k], lng = D.lng[k], bio = Math.round(lng * bioShare[k]);
    slots.forEach((s, j) => {
      const cls = j < bev ? "bev" : j < bev + bio ? "bio" : j < bev + lng ? "lng" : "e";
      if (!s.classList.contains(cls)) { s.className = "slot " + cls; void s.offsetWidth; s.classList.add("chg"); }
    });
    const em = D.em[k], cap = D.cap[k], atCap = em >= cap*0.99;
    $("emv").textContent = (em/1e6).toFixed(2) + "M kg";
    $("emg").style.width = (em/capMax*100) + "%";
    $("emg").style.background = atCap ? css("--cap") : em < 1 ? css("--bev") : css("--lng");
    $("capm").style.left = (cap/capMax*100) + "%";
    $("emnote").textContent = em < 1 ? "No CO₂ at all: every km is electric" : atCap ? `At the cap (${(cap/1e6).toFixed(2)}M): carbon is now a binding constraint` : `${((1-em/cap)*100).toFixed(0)}% below the cap of ${(cap/1e6).toFixed(2)}M`;
    const kms = [D.km.LNG[k], D.km.BioLNG[k], D.km.Electricity[k]], tk = kms.reduce((a,b)=>a+b,0);
    $("kmv").textContent = (tk/1e6).toFixed(2) + "M km";
    [...$("mix").children].forEach((e,j) => e.style.width = (kms[j]/tk*100) + "%");
    $("bv").textContent = D.buys[k]; $("sv").textContent = D.sells[k];
    $("cc").textContent = "$" + fmtM(cum[k]);
    cur.setAttribute("x1", X(k)); cur.setAttribute("x2", X(k)); dot.setAttribute("cx", X(k)); dot.setAttribute("cy", Y(D.em[k]));
    const c = caption(k); if (c !== lastCap) { const ce = $("cap"); ce.textContent = c; ce.classList.remove("flash"); void ce.offsetWidth; ce.classList.add("flash"); lastCap = c; }
  }
  function playIcon(p) { $("playic").innerHTML = p ? '<rect x="6" y="4" width="4" height="16" fill="#1a1205"/><rect x="14" y="4" width="4" height="16" fill="#1a1205"/>' : '<path d="M7 4l13 8-13 8z" fill="#1a1205"/>'; }
  function stop() { clearInterval(timer); timer = null; playIcon(false); }
  function play() { if (i >= 15) show(0); stop(); playIcon(true); timer = setInterval(() => { if (i >= 15) return stop(); show(i+1); }, 1150); }
  $("play").onclick = e => { e.stopPropagation(); timer ? stop() : play(); };
  $("scrub").oninput = e => { stop(); show(+e.target.value); };
  show(0);
  return { enter() { show(0); setTimeout(play, 900); }, leave: stop,
    mix() { const t = D.bev[i] + D.lng[i] || 1, b = Math.round(D.lng[i]*bioShare[i]); return [D.bev[i]/t, b/t]; } };
})();

/* ---------- waterfall + phases ---------- */
(function () {
  const s = $("wf"), W = 1060, H = 520, L = 20, T = 60, B = 70, ph = H-T-B;
  const tot = k => D.cost[k].reduce((a,b)=>a+b,0);
  const steps = [["Buying", tot("buy"), "--acc"], ["Insurance", tot("insurance"), "--lng"], ["Maintenance", tot("maintenance"), "--bio"], ["Fuel", tot("fuel"), "--dsl"], ["Resale", tot("resale"), "--bev"]];
  const ymax = steps.slice(0,4).reduce((a,x)=>a+x[1],0) * 1.08, Y = v => T + ph*(1 - v/ymax);
  const n = steps.length + 1, slot = (W-L)/n, bw = slot*0.62;
  let run = 0;
  steps.forEach(([name, v, c], k) => {
    const x = L + slot*k + (slot-bw)/2, y0 = run, y1 = run + v;
    el("rect", {x, y:Y(Math.max(y0,y1)), width:bw, height:Math.abs(Y(y0)-Y(y1)), rx:8, fill:css(c), class:"bar" + (v<0?" neg":""), style:`--d:${0.4+k*0.35}s`}, s);
    if (k < steps.length) el("line", {x1:x+bw, x2:x+slot, y1:Y(y1), y2:Y(y1), stroke:"#5f7686", "stroke-dasharray":"6 6", "stroke-width":2, class:"fadein", style:`--d:${0.8+k*0.35}s`}, s);
    const t = el("text", {x:x+bw/2, y:Y(Math.max(y0,y1))-14, "text-anchor":"middle", class:"chartlab fadein", fill:"#eef1ec", style:`--d:${0.7+k*0.35}s;font-size:26px`}, s); t.textContent = (v<0?"−":"+") + "$" + (Math.abs(v)/1e6).toFixed(1) + "M";
    const l = el("text", {x:x+bw/2, y:H-B+38, "text-anchor":"middle", class:"ax"}, s); l.textContent = name;
    run = y1;
  });
  const x = L + slot*(n-1) + (slot-bw)/2;
  el("rect", {x, y:Y(run), width:bw, height:Y(0)-Y(run), rx:8, fill:"#eef1ec", class:"bar", style:`--d:${0.4+steps.length*0.35}s`}, s);
  const t = el("text", {x:x+bw/2, y:Y(run)-14, "text-anchor":"middle", class:"chartlab fadein", fill:css("--acc"), style:`--d:${0.7+steps.length*0.35}s`}, s); t.textContent = "$" + (run/1e6).toFixed(2) + "M";
  const l = el("text", {x:x+bw/2, y:H-B+38, "text-anchor":"middle", class:"ax", style:"font-weight:700;fill:#eef1ec"}, s); l.textContent = "Total";
  el("line", {x1:L, x2:W, y1:Y(0), y2:Y(0), stroke:"#5f7686", "stroke-width":2}, s);
  $("costh").textContent = `Total cost over 16 years: $${fmtM(D.total)}`;
  const g = $("gapc"); g.dataset.to = D.gap ?? 2.1;
  $("lbtxt").textContent = D.lb ? `above the true optimum: the solver proved no plan can cost less than $${fmtM(D.lb)}` : "optimality gap reported by the solver";
  const firstBev = D.years[D.bev.findIndex(b=>b>0)], allBev = D.years[D.lng.findIndex((l,i)=>i>0 && l===0 && D.bev[i]>0)];
  const bioY = D.years.filter((_,i)=>D.km.BioLNG[i]>1);
  const ph_ = [[`2023–${bioY[0]-1}`, "Cheapest per km", "All-LNG fleet", "--lng"], [`${bioY[0]}–${bioY[bioY.length-1]}`, "Blend cleaner fuel", "BioLNG when the cap binds", "--bio"],
               [`${firstBev}–${allBev}`, "Switch to electric", "BEVs replace LNG", "--bev"], [`${allBev}–2038`, "Zero emissions", "100% BEV", "#5fd3b9"]];
  $("phases").innerHTML = ph_.map(([a,b,c,col],k)=>`<div class="phase in" style="--c:${col.startsWith("--")?`var(${col})`:col};--d:${3.2+k*0.2}s"><p class="mono">${a}</p><b>${b}</b><p>${c}</p></div>`).join("");
})();


/* ---------- scenery: hills, city, turbines, clouds ---------- */
function scenery(host, H) {
  const hy = x => H*0.62 + 34*Math.sin(2*Math.PI*x/960) + 20*Math.sin(2*Math.PI*x/480 + 1);
  let hills = `M0 ${H}`; for (let x = 0; x <= 3840; x += 20) hills += ` L${x} ${hy(x).toFixed(1)}`; hills += ` L3840 ${H} Z`;
  let rnd = 7; const R = () => (rnd = (rnd*9301 + 49297) % 233280) / 233280;
  let city = "", wins = "";
  const base = H*0.72;
  for (let x = 0; x < 1920;) {
    const w = 50 + R()*70, h = 60 + R()*170;
    for (const off of [0, 1920]) {
      city += `<rect x="${(x+off).toFixed(0)}" y="${(base-h).toFixed(0)}" width="${w.toFixed(0)}" height="${h.toFixed(0)}" fill="#0f2130"/>`;
    }
    for (let wy = base-h+14; wy < base-12; wy += 26) for (let wx = x+10; wx < x+w-14; wx += 20)
      if (R() > .72) { const d = (R()*4).toFixed(2); for (const off of [0, 1920]) wins += `<rect class="win" x="${(wx+off).toFixed(0)}" y="${wy.toFixed(0)}" width="8" height="10" fill="#ffd08a" style="animation-delay:-${d}s;animation-duration:${(2+R()*4).toFixed(1)}s"/>`; }
    x += w + 6 + R()*20;
  }
  let turb = "";
  for (const x0 of [140, 470, 820, 1190, 1560]) for (const off of [0, 1920]) {
    const x = x0 + off, y = hy(x0) + 6, hub = y - 150;
    turb += `<line x1="${x}" y1="${y}" x2="${x}" y2="${hub}" stroke="#7d93a3" stroke-width="5"/>
      <g class="blades" style="transform-origin:${x}px ${hub}px;animation-duration:${(2.4 + (x0 % 5)*0.4).toFixed(1)}s">
      ${[0,120,240].map(a => `<path d="M${x} ${hub} L${x-5} ${hub-70} L${x} ${hub-82} L${x+5} ${hub-70} Z" fill="#c9d6df" transform="rotate(${a} ${x} ${hub})"/>`).join("")}</g>
      <circle cx="${x}" cy="${hub}" r="6" fill="#eef1ec"/>`;
  }
  host.innerHTML = `<div class="sunb"></div>
   ${[0,1,2,3].map(k => `<div class="cloud" style="top:${20+k*48}px;width:${180+k*70}px;--t:${70+k*18}s;--d:-${k*17}s"></div>`).join("")}
   <svg class="loop" style="--t:120s;opacity:.55" width="3840" height="${H}" viewBox="0 0 3840 ${H}"><path d="${hills}" fill="#13293a"/></svg>
   <svg class="loop" style="--t:70s" width="3840" height="${H}" viewBox="0 0 3840 ${H}">${turb}</svg>
   <svg class="loop" style="--t:45s" width="3840" height="${H}" viewBox="0 0 3840 ${H}">${city}${wins}<rect x="0" y="${base}" width="3840" height="${H-base}" fill="#0a141b"/></svg>`;
}
scenery($("scene1"), 520); scenery($("scene2"), 300);
$("months").innerHTML = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ").map((m,k) => `<span style="left:${(k+0.5)/12*100}%;--d:${k*0.5}s">${m}</span>`).join("");

/* ---------- canvas effects ---------- */
const FX = (function () {
  const c = $("fx"), g = c.getContext("2d"); c.width = 1920; c.height = 1080;
  let mode = "stars", t0 = performance.now(), fired = false, last = performance.now();
  const mouse = {x: -999, y: -999};
  const rand = Math.random;
  const P = Array.from({length: 80}, () => ({x: rand()*1920, y: rand()*1080, vx: (rand()-.5)*.5, vy: (rand()-.5)*.5}));
  const ST = Array.from({length: 160}, () => ({x: rand()*1920, y: rand()*700, r: rand()*1.8+.4, p: rand()*6.28, s: .5+rand()*2}));
  let shoot = null, bubbles = [], conf = [], trucks = [], nextTruck = 0;
  const cols = 54, drops = Array.from({length: cols}, () => rand()*-40), chars = "01ΣΔλ≤≥+−=∂xkm$CO₂∑";
  const glyph = (i, r) => chars[(i*31 + r*17) % chars.length];
  function network(col, alpha) {
    for (const p of P) {
      const dx = p.x - mouse.x, dy = p.y - mouse.y, d2 = dx*dx + dy*dy;
      if (d2 < 32000) { const f = 1.2/Math.sqrt(d2+1); p.vx += dx*f*.06; p.vy += dy*f*.06; }
      p.vx *= .985; p.vy *= .985; p.vx += (rand()-.5)*.03; p.vy += (rand()-.5)*.03;
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0) p.x += 1920; if (p.x > 1920) p.x -= 1920; if (p.y < 0) p.y += 1080; if (p.y > 1080) p.y -= 1080;
    }
    g.lineWidth = 1.2;
    for (let a = 0; a < P.length; a++) for (let b = a+1; b < P.length; b++) {
      const dx = P[a].x-P[b].x, dy = P[a].y-P[b].y, d = Math.hypot(dx, dy);
      if (d < 180) { g.strokeStyle = `rgba(${col},${(1-d/180)*alpha})`; g.beginPath(); g.moveTo(P[a].x, P[a].y); g.lineTo(P[b].x, P[b].y); g.stroke(); }
    }
    g.fillStyle = `rgba(${col},${alpha*2.4})`;
    for (const p of P) { g.beginPath(); g.arc(p.x, p.y, 2.6, 0, 6.29); g.fill(); }
  }
  function stars(now) {
    for (const s of ST) { const a = .25 + .75*Math.abs(Math.sin(now/1000*s.s + s.p)); g.fillStyle = `rgba(230,238,245,${a*.8})`; g.beginPath(); g.arc(s.x, s.y, s.r, 0, 6.29); g.fill(); }
    if (!shoot && rand() < .008) shoot = {x: 300 + rand()*1300, y: 40 + rand()*200, l: 0};
    if (shoot) { shoot.l += 1; const L = shoot.l*18, x = shoot.x + L, y = shoot.y + L*.35;
      const gr = g.createLinearGradient(x-220, y-77, x, y); gr.addColorStop(0, "rgba(255,255,255,0)"); gr.addColorStop(1, "rgba(255,230,180,.95)");
      g.strokeStyle = gr; g.lineWidth = 3; g.beginPath(); g.moveTo(x-220, y-77); g.lineTo(x, y); g.stroke();
      if (shoot.l > 50) shoot = null; }
  }
  function co2() {
    if (rand() < .12) bubbles.push({x: rand()*1920, y: 1120, r: 14 + rand()*26, v: .6 + rand()*1.4, p: rand()*6});
    g.textAlign = "center"; g.textBaseline = "middle";
    bubbles = bubbles.filter(b => b.y > -60);
    for (const b of bubbles) {
      b.y -= b.v; b.p += .02; const x = b.x + Math.sin(b.p)*20, fade = Math.min(1, b.y/700);
      g.strokeStyle = `rgba(255,122,89,${.45*fade})`; g.lineWidth = 2; g.beginPath(); g.arc(x, b.y, b.r, 0, 6.29); g.stroke();
      g.fillStyle = `rgba(255,122,89,${.1*fade})`; g.fill();
      g.fillStyle = `rgba(255,180,160,${.6*fade})`; g.font = `600 ${Math.round(b.r*.7)}px Inter, sans-serif`; g.fillText("CO₂", x, b.y);
    }
  }
  function code() {
    g.font = "22px 'JetBrains Mono', monospace"; g.textAlign = "center";
    for (let i = 0; i < cols; i++) {
      const head = Math.floor(drops[i]);
      for (let k = 0; k < 14; k++) { const r = head - k; if (r < 0) continue;
        g.fillStyle = k === 0 ? "rgba(200,255,235,.55)" : `rgba(43,179,154,${.32*(1-k/14)})`;
        g.fillText(glyph(i, r), i*36 + 18, r*30); }
      drops[i] += .18 + (i % 5)*.03;
      if (drops[i]*30 > 1300) drops[i] = rand()*-20;
    }
  }
  function truckShape(x, y, s, col) {
    g.fillStyle = col; g.beginPath(); g.roundRect(x, y, 78*s, 40*s, 5*s); g.fill();
    g.globalAlpha = .8; g.beginPath(); g.moveTo(x+84*s, y+12*s); g.lineTo(x+102*s, y+12*s); g.lineTo(x+116*s, y+26*s); g.lineTo(x+116*s, y+40*s); g.lineTo(x+84*s, y+40*s); g.fill(); g.globalAlpha = 1;
    g.fillStyle = "#0b141b"; for (const wx of [20, 60, 100]) { g.beginPath(); g.arc(x+wx*s, y+44*s, 8*s, 0, 6.29); g.fill(); }
  }
  function road(now) {
    const y = 66;
    g.strokeStyle = "rgba(120,150,170,.35)"; g.lineWidth = 3; g.setLineDash([40, 30]); g.lineDashOffset = -now/8;
    g.beginPath(); g.moveTo(0, y+34); g.lineTo(1920, y+34); g.stroke(); g.setLineDash([]);
    if (now > nextTruck) {
      const m = SIM.mix(), r = rand(), col = r < m[0] ? "#2bb39a" : r < m[0]+m[1] ? "#9cc4f2" : "#4a82d0";
      trucks.push({x: -140, v: 3 + rand()*2.5, col, ev: col === "#2bb39a"}); nextTruck = now + 550 + rand()*700;
    }
    trucks = trucks.filter(t => t.x < 2000);
    for (const t of trucks) {
      t.x += t.v; truckShape(t.x, y-14, .55, t.col);
      if (!t.ev) for (let k = 0; k < 3; k++) { g.fillStyle = `rgba(150,170,185,${.25 - k*.07})`; g.beginPath(); g.arc(t.x - 8 - k*14, y + 4 - k*4, 5 + k*3, 0, 6.29); g.fill(); }
      else { g.strokeStyle = "rgba(43,179,154,.6)"; g.lineWidth = 2; g.beginPath(); g.moveTo(t.x-6, y+8); g.lineTo(t.x-40, y+8); g.stroke(); }
    }
  }
  function confetti(dt) {
    if (!fired && dt > 2.7) { fired = true;
      const colors = ["#f0a23b","#2bb39a","#4a82d0","#9cc4f2","#ff7a59","#eef1ec"];
      for (const [cx, cy, dir] of [[1060, 520, 0], [140, 1080, 1], [1780, 1080, -1]])
        for (let k = 0; k < 110; k++) conf.push({x: cx, y: cy, vx: dir ? dir*(6+rand()*12) : (rand()-.5)*20, vy: -(8 + rand()*16), r: rand()*6, vr: (rand()-.5)*.4, c: colors[k % 6], w: 10 + rand()*10, h: 6 + rand()*6});
    }
    conf = conf.filter(p => p.y < 1150);
    for (const p of conf) { p.vy += .32; p.vx *= .99; p.x += p.vx; p.y += p.vy; p.r += p.vr;
      g.save(); g.translate(p.x, p.y); g.rotate(p.r); g.fillStyle = p.c; g.fillRect(-p.w/2, -p.h/2, p.w, p.h*Math.abs(Math.cos(p.r*1.7))+1); g.restore(); }
  }
  // floating cards: gentle bob + tilt toward the mouse
  function cards(now) {
    const sl = document.querySelector(".slide.active"); if (!sl) return;
    const st = $("stage").getBoundingClientRect(), k = st.width/1920;
    sl.querySelectorAll(".card,.rule,.phase").forEach((e, i) => {
      if (e.getAnimations().some(a => a.playState === "running" && a.animationName !== "stripes" && a.animationName !== "sweep")) return;
      const r = e.getBoundingClientRect(), cx = (r.left + r.width/2 - st.left)/k, cy = (r.top + r.height/2 - st.top)/k;
      const w = r.width/k, h = r.height/k, dx = (mouse.x - cx)/w, dy = (mouse.y - cy)/h;
      const near = Math.abs(dx) < .7 && Math.abs(dy) < .7;
      const bob = Math.sin(now/1000*1.1 + i*0.9)*5;
      e.style.transform = `perspective(1000px) translateY(${bob.toFixed(2)}px)` + (near ? ` rotateY(${(dx*10).toFixed(2)}deg) rotateX(${(-dy*10).toFixed(2)}deg) scale(1.02)` : "");
    });
  }
  function frame(now) {
    const dt = (now - t0)/1000; last = now;
    g.clearRect(0, 0, 1920, 1080);
    if (mode === "stars") { stars(now); network("120,160,190", .08); }
    else if (mode === "code") { code(); }
    else network(mode === "co2" ? "255,122,89" : "120,170,220", mode === "co2" ? .1 : .14);
    if (mode === "co2") co2();
    if (mode === "road") road(now);
    if (mode === "confetti") confetti(dt);
    cards(now);
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  $("stage").addEventListener("mousemove", e => {
    const st = $("stage").getBoundingClientRect(), k = st.width/1920;
    mouse.x = (e.clientX - st.left)/k; mouse.y = (e.clientY - st.top)/k;
    const sp = $("spot"); sp.style.left = mouse.x + "px"; sp.style.top = mouse.y + "px";
  });
  $("stage").addEventListener("mouseleave", () => { mouse.x = mouse.y = -999; $("spot").style.left = "-999px"; });
  return { set(m) { mode = m; t0 = performance.now(); fired = false; conf = []; bubbles = []; trucks = []; } };
})();

/* ---------- counters ---------- */
function runCounters(sl) {
  sl.querySelectorAll(".cnt").forEach(c => {
    const to = parseFloat(c.dataset.to || 0), dec = +(c.dataset.dec || 0), pre = c.dataset.pre || "", suf = c.dataset.suf || "";
    const delay = parseFloat(getComputedStyle(c.closest(".pop,.in") || c).getPropertyValue("--d")) || 0;
    const t0 = performance.now() + delay*1000, dur = 1400;
    c.textContent = pre + (0).toFixed(dec) + suf;
    const step = now => { const p = Math.min(Math.max((now - t0)/dur, 0), 1), e = 1 - Math.pow(1-p, 3);
      c.textContent = pre + (to*e).toFixed(dec) + suf; if (p < 1) requestAnimationFrame(step); };
    requestAnimationFrame(step);
  });
}

/* ---------- odometer on the year slide ---------- */
let odoRaf = null;
function odo(on) {
  cancelAnimationFrame(odoRaf); if (!on) return;
  const t0 = performance.now();
  const f = now => { const p = ((now - t0) % 6000) / 6000; $("odo").textContent = Math.round(p * 100000).toLocaleString("en-US"); odoRaf = requestAnimationFrame(f); };
  odoRaf = requestAnimationFrame(f);
}

/* ---------- navigation ---------- */
const S = [...document.querySelectorAll(".slide")]; let cur = -1;
S.forEach((s, k) => { if (k > 0 && k < S.length - 1) s.insertAdjacentHTML("beforeend", `<div class="footer"><span>Shell.ai fleet transition · mini model (S1 × D1–D2, 2023–2038)</span><span>${k+1} / ${S.length}</span></div>`); });
function fit() { const k = Math.min(innerWidth/1920, innerHeight/1080); $("stage").style.transform = `translate(-50%,-50%) scale(${k})`; }
function go(n) {
  n = Math.max(0, Math.min(S.length-1, n)); if (n === cur) return;
  if (S[cur] && S[cur].contains($("lot"))) SIM.leave();
  S.forEach((s, j) => s.classList.toggle("active", j === n)); cur = n;
  runCounters(S[n]); odo(S[n].contains($("odo"))); FX.set(S[n].dataset.fx || "network");
  if (S[n].contains($("lot"))) SIM.enter();
  $("bar").style.width = ((n+1)/S.length*100) + "%"; history.replaceState(null, "", "#" + (n+1));
}
addEventListener("resize", fit);
addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT") return;
  if (["ArrowRight","PageDown"," ","Enter"].includes(e.key)) { e.preventDefault(); go(cur+1); }
  if (["ArrowLeft","PageUp","Backspace"].includes(e.key)) { e.preventDefault(); go(cur-1); }
  if (e.key === "Home") go(0); if (e.key === "End") go(S.length-1);
  if (e.key === "f" && document.documentElement.requestFullscreen) document.documentElement.requestFullscreen();
});
$("prev").onclick = () => go(cur-1); $("next").onclick = () => go(cur+1);
fit(); go((parseInt(location.hash.slice(1)) || 1) - 1);
</script></body></html>"""

html = HTML.replace("__DATA__", json.dumps(D)).replace("__NMODELS__", str(len(veh)))
open(OUT, "w").write(html)

notes = re.findall(r'<section data-fx="\w+" class="slide" data-notes="([^"]*)"', html)
with open(OUT.replace(".html", "_script.md"), "w") as f:
    f.write("# Video narration script\n\n")
    for k, n in enumerate(notes, 1):
        f.write(f"**Slide {k}.** {n}\n\n")
print(f"wrote {OUT} with {len(notes)} slides")
