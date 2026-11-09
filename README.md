# Fleet Transition Optimization

**The lowest-cost plan to move a truck fleet to zero emissions by 2038.** This is a mixed-integer linear program (MILP) in Python (PuLP + HiGHS) for a subset of the [Shell.ai Hackathon 2024](https://www.hackerearth.com/challenges/new/competitive/shellai-hackathon-2024/) Fleet Transition Challenge, with an animated HTML slide deck that explains the problem and the results.

![Animated deck: the optimal plan, year by year](docs/images/simulation.png)

> 🎥 **Video walkthrough:** [add your video link here]
> 🖥️ **Slides:** download [`deck/fleet_transition_deck.html`](deck/fleet_transition_deck.html) and open it in Chrome or Edge (use ← → to move, F for full screen).

---

## The problem

A logistics company must deliver a fixed number of truck-kilometres every year from 2023 to 2038, while a carbon cap shrinks every year. Freight demand grows **47%**, from 17.2M to 25.3M km a year, while the carbon budget falls **79%**, from 11.7M to 2.4M kg CO₂.

Every year the company decides:

- **Buy:** which truck models to buy and how many (BEV, Diesel or LNG; 192 models in total).
- **Use:** which fuel each truck burns (Electricity, B20, HVO, LNG or BioLNG), which distance bucket it serves, and how many km it drives.
- **Sell:** which trucks to sell at the end of the year.

The goal is the **lowest total cost**: purchase + insurance + maintenance + fuel − resale. These eight rules must hold:

1. A truck only serves demand of its own size (S1–S4).
2. A truck of distance bucket Dx can serve buckets D1 to Dx.
3. Total CO₂ each year stays under that year's carbon cap.
4. Demand is fully met in every year, size and bucket.
5. A model can only be bought in its own year (`BEV_S1_2026` only in 2026).
6. Every truck is sold within 10 years.
7. Trucks are bought on 1 January and sold on 31 December.
8. At most 20% of the fleet can be sold in any year.

## What we solve

To keep the model small enough to explain and to solve on a laptop, we solve **2 of the 16 demand cells** and keep everything else:

| Kept | Left for later |
| --- | --- |
| All 16 years (2023–2038) | Sizes S2–S4 |
| All 3 drivetrains and all 5 fuels | Distance buckets D3–D4 |
| All 8 rules and the full cost formula | Fuel price uncertainty (we use the median prices) |
| Size S1, distance buckets D1 and D2 | |

The carbon cap in the data covers the whole fleet, so our slice gets its fair share each year: the cap × (S1-D1/D2 demand ÷ total demand), about 20%.

## The model

**Decision variables**

| Variable | Type | Meaning |
| --- | --- | --- |
| `buy[v]` | integer | trucks of model *v* bought (in *v*'s own year) |
| `fleet[v,t]` | integer | trucks of model *v* owned in year *t* |
| `sell[v,t]` | integer | trucks of model *v* sold at the end of year *t* |
| `use[v,f,b,t]` | integer | trucks of *v* driven on fuel *f* in bucket *b* in year *t* |
| `km[v,f,b,t]` | continuous | total km those trucks drive |

**Objective**

$$
\min \sum_v c_v\,\text{buy}_v + \sum_{v,t} c_v\,(\text{ins}_{a}+\text{mnt}_{a})\,\text{fleet}_{v,t} + \sum_{v,f,b,t} \text{km}_{v,f,b,t}\,\text{cons}_{v,f}\,p_{f,t} - \sum_{v,t} c_v\,\text{res}_{a}\,\text{sell}_{v,t}
$$

where *c* is the purchase price, *a* the truck's age, *cons* its fuel use per km and *p* the fuel price.

**Constraints**

| Constraint | Rule |
| --- | --- |
| `fleet[v,t] = buy[v]` in the purchase year, else `fleet[v,t-1] − sell[v,t-1]` | fleet balance (5, 7) |
| `Σ km[·,·,b,t] ≥ demand[b,t]`, counting only trucks with bucket ≥ b | demand (1, 2, 4) |
| `km[v,f,b,t] ≤ range[v] · use[v,f,b,t]` | yearly range per truck |
| `Σ use[v,·,·,t] ≤ fleet[v,t]` | can only drive owned trucks |
| `Σ km · cons · CO₂ ≤ cap[t]` | carbon cap (3) |
| `sell[v,t] = fleet[v,t]` at age 10 | 10-year life (6) |
| `Σ sell[·,t] ≤ 0.2 · Σ fleet[·,t]` | 20% sell limit (8) |

For the full 16 years this is about 3,000 variables and 2,240 constraints.

## Results

| Year | BEV | LNG | CO₂ (t) | Cap (t) | Fuel mix (share of km) |
| --- | --- | --- | --- | --- | --- |
| 2023 | 0 | 35 | 1,426 | 2,357 | LNG 100% |
| 2027 | 0 | 40 | 1,592 | 1,599 | LNG 98%, BioLNG 2% |
| 2029 | 0 | 42 | 1,289 | 1,292 | LNG 73%, BioLNG 27% |
| 2030 | 9 | 34 | 1,168 | 1,168 | Electricity 21%, LNG 67%, BioLNG 12% |
| 2032 | 28 | 17 | 638 | 941 | Electricity 63%, LNG 37% |
| 2034 | 47 | 0 | 0 | 750 | Electricity 100% |
| 2038 | 53 | 0 | 0 | 499 | Electricity 100% |

The plan runs in four phases:

1. **2023–2026, cheapest per km:** an all-LNG fleet. Diesel is never chosen, because LNG costs only $15k more to buy and is cheaper per km.
2. **2027–2030, cleaner fuel:** the carbon cap starts to bind, so some LNG trucks switch to BioLNG (about 85% less CO₂).
3. **2030–2034, switch to electric:** BEVs are now about 30% cheaper than in 2023, reach longer routes and have the cheapest fuel per km.
4. **2034–2038, zero emissions:** a 100% BEV fleet.

**Total cost over 16 years: $29.84M** (buying $20.02M + insurance $5.89M + maintenance $4.32M + fuel $9.17M − resale $9.56M).

**Solution quality**

- An independent checker re-reads `solution.csv`, tests every rule from scratch and recomputes the cost. It found **zero violations** and the same cost to the dollar.
- The 16-year solve stopped at its 5-minute time limit. HiGHS proved no plan can cost less than **$29.22M**, so this plan is within **2.1%** of the true optimum. The 3-year version solves to within 0.5% in under a second.

| | |
| --- | --- |
| ![Cover](docs/images/cover.png) | ![Trade-off](docs/images/dilemma.png) |
| ![Results](docs/images/results.png) | ![Simulation](docs/images/simulation.png) |

## How to run

You need Python 3.9 or newer.

```bash
git clone https://github.com/<your-username>/fleet-transition-optimization.git
cd fleet-transition-optimization
pip install -r requirements.txt

python get_data.py                               # downloads the 6 CSVs into data/
python fleet_transition_solver.py --end 2025     # 3-year demo, under 1 second
python fleet_transition_solver.py                # full 16 years, about 5 minutes
python make_deck.py data out deck/fleet_transition_deck.html   # rebuild the slides from the new results
```

Useful options for `fleet_transition_solver.py`: `--start` / `--end` (years), `--time-limit` (seconds, default 300), `--gap` (default 0.005), `--log` (show the solver log), `--data` and `--out` (folders).

To scale up to more of the problem, edit `SIZES` and `BUCKETS` near the top of `fleet_transition_solver.py`.

## Repository structure

```
fleet-transition-optimization/
├── fleet_transition_solver.py   # the MILP: data → model → solve → solution.csv → rule check → summary
├── make_deck.py                 # builds the animated HTML deck from out/results.json
├── get_data.py                  # downloads the hackathon data into data/
├── requirements.txt
├── data/                        # the 6 CSVs (downloaded, not committed)
├── out/
│   ├── solution.csv             # the 16-year plan, in the competition's submission format
│   ├── results.json             # yearly fleet, km by fuel, CO₂, costs, solver bound and gap
│   └── solver_log.txt           # HiGHS log of the 16-year run
├── deck/fleet_transition_deck.html
└── docs/images/                 # screenshots used in this README
```

## Limitations and next steps

- **Scale up:** add sizes S2–S4 and buckets D3–D4. The model grows about 8×, so use a longer time limit or rolling-horizon solving.
- **Fuel price risk:** price uncertainty reaches ±30%; a scenario-based or robust model would protect the plan against price shocks.
- **End of horizon:** trucks still owned in 2038 get no value. Adding a salvage value removes this end effect.
- **Carbon cap share:** the subset gets a demand-proportional share of the cap. The full model would share one cap across all cells.

## Team

Project for **BMN 616, Advanced Optimization Techniques for Managers**, DoMS, IIT Roorkee.

- Aditya Surya
- Chirag Sharma
- Yash Phuke

## Acknowledgements

- Problem statement and data: **Shell.ai Hackathon 2024, Fleet Transition Challenge** (Shell / HackerEarth). The data is not included in this repository; `get_data.py` downloads it from the public mirror [HagaiRaja/shell-ai-web](https://github.com/HagaiRaja/shell-ai-web).
- Solver: [HiGHS](https://highs.dev) through [PuLP](https://github.com/coin-or/pulp).

Code is released under the [MIT License](LICENSE).
