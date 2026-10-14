import time
from fastapi import FastAPI
from storm_safe.noaa import get_snapshot
from storm_safe.advisories import get_advisories

app=FastAPI(title="Storm-Safe")
_cache = {}

def cached(key, fn, ttl):
    """
    Reuse a result for `ttl` seconds so we don't hammer NOAA/Tavily
    """
    now=time.time()
    if key in _cache and now - _cache[key][0]<ttl:
        return _cache[key][1]
    value = fn()
    _cache[key] = (now, value)
    return value

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/snapshot")
def snapshot():
    return cached("snapshot", get_snapshot, ttl=60)

@app.get("/advisories")
def advisories():
    return cached("advisories", get_advisories, ttl=600)