import json
from datetime import date
from storm_safe.noaa import fetch

for name in ("kp", "dst", "alerts", "scales"):
    with open(f"data/raw_{name}_{date.today()}.json", "w") as f:
        json.dump(fetch(name), f)
    print("saved", name)