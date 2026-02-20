"""Crawl agent with multi-strategy discovery and domain control."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from app.config import get_settings
from app.database import SessionLocal
from app.models import CrawlDiagnostic
from app.utils.crawl_control import domain_control
from app.utils.http_client import is_blocked_response, request_with_retries
from app.workflow.state import PipelineState

logger = logging.getLogger(__name__)
settings = get_settings()

FINANCIAL_KEYWORDS = [
    "annual",
    "quarter",
    "financial",
    "report",
    "investor",
    "earnings",
    "result",
    "statement",
    "filing",
    "disclosure",
    "presentation",
    "interim",
    "half-year",
    "ipo",
    "prospectus",
]
PDF_REGEX = re.compile(r'https?://[^\s\'"<>]+\.pdf(?:\?[^\s\'"<>]*)?', re.IGNORECASE)
USER_AGENT = "Mozilla/5.0 FinWatch/2.1"

_STRIP_PREFIXES = re.compile(r"^(www\d*|ir|investors?|investor-relations|corp|corporate)\.", re.I)
_STRIP_TLDS = re.compile(r"\.(com|in|co\.in|net|org|io|gov|edu|bank|finance|info|biz|us|uk|co\.uk)$", re.I)


@dataclass
class CrawlRuntime:
    company_id: int
    diagnostics: List[dict] = field(default_factory=list)


def crawl_agent(state: PipelineState) -> dict:
    company_name = state["company_name"]
    website = state["website_url"]
    clean_name = _clean_company_name(company_name, website)
    depth = int(state.get("crawl_depth", 3) or 3)
    runtime = CrawlRuntime(company_id=int(state["company_id"]))

    mode = (settings.crawler_mode or "auto").strip().lower()
    if mode not in {"auto", "local", "api"}:
        mode = "auto"

    all_urls: Set[str] = set()
    source_meta_by_url: Dict[str, dict] = {}
    crawl_errors: List[str] = []

    local_first = [
        ("Sitemap", lambda: _strategy_sitemap(website, runtime)),
        ("Crawl4AI", lambda: _strategy_crawl4ai(website, depth=depth, runtime=runtime)),
        ("BS4", lambda: _strategy_bs4(website, depth=depth, runtime=runtime)),
        ("Regex", lambda: _strategy_regex(website, runtime)),
    ]
    api_first = [
        ("Firecrawl", lambda: _strategy_firecrawl(website, runtime)),
        ("Tavily", lambda: _strategy_tavily(clean_name, website, runtime)),
        ("EDGAR", lambda: _strategy_edgar(clean_name, runtime)),
    ]

    strategies = local_first if mode == "local" else api_first + local_first if mode == "api" else local_first + api_first

    logger.info("[CRAWL] Start %s | mode=%s | site=%s", clean_name, mode, website)
    for strategy_name, strategy_func in strategies:
        try:
            urls = strategy_func()
            all_urls.update(urls)
            for url in urls:
                normalized = _normalize_url(url)
                if not normalized:
                    continue
                source_meta_by_url[normalized] = {
                    "discovery_strategy": strategy_name,
                    "source_domain": urlparse(normalized).netloc.lower(),
                    "source_type": _source_type_for(strategy_name, normalized),
                }
            logger.info("[CRAWL] %s: +%s urls", strategy_name, len(urls))
        except Exception as exc:
            logger.warning("[CRAWL] %s failed: %s", strategy_name, exc)
            crawl_errors.append(f"{strategy_name}: {exc}")

    filtered = _filter_urls(list(all_urls))
    filtered_sources = {url: source_meta_by_url[url] for url in filtered if url in source_meta_by_url}
    _persist_diagnostics(runtime)
    logger.info("[CRAWL] Finished %s | discovered=%s", clean_name, len(filtered))
    return {
        "pdf_urls": filtered,
        "pdf_sources": filtered_sources,
        "crawl_errors": crawl_errors,
        "company_name_clean": clean_name,
    }


def _clean_company_name(raw_name: str, website_url: str = "") -> str:
    name = (raw_name or "").strip()
    if "." in name and " " not in name:
        name = re.sub(r"^https?://", "", name, flags=re.I).split("/")[0]
        name = _STRIP_PREFIXES.sub("", name)
        name = _STRIP_TLDS.sub("", name)
        name = re.sub(r"[._-]+", " ", name).strip()
    if not name and website_url:
        host = (urlparse(website_url).netloc or website_url.split("/")[0]).strip()
        host = _STRIP_PREFIXES.sub("", host)
        host = _STRIP_TLDS.sub("", host)
        name = re.sub(r"[._-]+", " ", host).strip()
    return name or raw_name


def _strategy_firecrawl(url: str, runtime: CrawlRuntime) -> List[str]:
    if not settings.firecrawl_api_key:
        return []
    response = _guarded_request(
        "POST",
        "https://api.firecrawl.dev/v1/crawl",
        "Firecrawl",
        runtime,
        headers={"Authorization": f"Bearer {settings.firecrawl_api_key}"},
        json={"url": url, "limit": settings.max_crawl_pages, "scrapeOptions": {"formats": ["links"]}},
        timeout=60,
    )
    if response is None or response.status_code in {402, 429}:
        return []
    response.raise_for_status()

    discovered = []
    for item in response.json().get("data", []):
        for link in item.get("links", []):
            if isinstance(link, str) and _is_probable_pdf_url(link):
                normalized = _normalize_url(link)
                if normalized:
                    discovered.append(normalized)
    return discovered


def _strategy_tavily(company_name: str, website_url: str, runtime: CrawlRuntime) -> List[str]:
    if not settings.tavily_api_key:
        return []

    domain = re.sub(r"^www\.", "", urlparse(website_url).netloc or "")
    site_hint = f"site:{domain}" if domain else ""
    queries = [
        f"{company_name} annual report filetype:pdf {site_hint}".strip(),
        f"{company_name} quarterly results investor relations filetype:pdf",
        f"{company_name} financial statement disclosure pdf",
        f"{company_name} earnings release results pdf",
    ]
    found = []
    for query in queries:
        response = _guarded_request(
            "POST",
            "https://api.tavily.com/search",
            "Tavily",
            runtime,
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": 15,
                "include_domains": [domain] if domain else [],
            },
            timeout=20,
        )
        if response is None:
            continue
        try:
            response.raise_for_status()
        except Exception:
            continue
        for item in response.json().get("results", []):
            candidate = item.get("url", "")
            if _is_probable_pdf_url(candidate):
                normalized = _normalize_url(candidate)
                if normalized:
                    found.append(normalized)
    return found


def _strategy_edgar(company_name: str, runtime: CrawlRuntime) -> List[str]:
    query = company_name.replace(" ", "+")
    response = _guarded_request(
        "GET",
        f"https://efts.sec.gov/LATEST/search-index?q=%22{query}%22&dateRange=custom&startdt=2020-01-01&forms=10-K,10-Q,20-F",
        "EDGAR",
        runtime,
        timeout=15,
        headers={"User-Agent": "FinWatch contact@finwatch.local"},
    )
    if response is None:
        return []
    try:
        response.raise_for_status()
    except Exception:
        return []
    return []


def _strategy_sitemap(base_url: str, runtime: CrawlRuntime) -> List[str]:
    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    queue = [urljoin(root, "/sitemap.xml"), urljoin(root, "/sitemap_index.xml")]
    seen: Set[str] = set()
    found: Set[str] = set()

    while queue and len(seen) < 30:
        sitemap_url = queue.pop(0)
        if sitemap_url in seen:
            continue
        seen.add(sitemap_url)
        response = _guarded_request("GET", sitemap_url, "Sitemap", runtime, timeout=15, headers={"User-Agent": USER_AGENT})
        if response is None or response.status_code >= 400 or is_blocked_response(response):
            continue
        try:
            root_el = ET.fromstring(response.text)
        except Exception:
            continue
        for loc in root_el.findall(".//{*}loc"):
            normalized = _normalize_url((loc.text or "").strip())
            if not normalized:
                continue
            if normalized.lower().endswith(".xml"):
                queue.append(normalized)
            elif _is_probable_pdf_url(normalized):
                found.add(normalized)
    return list(found)


def _strategy_bs4(base_url: str, depth: int, runtime: CrawlRuntime) -> List[str]:
    visited: Set[str] = set()
    pdf_links: Set[str] = set()
    base_domain = urlparse(base_url).netloc

    def crawl(url: str, current_depth: int):
        if current_depth <= 0 or url in visited or len(visited) >= settings.max_crawl_pages:
            return
        visited.add(url)
        response = _guarded_request(
            "GET",
            url,
            "BS4",
            runtime,
            follow_redirects=True,
            timeout=12,
            headers={"User-Agent": USER_AGENT},
        )
        if response is None:
            return
        try:
            response.raise_for_status()
        except Exception:
            return
        if is_blocked_response(response):
            return
        soup = BeautifulSoup(response.text, "html.parser")
        page_base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

        for anchor in soup.find_all("a", href=True):
            full = _normalize_url(urljoin(page_base, anchor.get("href") or ""))
            if not full:
                continue
            if _is_probable_pdf_url(full):
                pdf_links.add(full)
            elif urlparse(full).netloc == base_domain:
                crawl(full, current_depth - 1)

        for embed in soup.find_all(["iframe", "embed", "object"]):
            for attr in ("src", "data"):
                full = _normalize_url(urljoin(page_base, embed.get(attr, "")))
                if full and _is_probable_pdf_url(full):
                    pdf_links.add(full)

    crawl(base_url, depth)
    return list(pdf_links)


def _strategy_regex(url: str, runtime: CrawlRuntime) -> List[str]:
    response = _guarded_request(
        "GET",
        url,
        "Regex",
        runtime,
        follow_redirects=True,
        timeout=12,
        headers={"User-Agent": USER_AGENT},
    )
    if response is None or is_blocked_response(response):
        return []
    matches = PDF_REGEX.findall(response.text)
    return list({normalized for normalized in (_normalize_url(m) for m in matches) if normalized})


def _strategy_crawl4ai(base_url: str, depth: int, runtime: CrawlRuntime) -> List[str]:
    if not settings.enable_crawl4ai:
        return []
    try:
        from crawl4ai import AsyncWebCrawler
    except Exception:
        return []

    async def run_crawl() -> List[str]:
        found: Set[str] = set()
        visited: Set[str] = set()
        queue: List[tuple[str, int]] = [(base_url, 0)]
        base_domain = urlparse(base_url).netloc

        async with AsyncWebCrawler() as crawler:
            while queue and len(visited) < settings.max_crawl_pages:
                url, d = queue.pop(0)
                if url in visited:
                    continue
                visited.add(url)
                domain = urlparse(url).netloc.lower()
                if domain_control.is_blocked(domain):
                    continue
                domain_control.wait_turn(domain, settings.crawl_domain_delay_seconds)

                started = time.perf_counter()
                try:
                    result = await crawler.arun(url=url)
                    _record_diag(runtime, "Crawl4AI", url, 200, False, None, int((time.perf_counter() - started) * 1000))
                except Exception as exc:
                    _record_diag(runtime, "Crawl4AI", url, None, False, str(exc), int((time.perf_counter() - started) * 1000))
                    continue

                for link in _extract_crawl4ai_links(result, url):
                    if _is_probable_pdf_url(link):
                        normalized = _normalize_url(link)
                        if normalized:
                            found.add(normalized)
                        continue
                    if d + 1 < depth and urlparse(link).netloc == base_domain and link not in visited:
                        queue.append((link, d + 1))
        return list(found)

    try:
        return asyncio.run(run_crawl())
    except Exception:
        return []


def _guarded_request(method: str, url: str, strategy: str, runtime: CrawlRuntime, **kwargs):
    domain = urlparse(url).netloc.lower()
    if domain_control.is_blocked(domain):
        _record_diag(runtime, strategy, url, None, True, "domain cooldown active", 0)
        return None

    domain_control.wait_turn(domain, settings.crawl_domain_delay_seconds)
    started = time.perf_counter()
    try:
        response = request_with_retries(method, url, **kwargs)
    except Exception as exc:
        _record_diag(runtime, strategy, url, None, False, str(exc), int((time.perf_counter() - started) * 1000))
        return None

    blocked = is_blocked_response(response)
    if blocked:
        domain_control.mark_blocked(domain, settings.crawl_block_cooldown_seconds)
    _record_diag(
        runtime,
        strategy,
        url,
        response.status_code,
        blocked,
        None,
        int((time.perf_counter() - started) * 1000),
    )
    return response


def _record_diag(runtime: CrawlRuntime, strategy: str, url: str, status_code: int | None, blocked: bool, error: str | None, duration_ms: int):
    runtime.diagnostics.append(
        {
            "company_id": runtime.company_id,
            "domain": urlparse(url).netloc.lower() if url else None,
            "strategy": strategy,
            "page_url": url,
            "status_code": status_code,
            "blocked": blocked,
            "error_message": (error or "")[:1000] if error else None,
            "retry_count": 0,
            "duration_ms": duration_ms,
        }
    )


def _persist_diagnostics(runtime: CrawlRuntime) -> None:
    if not runtime.diagnostics:
        return
    db = SessionLocal()
    try:
        for item in runtime.diagnostics[:1000]:
            db.add(CrawlDiagnostic(**item))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _extract_crawl4ai_links(result: Any, base_url: str) -> List[str]:
    candidates: List[str] = []
    links = getattr(result, "links", None)

    if isinstance(links, dict):
        for key in ("internal", "external", "all"):
            entries = links.get(key, [])
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, str):
                    candidates.append(entry)
                elif isinstance(entry, dict):
                    candidates.append(entry.get("href") or entry.get("url") or "")
    elif isinstance(links, list):
        for entry in links:
            if isinstance(entry, str):
                candidates.append(entry)
            elif isinstance(entry, dict):
                candidates.append(entry.get("href") or entry.get("url") or "")

    html_blob = " ".join(str(part) for part in (getattr(result, "html", ""), getattr(result, "cleaned_html", ""), getattr(result, "markdown", "")) if part)
    if html_blob:
        for matched in PDF_REGEX.findall(html_blob):
            candidates.append(matched)
        try:
            soup = BeautifulSoup(html_blob, "html.parser")
            for anchor in soup.find_all("a", href=True):
                candidates.append(anchor.get("href") or "")
        except Exception:
            pass

    normalized = []
    for candidate in candidates:
        full = _normalize_url(urljoin(base_url, candidate))
        if full:
            normalized.append(full)
    return list(dict.fromkeys(normalized))


def _filter_urls(urls: List[str]) -> List[str]:
    seen: Set[str] = set()
    result = []
    for url in urls:
        normalized = _normalize_url(url)
        if not normalized or not _is_probable_pdf_url(normalized):
            continue
        digest = hashlib.md5(normalized.encode()).hexdigest()
        if digest in seen:
            continue
        lower = normalized.lower()
        if not any(keyword in lower for keyword in FINANCIAL_KEYWORDS):
            if "report" not in lower and "results" not in lower:
                continue
        seen.add(digest)
        result.append(normalized)
    return result


def _normalize_url(url: str) -> str:
    if not isinstance(url, str):
        return ""
    value = url.strip()
    if not value.lower().startswith(("http://", "https://")):
        return ""
    parsed = urlparse(value)
    filtered_query = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=True):
        lk = key.lower()
        if lk.startswith("utm_") or lk in {"session", "sid", "phpsessid"}:
            continue
        filtered_query.append((key, val))
    query = urlencode(filtered_query, doseq=True)
    cleaned_path = re.sub(r"/+$", "", parsed.path or "")
    normalized = parsed._replace(query=query, fragment="", path=cleaned_path)
    return urlunparse(normalized)


def _is_probable_pdf_url(url: str) -> bool:
    return ".pdf" in (url or "").lower()


def _source_type_for(strategy_name: str, url: str) -> str:
    strategy = (strategy_name or "").strip().upper()
    domain = (urlparse(url).netloc or "").lower()
    if strategy in {"FIRECRAWL", "TAVILY"}:
        return "SEARCH_API"
    if strategy == "EDGAR" or "sec.gov" in domain:
        return "REGULATORY"
    return "WEBSITE"
