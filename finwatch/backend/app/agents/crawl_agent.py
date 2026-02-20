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
import xml.etree.ElementTree as ET
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
USER_AGENT = "Mozilla/5.0 FinWatch/1.0"

# Common TLDs and subdomains to strip when cleaning company names
_STRIP_PREFIXES = re.compile(r'^(www\d*|ir|investors?|investor-relations|corp|corporate)\.', re.I)
_STRIP_TLDS    = re.compile(r'\.(com|in|co\.in|net|org|io|gov|edu|bank|finance|info|biz|us|uk|co\.uk)$', re.I)


def _clean_company_name(raw_name: str, website_url: str = "") -> str:
    """
    Convert a raw company_name into a clean search term.
    Handles cases where users paste a domain instead of a company name:
      'www.icici.bank.in'  → 'icici bank'
      'http://www.tcs.com' → 'tcs'
      'Tata Consultancy'   → 'Tata Consultancy'  (unchanged)
    """
    name = raw_name.strip()

    # If name looks like a URL/domain (contains dots but no spaces)
    if '.' in name and ' ' not in name:
        # Strip protocol
        name = re.sub(r'^https?://', '', name, flags=re.I)
        # Strip path
        name = name.split('/')[0]
        # Strip subdomains like www., ir., investors.
        name = _STRIP_PREFIXES.sub('', name)
        # Strip TLD
        name = _STRIP_TLDS.sub('', name)
        # Convert dots/dashes/underscores to spaces
        name = re.sub(r'[._-]+', ' ', name).strip()

    # If still empty, fall back to extracting from website_url
    if not name and website_url:
        parsed = urlparse(website_url)
        host = parsed.netloc or website_url.split('/')[0]
        host = _STRIP_PREFIXES.sub('', host)
        host = _STRIP_TLDS.sub('', host)
        name = re.sub(r'[._-]+', ' ', host).strip()

    return name or raw_name


def crawl_agent(state: PipelineState) -> dict:
    """LangGraph node — discovers all PDF URLs for the company."""
    raw_name   = state["company_name"]
    website    = state["website_url"]
    clean_name = _clean_company_name(raw_name, website)

    if clean_name != raw_name:
        logger.info(f"[M1-CRAWL] Company name cleaned: '{raw_name}' → '{clean_name}'")
    logger.info(f"[M1-CRAWL] Starting: {clean_name} → {website}")

    all_urls: Set[str] = set()

    # Strategy 1: Firecrawl (deep JS crawl)
    try:
        fc_urls = _strategy_firecrawl(website)
        all_urls.update(fc_urls)
        logger.info(f"[M1-CRAWL][Firecrawl] +{len(fc_urls)} URLs")
    except Exception as e:
        logger.warning(f"[M1-CRAWL][Firecrawl] Failed: {e}")

    # Strategy 2: Tavily semantic search (uses cleaned name + site: hint)
    try:
        tv_urls = _strategy_tavily(clean_name, website)
        all_urls.update(tv_urls)
        logger.info(f"[M1-CRAWL][Tavily] +{len(tv_urls)} URLs")
    except Exception as e:
        logger.warning(f"[M1-CRAWL][Tavily] Failed: {e}")

    # Strategy 3: SEC EDGAR (uses cleaned name)
    try:
        ed_urls = _strategy_edgar(clean_name)
        all_urls.update(ed_urls)
        logger.info(f"[M1-CRAWL][EDGAR] +{len(ed_urls)} URLs")
    except Exception as e:
        logger.warning(f"[M1-CRAWL][EDGAR] Failed: {e}")

    # Strategy 4: Sitemap parsing (fast path for enterprise IR sites)
    try:
        sm_urls = _strategy_sitemap(website)
        all_urls.update(sm_urls)
        logger.info(f"[M1-CRAWL][Sitemap] +{len(sm_urls)} URLs")
    except Exception as e:
        logger.warning(f"[M1-CRAWL][Sitemap] Failed: {e}")

    # Strategy 5: BeautifulSoup recursive crawler
    try:
        bs_urls = _strategy_bs4(website, depth=state.get("crawl_depth", 3))
        all_urls.update(bs_urls)
        logger.info(f"[M1-CRAWL][BS4] +{len(bs_urls)} URLs")
    except Exception as e:
        logger.warning(f"[M1-CRAWL][BS4] Failed: {e}")

    # Strategy 6: Regex PDF scan on raw HTML
    try:
        rx_urls = _strategy_regex(website)
        all_urls.update(rx_urls)
        logger.info(f"[M1-CRAWL][Regex] +{len(rx_urls)} URLs")
    except Exception as e:
        logger.warning(f"[M1-CRAWL][Regex] Failed: {e}")

    filtered = _filter_urls(list(all_urls))
    logger.info(f"[M1-CRAWL] Total unique financial PDFs: {len(filtered)}")
    return {"pdf_urls": filtered, "crawl_errors": [], "company_name_clean": clean_name}


# ─────────────────────────────────────────────────────────────────────────────
# Strategy Implementations
# ─────────────────────────────────────────────────────────────────────────────

def _strategy_firecrawl(url: str) -> List[str]:
    if not settings.firecrawl_api_key:
        return []
    try:
        resp = httpx.post(
            "https://api.firecrawl.dev/v1/crawl",
            headers={"Authorization": f"Bearer {settings.firecrawl_api_key}"},
            json={
                "url": url,
                "limit": MAX_CRAWL_PAGES,
                "scrapeOptions": {"formats": ["links"]},
            },
            timeout=60,
        )
        # Detect insufficient credits (402) or quota errors gracefully
        if resp.status_code == 402:
            logger.warning(
                "[M1-CRAWL][Firecrawl] Insufficient credits — skipping Firecrawl, "
                "using remaining 4 strategies instead."
            )
            return []
        if resp.status_code == 429:
            logger.warning("[M1-CRAWL][Firecrawl] Rate limited — skipping.")
            return []
        resp.raise_for_status()
        data = resp.json()
        # v1 returns data list with each page's links
        found = []
        for item in data.get("data", []):
            for link in item.get("links", []):
                if isinstance(link, str) and _is_probable_pdf_url(link):
                    found.append(_normalize_url(link))
        return [u for u in found if u]
    except httpx.HTTPStatusError as e:
        if "insufficient" in str(e).lower() or "credits" in str(e).lower() or "402" in str(e):
            logger.warning("[M1-CRAWL][Firecrawl] Insufficient credits — skipping.")
        else:
            logger.warning(f"[M1-CRAWL][Firecrawl] HTTP error: {e}")
        return []
    except Exception as e:
        logger.warning(f"[M1-CRAWL][Firecrawl] Failed: {e}")
        return []


def _strategy_tavily(company_name: str, website_url: str = "") -> List[str]:
    if not settings.tavily_api_key:
        return []

    # Build site: hint from website_url for more targeted results
    domain = ""
    if website_url:
        parsed = urlparse(website_url)
        domain = parsed.netloc or ""
        # strip www.
        domain = re.sub(r'^www\.', '', domain)

    site_hint = f"site:{domain}" if domain else ""

    queries = [
        f"{company_name} annual report filetype:pdf {site_hint}".strip(),
        f"{company_name} quarterly results investor relations filetype:pdf",
        f"{company_name} financial statement disclosure pdf",
        f"{company_name} earnings release results pdf",
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
                    "include_domains": [domain] if domain else [],
                },
                timeout=20,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            for r in results:
                url = r.get("url", "")
                if _is_probable_pdf_url(url):
                    n = _normalize_url(url)
                    if n:
                        found.append(n)
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
            r = httpx.get(url, follow_redirects=True, timeout=12, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

            for tag in soup.find_all("a", href=True):
                href = tag.get("href") or ""
                full = _normalize_url(urljoin(base, href))
                if not full:
                    continue
                if _is_probable_pdf_url(full):
                    pdf_links.add(full)
                elif urlparse(full).netloc == base_domain and full not in visited:
                    _crawl(full, current_depth - 1)

            # Embedded PDF links via src/data/object/iframe.
            for tag in soup.find_all(["iframe", "embed", "object"]):
                for attr in ("src", "data"):
                    val = tag.get(attr, "")
                    if not val:
                        continue
                    full = _normalize_url(urljoin(base, val))
                    if full and _is_probable_pdf_url(full):
                        pdf_links.add(full)

        except Exception:
            pass

    _crawl(base_url, depth)
    return list(pdf_links)


def _strategy_regex(url: str) -> List[str]:
    """Scan raw HTML source for .pdf URLs using regex."""
    try:
        r = httpx.get(url, follow_redirects=True, timeout=12, headers={"User-Agent": USER_AGENT})
        matches = PDF_REGEX.findall(r.text)
        return list({u for u in (_normalize_url(m) for m in matches) if u})
    except Exception:
        return []


def _filter_urls(urls: List[str]) -> List[str]:
    """Normalize and deduplicate discovered PDF URLs."""
    seen: Set[str] = set()
    result = []
    for url in urls:
        norm = _normalize_url(url)
        if not norm or not _is_probable_pdf_url(norm):
            continue
        key = hashlib.md5(norm.encode()).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        result.append(norm)
    return result


def _strategy_sitemap(base_url: str) -> List[str]:
    """
    Parse /sitemap.xml and nested sitemap indexes to discover PDF URLs quickly.
    """
    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    candidates = [
        urljoin(root, "/sitemap.xml"),
        urljoin(root, "/sitemap_index.xml"),
    ]

    seen_maps: Set[str] = set()
    queue = list(candidates)
    found: Set[str] = set()

    while queue and len(seen_maps) < 30:
        sm_url = queue.pop(0)
        if sm_url in seen_maps:
            continue
        seen_maps.add(sm_url)
        try:
            r = httpx.get(sm_url, timeout=15, headers={"User-Agent": USER_AGENT})
            if r.status_code >= 400:
                continue
            root_el = ET.fromstring(r.text)
            for loc in root_el.findall(".//{*}loc"):
                loc_url = (loc.text or "").strip()
                if not loc_url:
                    continue
                n = _normalize_url(loc_url)
                if not n:
                    continue
                if n.lower().endswith(".xml"):
                    queue.append(n)
                elif _is_probable_pdf_url(n):
                    found.add(n)
        except Exception:
            continue

    return list(found)


def _normalize_url(url: str) -> str:
    if not isinstance(url, str):
        return ""
    u = url.strip()
    if not u.lower().startswith(("http://", "https://")):
        return ""
    parsed = urlparse(u)
    clean = parsed._replace(fragment="")
    return clean.geturl()


def _is_probable_pdf_url(url: str) -> bool:
    lower = (url or "").lower()
    if not lower:
        return False
    return ".pdf" in lower
