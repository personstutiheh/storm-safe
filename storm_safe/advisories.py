import os
import re
from dotenv import load_dotenv
from tavily import TavilyClient
from urllib.parse import urlparse

load_dotenv()

DEFAULT_QUERY = "geomagnetic storm solar flare satellite space weather"
TRUSTED = ("spaceweather.gov", "swpc.noaa.gov", "noaa.gov", "nasa.gov", "esa.int")

def clean(text):
    text = re.sub(r"\[\]\(\s*", "", text or "")
    text = re.sub(r"\[\.?\s*$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def trim(results, max_chars=500):
    out = []
    for r in results:
        official = is_trusted(r.get("url"))
        text = clean(r.get("content"))
        if official:
            text = strip_boilerplate(text)
        out.append({
            "title": r.get("title"),
            "url": r.get("url"),
            "source_type": "official" if official else "news",
            "snippet": text[:max_chars],
            "published": r.get("published_date"),
        })
    return out

def is_trusted(url):
    host = urlparse(url or "").hostname or ""
    return any(host == d or host.endswith("." + d) for d in TRUSTED)

def rank(results):
    """Official sources first (stable sort keeps the original order otherwise)."""
    return sorted(results, key=lambda r: not is_trusted(r.get("url")))

KEYWORDS = ("geomagnetic", "space weather", "coronal mass", "solar flare",
            "solar storm", "cme", "kp index", "radio blackout")

def relevant(r):
    text = ((r.get("title") or "") + " " + (r.get("content") or "")).lower()
    return any(k in text for k in KEYWORDS)

def strip_boilerplate(text):
    """SWPC pages put navigation text first; the bulletin starts after 'published:'."""
    head, sep, tail = text.partition("published:")
    return tail.strip() if sep else text

def _search(client, errors, **kw):
    try:
        return client.search(**kw).get("results", [])
    except Exception as e:
        errors.append(repr(e))
        return []
    
def get_advisories(query=DEFAULT_QUERY, max_results=5, days=7):
    """News + official-source results, deduped, relevant only, official first."""
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        return {"error": "TAVILY_API_KEY not set", "results": []}
    errors = []
    try:
        client = TavilyClient(api_key=key)
        news = _search(client, errors, query=query, topic="news", days=days, max_results=max_results)
        official = _search(client, errors, query=query + " NOAA SWPC", topic="news", days=14, include_domains=list(TRUSTED), max_results=3)
        seen, merged = set(), []
        for r in official + news:
            if r.get("url") not in seen:
                seen.add(r.get("url"))
                merged.append(r)
        merged = [r for r in merged if relevant(r)]
        results = trim(rank(merged))[:max_results]
        return {"error": "; ".join(errors) or None, "counts": {"news": len(news), "official": len(official), "kept": len(results)}, "results": results}
    except Exception as e:
        return {"error": repr(e), "results": []}

if __name__ == "__main__":
    import json
    print(json.dumps(get_advisories(), indent=2))