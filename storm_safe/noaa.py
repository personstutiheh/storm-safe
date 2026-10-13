import json
import requests

BASE = "https://services.swpc.noaa.gov"
PATHS = {
    "scales": "/products/noaa-scales.json",
    "kp": "/products/noaa-planetary-k-index.json",
    "dst": "/products/kyoto-dst.json",
    "plasma": "/json/rtsw/rtsw_wind_1m.json",
    "mag": "/json/rtsw/rtsw_mag_1m.json",
    "xray": "/json/goes/primary/xrays-6-hour.json",
    "proton": "/json/goes/primary/integral-protons-6-hour.json",
    "alerts": "/products/alerts.json",
}


def fetch(name, timeout=10):
    r = requests.get(BASE + PATHS[name], timeout=timeout)
    r.raise_for_status()
    return r.json()

def rows_to_dicts(data):
    """Handle both [{...}, ...] and [[header...], [row...], ...] shapes."""
    if data and isinstance(data[0], list):
        header = data[0]
        return [dict(zip(header, row)) for row in data[1:]]
    return data

def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

def last_valid(rows, key):
    """Most recent row where `key` is a usable number."""
    for row in reversed(rows):
        v = num(row.get(key))
        if v is not None:
            return v, row.get("time_tag")
    return None, None

def last_valid_any(rows, keys):
    """Newest usable number under any of `keys`; prefers the active source."""
    active = [r for r in rows if r.get("active") in (True, "true", 1)]
    for pool in (active, rows):
        for row in sorted(pool, key=lambda r: r.get("time_tag") or "", reverse=True):
            for k in keys:
                v = num(row.get(k))
                if v is not None and v > -9000:  # skip fill values like -9999
                    return v, row.get("time_tag")
    return None, None

def flare_class(flux):
    if flux is None:
        return None
    for letter, floor in (("X", 1e-4), ("M", 1e-5), ("C", 1e-6), ("B", 1e-7)):
        if flux >= floor:
            return f"{letter}{flux / floor:.1f}"
    return "A"

def _scales(data):
    cur = data.get("0", {})  # "0" = current observed conditions
    return {k: int(cur.get(k, {}).get("Scale", 0) or 0) for k in ("G", "S", "R")}

def _kp(data):
    rows = rows_to_dicts(data)
    key = "Kp" if "Kp" in rows[-1] else "kp"
    return last_valid(rows, key)

def _xray(data):
    # long channel (0.1-0.8 nm) is the one used for flare classes
    rows = [r for r in data if r.get("energy") == "0.1-0.8nm"] or data
    flux, t = last_valid(rows, "flux")
    return {"flux": flux, "class": flare_class(flux), "time": t}

def _proton(data):
    rows = [r for r in data if r.get("energy") == ">=10 MeV"] or data
    flux, t = last_valid(rows, "flux")
    return {"flux_ge10MeV": flux, "time": t}

def get_snapshot():
    """Return one dict of current conditions. A failed feed becomes None."""
    snap, errors = {}, {}

    def grab(name, fn, feed=None):
        try:
            snap[name] = fn(fetch(feed or name))
        except Exception as e:  # keep going if one feed is down
            snap[name] = None
            errors[name] = repr(e)

    grab("scales", _scales)
    grab("kp", lambda d: dict(zip(("value", "time"), _kp(d))))
    grab("dst", lambda d: dict(zip(("value", "time"), last_valid(rows_to_dicts(d), "dst"))))
    grab("solar_wind_speed", lambda d: dict(zip(("km_s", "time"), last_valid_any(rows_to_dicts(d), ["proton_speed", "speed"]))), feed="plasma")
    grab("bz", lambda d: dict(zip(("nT", "time"), last_valid_any(rows_to_dicts(d), ["bz_gsm", "bz_gse"]))), feed="mag")
    grab("xray", _xray)
    grab("proton", _proton)
    grab("alerts", lambda d: [
        {"issued": a.get("issue_datetime"), "message": (a.get("message") or "")[:400]}
        for a in d[:3]
    ])
    snap["errors"] = errors
    return snap

def save_snapshot(path="data/sample_snapshot.json"):
    with open(path, "w") as f:
        json.dump(get_snapshot(), f, indent=2)

if __name__ == "__main__":
    print(json.dumps(get_snapshot(), indent=2))