"""
Downloads the six Shell.ai Hackathon 2024 data files into data/.

The files are not stored in this repository because we don't own them. They come from the
official Shell.ai Hackathon 2024 dataset (HackerEarth), as mirrored in the public repo
https://github.com/HagaiRaja/shell-ai-web (pinned to one commit, so the data never changes).

Run:  python get_data.py
"""
import os
import urllib.request

COMMIT = "33fa48044c853c155d1e1349ffab89a7f1a963b8"
BASE = f"https://raw.githubusercontent.com/HagaiRaja/shell-ai-web/{COMMIT}/public/preset/default/"
FILES = ["demand.csv", "vehicles.csv", "vehicles_fuels.csv", "fuels.csv",
         "carbon_emissions.csv", "cost_profiles.csv"]

os.makedirs("data", exist_ok=True)
for name in FILES:
    path = os.path.join("data", name)
    if os.path.exists(path):
        print(f"already there: {path}")
        continue
    urllib.request.urlretrieve(BASE + name, path)
    print(f"downloaded:    {path}")
print("Done. Now run:  python fleet_transition_solver.py --end 2025")
