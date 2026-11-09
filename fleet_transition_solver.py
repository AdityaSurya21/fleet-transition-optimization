"""
=====================================================================================
 Shell.ai Hackathon 2024 - Fleet Transition Challenge  (mini version)
=====================================================================================

 PROBLEM (in one line)
   Choose which trucks to BUY, how to USE them (fuel, route bucket, km) and when to
   SELL them, every year 2023-2038, so that all freight demand is met and every
   year's carbon cap is respected, at the LOWEST total cost.

 OUR SUBSET (what this file solves)
   - Size S1 only, distance buckets D1 and D2      (2 of the 16 demand cells)
   - All 16 years, all 3 drivetrains (BEV, Diesel, LNG), all 5 fuels
   - All 8 rules and the full cost formula from the problem statement
   - The carbon cap is scaled to our subset's share of total demand

 METHOD
   Mixed-Integer Linear Program (MILP), built with PuLP and solved with HiGHS.

 HOW TO RUN
   pip install "pulp==2.9.0" highspy pandas
   Put the 6 CSV files in a folder called  data/  next to this script, then:

       python fleet_transition_solver.py                     # full 16 years (~5 min)
       python fleet_transition_solver.py --end 2025          # 3-year demo   (< 1 s)
       python fleet_transition_solver.py --log               # show the solver log

 OUTPUT
   out/solution.csv   the plan, in the competition's submission format
   out/results.json   yearly summary (fleet, km by fuel, CO2, costs), used by the slides
=====================================================================================
"""
import argparse
import json
import math
import os
from collections import defaultdict

import pandas as pd
import pulp

# =====================================================================================
# 0. SETTINGS
# =====================================================================================
ap = argparse.ArgumentParser(description="Fleet transition MILP (mini version)")
ap.add_argument("--data", default="data", help="folder with the 6 CSV files")
ap.add_argument("--out", default="out", help="folder for solution.csv and results.json")
ap.add_argument("--start", type=int, default=2023)
ap.add_argument("--end", type=int, default=2038)
ap.add_argument("--time-limit", type=int, default=300, help="solver time limit in seconds")
ap.add_argument("--gap", type=float, default=0.005, help="stop when within this relative gap of optimal")
ap.add_argument("--log", action="store_true", help="print the HiGHS solver log")
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)

YEARS = list(range(args.start, args.end + 1))
SIZES = ["S1"]                      # <- add "S2", "S3", "S4" to scale up
BUCKETS = ["D1", "D2"]              # <- add "D3", "D4" to scale up
BUCKET_NUM = {"D1": 1, "D2": 2, "D3": 3, "D4": 4}
SAFETY = 5                          # tiny buffer (km / kg) so rounding in solution.csv never breaks a rule

# =====================================================================================
# 1. LOAD THE DATA
# =====================================================================================
demand = pd.read_csv(f"{args.data}/demand.csv")
vehicles = pd.read_csv(f"{args.data}/vehicles.csv")
veh_fuel = pd.read_csv(f"{args.data}/vehicles_fuels.csv")
fuels = pd.read_csv(f"{args.data}/fuels.csv")
caps = pd.read_csv(f"{args.data}/carbon_emissions.csv")
profile = pd.read_csv(f"{args.data}/cost_profiles.csv").set_index("End of Year")

demand.columns = ["Year", "Size", "Distance", "Demand"]
vehicles.columns = ["ID", "Type", "Size", "Year", "Cost", "Range", "Distance"]
veh_fuel.columns = ["ID", "Fuel", "Cons"]
fuels.columns = ["Fuel", "Year", "CO2", "Price", "Unc"]
caps.columns = ["Year", "Cap"]

# cost profile by age of the truck (age 1 = the year it was bought)
RESALE = (profile["Resale Value %"] / 100).to_dict()
INSUR = (profile["Insurance Cost %"] / 100).to_dict()
MAINT = (profile["Maintenance Cost %"] / 100).to_dict()

# demand we must meet: D[year, bucket] in km
D = {(r.Year, r.Distance): r.Demand for r in demand.itertuples()
     if r.Year in YEARS and r.Size in SIZES and r.Distance in BUCKETS}

# trucks we may buy (rule 1: size match, by keeping only S1 models)
V = vehicles[vehicles.Year.isin(YEARS) & vehicles.Size.isin(SIZES)].set_index("ID")

# which fuels each truck can burn, and how much per km
FUELS_OF = defaultdict(dict)
for r in veh_fuel.itertuples():
    if r.ID in V.index:
        FUELS_OF[r.ID][r.Fuel] = r.Cons

PRICE = {(r.Fuel, r.Year): r.Price for r in fuels.itertuples()}   # $ per unit of fuel
CO2 = {(r.Fuel, r.Year): r.CO2 for r in fuels.itertuples()}       # kg CO2 per unit of fuel

# Carbon cap: the file's cap is for the WHOLE fleet (all 16 demand cells).
# Our subset gets its fair share = subset demand / total demand in that year.
total_demand = demand.groupby("Year").Demand.sum()
cap_full = caps.set_index("Year").Cap
CAP = {t: float(cap_full[t]) * sum(D[t, b] for b in BUCKETS) / total_demand[t] for t in YEARS}


def age(v, t):
    """Age of truck model v in year t (1 in its purchase year)."""
    return t - V.Year[v] + 1


def owned(v, t):
    """Rules 5 & 6: a model is bought only in its own year and kept at most 10 years."""
    return V.Year[v] <= t < V.Year[v] + 10


def can_serve(v, b):
    """Rule 2: a truck of bucket Dx can serve D1..Dx."""
    return BUCKET_NUM[V.Distance[v]] >= BUCKET_NUM[b]


print(f"Scope: sizes {SIZES}, buckets {BUCKETS}, years {YEARS[0]}-{YEARS[-1]}, "
      f"{len(V)} truck models, {sum(len(f) for f in FUELS_OF.values())} truck-fuel pairs")

# =====================================================================================
# 2. DECISION VARIABLES
# =====================================================================================
m = pulp.LpProblem("fleet_transition_mini", pulp.LpMinimize)

# buy[v]          number of trucks of model v bought (in model v's own year)
buy = {v: pulp.LpVariable(f"buy_{v}", lowBound=0, cat="Integer") for v in V.index}

# fleet[v, t]     number of trucks of model v owned during year t
fleet = {(v, t): pulp.LpVariable(f"fleet_{v}_{t}", lowBound=0, cat="Integer")
         for v in V.index for t in YEARS if owned(v, t)}

# sell[v, t]      number of trucks of model v sold on 31 Dec of year t
sell = {(v, t): pulp.LpVariable(f"sell_{v}_{t}", lowBound=0, cat="Integer") for (v, t) in fleet}

# every way a truck can be used: (model, fuel, bucket, year)
arcs = [(v, f, b, t) for (v, t) in fleet for f in FUELS_OF[v] for b in BUCKETS if can_serve(v, b)]

# use[a]          number of trucks driven on that fuel, in that bucket, that year
use = {a: pulp.LpVariable("use_" + "_".join(map(str, a)), lowBound=0, cat="Integer") for a in arcs}

# km[a]           total km those trucks drive
km = {a: pulp.LpVariable("km_" + "_".join(map(str, a)), lowBound=0) for a in arcs}

# =====================================================================================
# 3. OBJECTIVE:  buy + insurance + maintenance + fuel - resale
# =====================================================================================
cost_buy = pulp.lpSum(V.Cost[v] * buy[v] for v in V.index)
cost_ins = pulp.lpSum(V.Cost[v] * INSUR[age(v, t)] * fleet[v, t] for (v, t) in fleet)
cost_mnt = pulp.lpSum(V.Cost[v] * MAINT[age(v, t)] * fleet[v, t] for (v, t) in fleet)
cost_fuel = pulp.lpSum(km[a] * FUELS_OF[a[0]][a[1]] * PRICE[a[1], a[3]] for a in arcs)
income_sell = pulp.lpSum(V.Cost[v] * RESALE[age(v, t)] * sell[v, t] for (v, t) in fleet)

m += cost_buy + cost_ins + cost_mnt + cost_fuel - income_sell

# =====================================================================================
# 4. CONSTRAINTS
# =====================================================================================
for (v, t) in fleet:
    # Fleet balance (rule 7: buy on 1 Jan, sell on 31 Dec)
    if t == V.Year[v]:
        m += fleet[v, t] == buy[v], f"bought_{v}"
    else:
        m += fleet[v, t] == fleet[v, t - 1] - sell[v, t - 1], f"balance_{v}_{t}"
    m += sell[v, t] <= fleet[v, t], f"sell_owned_{v}_{t}"

    # You can only drive trucks you own
    m += pulp.lpSum(use[a] for a in arcs if a[0] == v and a[3] == t) <= fleet[v, t], f"use_owned_{v}_{t}"

    # Rule 6: every truck is sold by the end of its 10th year
    if age(v, t) == 10:
        m += sell[v, t] == fleet[v, t], f"max_life_{v}_{t}"

for a in arcs:
    # Each truck in use drives at most its yearly range
    m += km[a] <= V.Range[a[0]] * use[a], "range_" + "_".join(map(str, a))

for t in YEARS:
    # Rule 4: meet demand in every distance bucket
    for b in BUCKETS:
        m += pulp.lpSum(km[a] for a in arcs if a[2] == b and a[3] == t) >= D[t, b] + SAFETY, f"demand_{b}_{t}"

    # Rule 3: total CO2 must stay under the carbon cap
    m += pulp.lpSum(km[a] * FUELS_OF[a[0]][a[1]] * CO2[a[1], t] for a in arcs if a[3] == t) \
        <= CAP[t] - SAFETY, f"carbon_{t}"

    # Rule 8: sell at most 20% of the fleet in any year
    m += pulp.lpSum(sell[v, s] for (v, s) in fleet if s == t) \
        <= 0.2 * pulp.lpSum(fleet[v, s] for (v, s) in fleet if s == t), f"sell_limit_{t}"

print(f"Model: {len(m.variables())} variables, {len(m.constraints)} constraints")

# =====================================================================================
# 5. SOLVE
# =====================================================================================
solver = pulp.HiGHS(msg=args.log, timeLimit=args.time_limit, gapRel=args.gap)
m.solve(solver)
total = pulp.value(m.objective)
# Ask HiGHS directly: PuLP reports "Optimal" even when the time limit stopped the search.
highs = m.solverModel
info = highs.getInfo()
highs_status = highs.modelStatusToString(highs.getModelStatus())
lower_bound, gap = info.mip_dual_bound, info.mip_gap
print(f"\nHiGHS status: {highs_status}")
print(f"Total cost: ${total:,.0f}   proven lower bound: ${lower_bound:,.0f}   gap: {gap:.2%}")

# =====================================================================================
# 6. WRITE solution.csv  (competition format)
# =====================================================================================
val = lambda x: round(x.value() or 0, 6)
rows = []
for v in V.index:
    if val(buy[v]) > 0.5:
        rows.append([V.Year[v], v, round(val(buy[v])), "Buy", "", "", 0])
for a in arcs:
    n = round(val(use[a]))
    if n > 0:
        per_truck = min(math.ceil(val(km[a]) / n * 100) / 100, float(V.Range[a[0]]))
        rows.append([a[3], a[0], n, "Use", a[1], a[2], per_truck])
for (v, t) in fleet:
    if val(sell[v, t]) > 0.5:
        rows.append([t, v, round(val(sell[v, t])), "Sell", "", "", 0])
sol = pd.DataFrame(rows, columns=["Year", "ID", "Num_Vehicles", "Type", "Fuel",
                                  "Distance_bucket", "Distance_per_vehicle(km)"])
type_order = {"Buy": 0, "Use": 1, "Sell": 2}
sol = sol.sort_values(["Year", "Type", "ID"], key=lambda c: c.map(type_order) if c.name == "Type" else c)
sol.to_csv(f"{args.out}/solution.csv", index=False)

# =====================================================================================
# 7. INDEPENDENT CHECK - re-read solution.csv and test every rule from scratch
# =====================================================================================
def check(sol):
    errors, owned_now, cost = [], defaultdict(int), 0.0
    for t in YEARS:
        yr = sol[sol.Year == t]
        for r in yr[yr.Type == "Buy"].itertuples():
            if V.Year[r.ID] != t: errors.append(f"{t}: rule 5, {r.ID} bought in wrong year")
            owned_now[r.ID] += r.Num_Vehicles
            cost += V.Cost[r.ID] * r.Num_Vehicles
        fleet_size = sum(owned_now.values())
        for v, n in owned_now.items():
            if n:
                cost += V.Cost[v] * (INSUR[age(v, t)] + MAINT[age(v, t)]) * n
        used, km_b, co2 = defaultdict(int), defaultdict(float), 0.0
        for r in yr[yr.Type == "Use"].itertuples():
            dist = r._7
            used[r.ID] += r.Num_Vehicles
            if dist > V.Range[r.ID] + 1e-6: errors.append(f"{t}: {r.ID} over its yearly range")
            if not can_serve(r.ID, r.Distance_bucket): errors.append(f"{t}: rule 2, {r.ID} in {r.Distance_bucket}")
            if r.Fuel not in FUELS_OF[r.ID]: errors.append(f"{t}: {r.ID} cannot use {r.Fuel}")
            k = r.Num_Vehicles * dist
            km_b[r.Distance_bucket] += k
            co2 += k * FUELS_OF[r.ID][r.Fuel] * CO2[r.Fuel, t]
            cost += k * FUELS_OF[r.ID][r.Fuel] * PRICE[r.Fuel, t]
        for v, n in used.items():
            if n > owned_now[v]: errors.append(f"{t}: using more {v} than owned")
        for b in BUCKETS:
            if km_b[b] < D[t, b] - 1e-6: errors.append(f"{t}: rule 4, demand {b} not met")
        if co2 > CAP[t] + 1e-6: errors.append(f"{t}: rule 3, CO2 {co2:,.0f} > cap {CAP[t]:,.0f}")
        sold = 0
        for r in yr[yr.Type == "Sell"].itertuples():
            if r.Num_Vehicles > owned_now[r.ID]: errors.append(f"{t}: selling more {r.ID} than owned")
            cost -= V.Cost[r.ID] * RESALE[age(r.ID, t)] * r.Num_Vehicles
            owned_now[r.ID] -= r.Num_Vehicles
            sold += r.Num_Vehicles
        if sold > 0.2 * fleet_size + 1e-9: errors.append(f"{t}: rule 8, sold {sold} of {fleet_size}")
        for v, n in owned_now.items():
            if n and age(v, t) >= 10: errors.append(f"{t}: rule 6, {v} kept past 10 years")
    return errors, cost


errors, recomputed = check(pd.read_csv(f"{args.out}/solution.csv").fillna(""))
print(f"Independent check: {'all rules satisfied' if not errors else f'{len(errors)} problems'}"
      f"  |  recomputed cost ${recomputed:,.0f}")
for e in errors[:20]:
    print("   -", e)

# =====================================================================================
# 8. SUMMARY - year by year
# =====================================================================================
res = {"status": highs_status, "total_cost": total, "lower_bound": lower_bound, "gap": gap, "years": YEARS,
       "demand": {f"{t}_{b}": D[t, b] for (t, b) in D}, "cap": CAP, "per_year": {}}
print(f"\n{'Year':<6}{'BEV':>5}{'LNG':>5}{'Diesel':>8}{'Buy':>6}{'Sell':>6}"
      f"{'CO2 (t)':>10}{'Cap (t)':>10}   Fuel mix (share of km)")
for t in YEARS:
    y = {"fleet": {}, "km_by_fuel": {}, "km_by_bucket_type": {}, "emissions": 0.0, "cost": {}}
    for (v, s) in fleet:
        if s == t:
            y["fleet"][V.Type[v]] = y["fleet"].get(V.Type[v], 0) + round(val(fleet[v, s]))
    for a in arcs:
        if a[3] == t:
            k = val(km[a])
            y["km_by_fuel"][a[1]] = y["km_by_fuel"].get(a[1], 0) + k
            key = f"{a[2]}_{V.Type[a[0]]}"
            y["km_by_bucket_type"][key] = y["km_by_bucket_type"].get(key, 0) + k
            y["emissions"] += k * FUELS_OF[a[0]][a[1]] * CO2[a[1], t]
    y["cost"] = {
        "buy": sum(V.Cost[v] * val(buy[v]) for v in V.index if V.Year[v] == t),
        "insurance": sum(V.Cost[v] * INSUR[age(v, t)] * val(fleet[v, s]) for (v, s) in fleet if s == t),
        "maintenance": sum(V.Cost[v] * MAINT[age(v, t)] * val(fleet[v, s]) for (v, s) in fleet if s == t),
        "fuel": sum(val(km[a]) * FUELS_OF[a[0]][a[1]] * PRICE[a[1], t] for a in arcs if a[3] == t),
        "resale": -sum(V.Cost[v] * RESALE[age(v, t)] * val(sell[v, s]) for (v, s) in fleet if s == t),
    }
    res["per_year"][t] = y
    tot_km = sum(y["km_by_fuel"].values()) or 1
    mix = ", ".join(f"{f} {k / tot_km:.0%}" for f, k in y["km_by_fuel"].items() if k > 1)
    nb = sum(val(buy[v]) for v in V.index if V.Year[v] == t)
    ns = sum(val(sell[v, s]) for (v, s) in fleet if s == t)
    print(f"{t:<6}{y['fleet'].get('BEV', 0):>5}{y['fleet'].get('LNG', 0):>5}{y['fleet'].get('Diesel', 0):>8}"
          f"{nb:>6.0f}{ns:>6.0f}{y['emissions'] / 1000:>10,.0f}{CAP[t] / 1000:>10,.0f}   {mix}")

tot = {k: sum(res["per_year"][t]["cost"][k] for t in YEARS) for k in res["per_year"][YEARS[0]]["cost"]}
print("\nCost breakdown: " + ", ".join(f"{k} ${v / 1e6:,.2f}M" for k, v in tot.items())
      + f"  =>  total ${total / 1e6:,.2f}M")
json.dump(res, open(f"{args.out}/results.json", "w"), indent=1, default=float)
print(f"\nSaved {args.out}/solution.csv ({len(sol)} rows) and {args.out}/results.json")
