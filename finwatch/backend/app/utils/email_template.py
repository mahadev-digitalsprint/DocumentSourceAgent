"""
HTML email template builder for 24-hour change digest.
"""
from datetime import datetime
from typing import List, Dict, Any


def build_email_html(
    company_names: List[str],
    doc_changes: List[Dict[str, Any]],
    page_changes: List[Dict[str, Any]],
    generated_at: datetime,
) -> str:
    """
    Returns styled HTML string for the 24h digest email.
    """
    doc_rows = ""
    for c in doc_changes:
        colour = {"NEW": "#22c55e", "UPDATED": "#f59e0b", "REMOVED": "#ef4444"}.get(c.get("change_type", ""), "#6b7280")
        doc_rows += f"""
        <tr>
            <td>{c.get('company', '')}</td>
            <td><span style="color:{colour};font-weight:bold">{c.get('change_type', '')}</span></td>
            <td style="font-size:12px">{c.get('url', '')[:80]}…</td>
            <td>{c.get('doc_type', '')}</td>
            <td>{c.get('detected_at', '')}</td>
        </tr>"""

    page_rows = ""
    for p in page_changes:
        colour = {"PAGE_ADDED": "#22c55e", "PAGE_DELETED": "#ef4444", "CONTENT_CHANGED": "#f59e0b", "NEW_DOC_LINKED": "#3b82f6"}.get(p.get("change_type", ""), "#6b7280")
        page_rows += f"""
        <tr>
            <td>{p.get('company', '')}</td>
            <td><span style="color:{colour};font-weight:bold">{p.get('change_type', '').replace('_', ' ')}</span></td>
            <td style="font-size:12px">{p.get('page_url', '')[:80]}…</td>
            <td style="font-size:12px">{(p.get('diff_summary', '') or '')[:100]}</td>
            <td>{p.get('detected_at', '')}</td>
        </tr>"""

    return f"""
<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: Arial, sans-serif; background: #f8fafc; color: #1e293b; margin: 0; padding: 20px; }}
  .container {{ max-width: 900px; margin: 0 auto; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
  .header {{ background: #1e3a5f; color: white; padding: 24px 32px; }}
  .header h1 {{ margin: 0; font-size: 22px; }}
  .header p {{ margin: 4px 0 0; opacity: 0.8; font-size: 13px; }}
  .section {{ padding: 24px 32px; border-bottom: 1px solid #e2e8f0; }}
  .section h2 {{ margin: 0 0 16px; font-size: 16px; color: #1e3a5f; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: #1e3a5f; color: white; padding: 8px 12px; text-align: left; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #e2e8f0; }}
  tr:hover {{ background: #f1f5f9; }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 16px; }}
  .stat {{ background: #f1f5f9; border-radius: 6px; padding: 16px; text-align: center; }}
  .stat .num {{ font-size: 28px; font-weight: bold; color: #1e3a5f; }}
  .stat .lbl {{ font-size: 12px; color: #64748b; margin-top: 4px; }}
  .footer {{ padding: 16px 32px; font-size: 12px; color: #94a3b8; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>📊 FinWatch — 24-Hour Change Digest</h1>
    <p>Generated: {generated_at.strftime('%Y-%m-%d %H:%M UTC')} &nbsp;|&nbsp; Companies monitored: {', '.join(company_names)}</p>
  </div>
  <div class="section">
    <h2>Summary</h2>
    <div class="stat-grid">
      <div class="stat"><div class="num">{len([c for c in doc_changes if c.get('change_type')=='NEW'])}</div><div class="lbl">New Docs</div></div>
      <div class="stat"><div class="num">{len([c for c in doc_changes if c.get('change_type')=='UPDATED'])}</div><div class="lbl">Updated Docs</div></div>
      <div class="stat"><div class="num">{len([p for p in page_changes if p.get('change_type')=='PAGE_ADDED'])}</div><div class="lbl">Pages Added</div></div>
      <div class="stat"><div class="num">{len([p for p in page_changes if p.get('change_type')=='PAGE_DELETED'])}</div><div class="lbl">Pages Deleted</div></div>
    </div>
  </div>
  <div class="section">
    <h2>📄 Document Changes</h2>
    <table>
      <tr><th>Company</th><th>Change</th><th>URL</th><th>Type</th><th>Detected At</th></tr>
      {doc_rows if doc_rows else '<tr><td colspan="5" style="text-align:center;color:#94a3b8">No document changes in last 24h</td></tr>'}
    </table>
  </div>
  <div class="section">
    <h2>🌐 Website Page Changes</h2>
    <table>
      <tr><th>Company</th><th>Change</th><th>Page URL</th><th>Summary</th><th>Detected At</th></tr>
      {page_rows if page_rows else '<tr><td colspan="5" style="text-align:center;color:#94a3b8">No page changes in last 24h</td></tr>'}
    </table>
  </div>
  <div class="footer">
    📎 Excel report attached — FinWatch Automated Alert System
  </div>
</div>
</body>
</html>
"""
