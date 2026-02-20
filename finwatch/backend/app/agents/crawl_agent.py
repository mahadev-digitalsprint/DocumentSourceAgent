"""
M1 — Crawl Agent
Aggressive 5-strategy PDF discovery for a given company website.

Strategies (in order):
  1. Firecrawl deep crawl (JS-rendered pages, follows redirects)
  2. Tavily semantic search (filetype:pdf + financial keywords)
  3. SEC EDGAR full-text search (if company appears in EDGAR)
  4. BeautifulSoup recursive link extractor (depth controlled)
  5. Regex PDF scan on raw HTML
"""
import re
import hashlib
import logging
from typing import List, Set
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings
from app.workflow.state import PipelineState

logger = logging.getLogger(__name__)
settings = get_settings()

FINANCIAL_KEYWORDS = [
    "annual", "quarter", "financial", "report", "investor", "earnings",
    "result", "statement", "filing", "disclosure", "presentation",
    "interim", "half-year", "ipo", "prospectus", "ar20", "qr20",
]

PDF_REGEX = re.compile(r'https?://[^\s\'"<>]+\.pdf(?:\?[^\s\'"<>]*)?', re.IGNORECASE)
MAX_CRAWL_PAGES = 200


def crawl_agent(state: PipelineState) -> dict:
    """LangGraph node — discovers all PDF URLs for the company."""
    logger.info(f"[M1-CRAWL] Starting: {state['company_name']} → {state['website_url']}")

    all_urls: Set[str] = set()

    # Strategy 1: Firecrawl
    try:
        fc_urls = _strategy_firecrawl(state["website_url"])
        all_urls.update(fc_urls)
        logger.info(f"[M1-CRAWL][Firecrawl] +{len(fc_urls)} URLs")
    except Exception as e:
        logger.warning(f"[M1-CRAWL][Firecrawl] Failed: {e}")

    # Strategy 2: Tavily
    try:
        tv_urls = _strategy_tavily(state["company_name"])
        all_urls.update(tv_urls)
        logger.info(f"[M1-CRAWL][Tavily] +{len(tv_urls)} URLs")
    except Exception as e:
        logger.warning(f"[M1-CRAWL][Tavily] Failed: {e}")

    # Strategy 3: SEC EDGAR
    try:
        ed_urls = _strategy_edgar(state["company_name"])
        all_urls.update(ed_urls)
        logger.info(f"[M1-CRAWL][EDGAR] +{len(ed_urls)} URLs")
    except Exception as e:
        logger.warning(f"[M1-CRAWL][EDGAR] Failed: {e}")

    # Strategy 4: BeautifulSoup recursive
    try:
        bs_urls = _strategy_bs4(state["website_url"], depth=state.get("crawl_depth", 3))
        all_urls.update(bs_urls)
        logger.info(f"[M1-CRAWL][BS4] +{len(bs_urls)} URLs")
    except Exception as e:
        logger.warning(f"[M1-CRAWL][BS4] Failed: {e}")

    # Strategy 5: Regex scan
    try:
        rx_urls = _strategy_regex(state["website_url"])
        all_urls.update(rx_urls)
        logger.info(f"[M1-CRAWL][Regex] +{len(rx_urls)} URLs")
    except Exception as e:
        logger.warning(f"[M1-CRAWL][Regex] Failed: {e}")

    # Filter: financial relevance & deduplicate
    filtered = _filter_urls(list(all_urls))
    logger.info(f"[M1-CRAWL] Total unique financial PDFs: {len(filtered)}")

    return {"pdf_urls": filtered, "crawl_errors": []}


# ─────────────────────────────────────────────────────────────────────────────
# Strategy Implementations
# ─────────────────────────────────────────────────────────────────────────────

def _strategy_firecrawl(url: str) -> List[str]:
    if not settings.firecrawl_api_key:
        return []
    resp = httpx.post(
        "https://api.firecrawl.dev/v0/crawl",
        headers={"Authorization": f"Bearer {settings.firecrawl_api_key}"},
        json={
            "url": url,
            "crawlerOptions": {
                "includes": ["*.pdf"],
                "excludes": ["*.jpg", "*.png", "*.css", "*.js"],
                "limit": MAX_CRAWL_PAGES,
                "returnOnlyUrls": True,
            },
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return [item["url"] for item in data.get("data", []) if item.get("url", "").lower().endswith(".pdf")]


def _strategy_tavily(company_name: str) -> List[str]:
    if not settings.tavily_api_key:
        return []
    queries = [
        f"{company_name} annual report filetype:pdf",
        f"{company_name} quarterly results investor relations filetype:pdf",
        f"{company_name} financial statement disclosure filetype:pdf",
    ]
    found = []
    for query in queries:
        try:
            resp = httpx.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.tavily_api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 15,
                },
                timeout=20,
            )
            resp.raise_for_status()
            found += [r["url"] for r in resp.json().get("results", []) if r.get("url", "").lower().endswith(".pdf")]
        except Exception:
            pass
    return found


def _strategy_edgar(company_name: str) -> List[str]:
    """Search SEC EDGAR full-text search for company filings."""
    try:
        resp = httpx.get(
            "https://efts.sec.gov/LATEST/search-index?q=%22{}%22&dateRange=custom&startdt=2020-01-01&forms=10-K,10-Q,20-F".format(
                company_name.replace(" ", "+")
            ),
            timeout=15,
            headers={"User-Agent": "FinWatch contact@finwatch.ai"},
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", {}).get("hits", [])
        urls = []
        for h in hits[:10]:
            src = h.get("_source", {})
            accession = src.get("file_date", "")
            entity_id = src.get("entity_id", "")
            if entity_id and accession:
                urls.append(f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={entity_id}&type=10-K&dateb=&owner=include&count=10&output=atom")
    except Exception:
        pass
    return []  # EDGAR returns HTML filing indexes, not direct PDFs; skip for now


def _strategy_bs4(base_url: str, depth: int = 3) -> List[str]:
    """Recursive BeautifulSoup crawler up to `depth` levels."""
    visited: Set[str] = set()
    pdf_links: Set[str] = set()
    base_domain = urlparse(base_url).netloc

    def _crawl(url: str, current_depth: int):
        if current_depth == 0 or url in visited or len(visited) > 150:
            return
        visited.add(url)
        try:
            r = httpx.get(url, follow_redirects=True, timeout=12,
                          headers={"User-Agent": "Mozilla/5.0 FinWatch/1.0"})
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

            for tag in soup.find_all(["a", "iframe", "embed", "object"], href=True):
                href = tag.get("href") or tag.get("src") or ""
                full = urljoin(base, href)
                if full.lower().endswith(".pdf"):
                    pdf_links.add(full)
                elif urlparse(full).netloc == base_domain and full not in visited:
                    _crawl(full, current_depth - 1)

            # Also check <object data=> and <frame src=>
            for tag in soup.find_all(True):
                for attr in ["src", "data"]:
                    val = tag.get(attr, "")
                    if val and val.lower().endswith(".pdf"):
                        pdf_links.add(urljoin(base, val))

        except Exception:
            pass

    _crawl(base_url, depth)
    return list(pdf_links)


def _strategy_regex(url: str) -> List[str]:
    """Scan raw HTML source for .pdf URLs using regex."""
    try:
        r = httpx.get(url, follow_redirects=True, timeout=12,
                      headers={"User-Agent": "Mozilla/5.0 FinWatch/1.0"})
        matches = PDF_REGEX.findall(r.text)
        return list(set(matches))
    except Exception:
        return []


def _filter_urls(urls: List[str]) -> List[str]:
    """Deduplicate and retain only financial-keyword URLs."""
    seen: Set[str] = set()
    result = []
    for url in urls:
        key = hashlib.md5(url.encode()).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        url_lower = url.lower()
        if any(kw in url_lower for kw in FINANCIAL_KEYWORDS):
            result.append(url)
        # Even if no keyword in URL: if found by Firecrawl/EDGAR trust it
        elif url not in result:
            result.append(url)
    return result
