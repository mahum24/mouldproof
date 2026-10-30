"""Live evidence about the landlord's track record via Tavily."""
import os
from concurrent.futures import ThreadPoolExecutor

from tavily import TavilyClient

_client = None


def client() -> TavilyClient:
    global _client
    if _client is None:
        _client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    return _client


def landlord_record(landlord: str) -> dict:
    """Housing Ombudsman findings and recent news about a landlord's handling of damp and mould."""
    queries = {
        "ombudsman": dict(query=f"{landlord} damp mould maladministration", include_domains=["housing-ombudsman.org.uk"],
                          search_depth="advanced", max_results=4),
        "regulator": dict(query=f"{landlord} regulatory judgement consumer standards",
                          include_domains=["gov.uk"], max_results=3),
        "news": dict(query=f'"{landlord}" damp mould tenants', topic="news", days=730, max_results=4,
                     exclude_domains=["facebook.com", "instagram.com", "x.com", "tiktok.com"]),
    }

    def run(item):
        key, kw = item
        try:
            return key, [_trim(r) for r in client().search(**kw).get("results", [])]
        except Exception:
            return key, []

    with ThreadPoolExecutor(3) as pool:
        return dict(pool.map(run, queries.items()))


def _trim(r: dict) -> dict:
    return {"title": r.get("title", ""), "url": r.get("url", ""), "content": (r.get("content") or "")[:1200]}
