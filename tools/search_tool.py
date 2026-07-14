"""search_tool.py — DuckDuckGo web search + URL scraper (free, no API key)"""
from duckduckgo_search import DDGS

class WebSearchTool:
    name = "web_search"
    description = "Search internet. INPUT: query. OUTPUT: top 5 results with title, URL, content."
    def _run(self, query: str) -> str:
        try:
            with DDGS() as ddgs:
                hits = list(ddgs.text(query, max_results=5))
            if not hits: return "No results for: " + query
            return "\n\n".join(
                f"[{i}] {r.get('title','')}\n    URL: {r.get('href','')}\n    {r.get('body','')[:600]}"
                for i, r in enumerate(hits, 1)
            )
        except Exception as e:
            return f"Search error: {str(e)}"

class URLScraperTool:
    name = "scrape_url"
    description = "Read full content of any webpage. INPUT: URL string. OUTPUT: full page text."
    def _run(self, url: str) -> str:
        try:
            import requests
            from bs4 import BeautifulSoup
            resp = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script","style","nav","footer"]): tag.decompose()
            text = "\n".join(l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip())
            return f"[PAGE: {url}]\n\n{text[:6000]}"
        except Exception as e:
            return f"Scrape error: {str(e)}"
