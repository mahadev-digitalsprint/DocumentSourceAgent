"""
LangGraph Graph — 8-node stateful pipeline with conditional routing.

Flow:
  crawl_agent → webwatch_agent → download_agent → classify_agent
  → parse_agent → extract_agent → excel_agent → email_agent → END

Conditional edges:
  - After crawl: skip rest if 0 PDFs found AND no page changes
  - Before email: skip if no changes (has_changes=False)
"""
import logging
from langgraph.graph import StateGraph, END

from app.workflow.state import PipelineState
from app.agents.crawl_agent import crawl_agent
from app.agents.webwatch_agent import webwatch_agent
from app.agents.download_agent import download_agent
from app.agents.classify_agent import classify_agent
from app.agents.parse_agent import parse_agent
from app.agents.extract_agent import extract_agent
from app.agents.excel_agent import excel_agent
from app.agents.email_agent import email_agent

logger = logging.getLogger(__name__)


def should_continue_after_crawl(state: PipelineState) -> str:
    """Skip the full pipeline if nothing was discovered."""
    if state.get("pdf_urls") or state.get("page_changes"):
        return "webwatch"
    logger.info("[GRAPH] No URLs or page changes — skipping pipeline")
    return "end"


def should_send_email(state: PipelineState) -> str:
    """Skip email if nothing changed."""
    return "email" if state.get("has_changes") else "end"


def _update_has_changes(state: PipelineState) -> dict:
    """
    After download: set has_changes = True if any doc is NEW/UPDATED
    or any page changes were recorded.
    """
    doc_changed = any(
        d.get("status") in ("NEW", "UPDATED")
        for d in state.get("downloaded_docs", [])
    )
    has = doc_changed or len(state.get("page_changes", [])) > 0
    return {"has_changes": has}


def build_graph() -> StateGraph:
    g = StateGraph(PipelineState)

    # ── Register nodes ──────────────────────────────────────────────────
    g.add_node("crawl",        crawl_agent)
    g.add_node("webwatch",     webwatch_agent)
    g.add_node("download",     download_agent)
    g.add_node("update_flags", _update_has_changes)
    g.add_node("classify",     classify_agent)
    g.add_node("parse",        parse_agent)
    g.add_node("extract",      extract_agent)
    g.add_node("excel",        excel_agent)
    g.add_node("email",        email_agent)

    # ── Entry point ─────────────────────────────────────────────────────
    g.set_entry_point("crawl")

    # ── Edges ───────────────────────────────────────────────────────────
    g.add_conditional_edges(
        "crawl",
        should_continue_after_crawl,
        {"webwatch": "webwatch", "end": END},
    )
    g.add_edge("webwatch",     "download")
    g.add_edge("download",     "update_flags")
    g.add_edge("update_flags", "classify")
    g.add_edge("classify",     "parse")
    g.add_edge("parse",        "extract")
    g.add_edge("extract",      "excel")
    g.add_conditional_edges(
        "excel",
        should_send_email,
        {"email": "email", "end": END},
    )
    g.add_edge("email", END)

    return g.compile()


# Singleton compiled graph
pipeline_graph = build_graph()
