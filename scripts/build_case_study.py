import html
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT_FILES = [ROOT / "case_study.html", ROOT / "index.html"]


def load(name):
    return json.load(open(DATA / name, encoding="utf-8"))


def esc(value):
    return html.escape("" if value is None else str(value), quote=True)


def href(value):
    raw = str(value or "").strip()
    if not raw:
        return "#"
    token = raw.split()[0].strip("()")
    if token.startswith(("http://", "https://")):
        return token
    if "." in token:
        return f"https://{token}"
    return "#"


def normalize_auth(values):
    labels = []
    for value in values or []:
        low = str(value).lower()
        if "oauth" in low:
            label = "OAuth2"
        elif "api_key" in low or "api key" in low or "apikey" in low:
            label = "API key"
        elif "basic" in low:
            label = "Basic"
        elif "token" in low or "bearer" in low:
            label = "Token"
        elif "none" in low:
            label = "None"
        else:
            label = "Other / unclear"
        if label not in labels:
            labels.append(label)
    return labels or ["Other / unclear"]


def catalog_row(row):
    auth = normalize_auth(row.get("auth_schemes"))
    actions = row.get("tool_count", 0)
    return {
        "number": row["number"],
        "app": row["app"],
        "category": row["category_given"],
        "what": row.get("description", ""),
        "auth": ", ".join(auth),
        "access": "Existing Composio toolkit",
        "api": f"Composio toolkit, {actions} actions",
        "verdict": "Buildable now",
        "blocker": "",
        "evidence": row.get("evidence_url", ""),
        "source": "Catalog match",
        "confidence": row.get("match_confidence", "catalog"),
        "buildable": True,
    }


def research_row(row):
    manual = row.get("layer") == 3
    return {
        "number": row["number"],
        "app": row["app"],
        "category": row["category_given"],
        "what": row.get("category", ""),
        "auth": ", ".join(normalize_auth(row.get("auth_methods"))),
        "access": row.get("access", "unclear").replace("_", " "),
        "api": row.get("api_surface", ""),
        "verdict": "Buildable now" if row.get("buildable_today") else "Blocked for now",
        "blocker": row.get("blocker") or "",
        "evidence": row.get("evidence_url", ""),
        "source": "Manual check" if manual else "Agent extract",
        "confidence": row.get("confidence", ""),
        "buildable": bool(row.get("buildable_today")),
    }


def pct(n, d):
    return f"{round(n / d * 100)}%" if d else "0%"


def bar(label, value, total):
    width = max(2, round(value / total * 100)) if total else 0
    return f"""
      <div class="bar">
        <span class="bar-label">{esc(label)}</span>
        <span class="bar-track"><i style="width:{width}%"></i></span>
        <span class="bar-value">{value}</span>
      </div>"""


def badge(label):
    safe = label.lower().replace(" ", "-").replace("/", "")
    return f'<span class="badge {esc(safe)}">{esc(label)}</span>'


def main():
    layer1 = load("layer1_results.json")
    layer2 = load("layer2_results.json")
    manual = load("manual_research_results.json")

    rows = []
    rows.extend(catalog_row(r) for r in layer1 if r.get("composio_toolkit_found"))
    rows.extend(research_row(r) for r in layer2)
    rows.extend(research_row(r) for r in manual)
    rows.sort(key=lambda r: r["number"])

    resolved = len(rows)
    buildable = [r for r in rows if r["buildable"]]
    blocked = [r for r in rows if not r["buildable"]]
    source_counts = Counter(r["source"] for r in rows)

    auth_counts = Counter()
    access_counts = Counter(r["access"] for r in rows)
    category_counts = Counter(r["category"] for r in rows)
    category_buildable = defaultdict(int)
    for row in rows:
        for auth in row["auth"].split(", "):
            auth_counts[auth] += 1
        if row["buildable"]:
            category_buildable[row["category"]] += 1

    top_blockers = Counter()
    for row in blocked:
        text = row["blocker"].lower()
        if "partner" in text or "gated" in text or "outreach" in text or "licensing" in text:
            top_blockers["Partner / sales gate"] += 1
        elif "public api" in text or "documentation" in text or "docs" in text:
            top_blockers["No clear public docs"] += 1
        elif "access" in text or "approval" in text:
            top_blockers["Credential approval"] += 1
        else:
            top_blockers["Product-specific ambiguity"] += 1

    category_html = "\n".join(
        f"""
        <tr>
          <td>{esc(category)}</td>
          <td>{count}</td>
          <td>{category_buildable[category]}</td>
          <td>{pct(category_buildable[category], count)}</td>
        </tr>"""
        for category, count in sorted(category_counts.items())
    )

    table_html = "\n".join(
        f"""
        <tr>
          <td>{row['number']}</td>
          <td><strong>{esc(row['app'])}</strong><small>{esc(row['category'])}</small></td>
          <td>{esc(row['what'])}</td>
          <td>{esc(row['auth'])}</td>
          <td>{esc(row['access'])}</td>
          <td>{esc(row['api'])}</td>
          <td>{badge(row['verdict'])}</td>
          <td>{esc(row['blocker'])}</td>
          <td><a href="{esc(href(row['evidence']))}">{esc(row['evidence'])}</a></td>
          <td>{esc(row['source'])}<small>{esc(row['confidence'])}</small></td>
        </tr>"""
        for row in rows
    )

    auth_bars = "\n".join(bar(k, v, resolved) for k, v in auth_counts.most_common())
    access_bars = "\n".join(bar(k, v, resolved) for k, v in access_counts.most_common())
    blocker_bars = "\n".join(bar(k, v, len(blocked)) for k, v in top_blockers.most_common())

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Composio 100-App Research Agent</title>
  <style>
    :root {{
      --paper: #fbfaf7;
      --ink: #191817;
      --muted: #66625c;
      --line: #ded9cf;
      --panel: #ffffff;
      --blue: #2454a6;
      --green: #126b5f;
      --red: #9f3a38;
      --amber: #9a5a12;
      --soft: #f1eee7;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font: 15px/1.55 ui-sans-serif, system-ui, -apple-system, Segoe UI, Arial, sans-serif;
    }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 42px 22px 64px; }}
    header {{ border-bottom: 1px solid var(--line); padding-bottom: 28px; margin-bottom: 26px; }}
    h1 {{ max-width: 950px; font-size: clamp(34px, 5vw, 58px); line-height: 1.02; margin: 0 0 16px; letter-spacing: 0; }}
    h2 {{ font-size: 22px; margin: 34px 0 12px; }}
    h3 {{ font-size: 16px; margin: 0 0 8px; }}
    p {{ margin: 0 0 12px; color: var(--muted); }}
    a {{ color: var(--blue); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    code {{ background: var(--soft); border: 1px solid var(--line); padding: 2px 5px; border-radius: 5px; }}
    .eyebrow {{ color: var(--muted); font-size: 13px; margin-bottom: 12px; }}
    .lede {{ max-width: 870px; color: #33312d; font-size: 18px; }}
    .grid {{ display: grid; gap: 12px; }}
    .metrics {{ grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 22px 0; }}
    .two {{ grid-template-columns: 1fr 1fr; }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    .metric b {{ display: block; font-size: 30px; line-height: 1; margin-bottom: 6px; }}
    .metric span, small {{ color: var(--muted); font-size: 12px; }}
    .findings {{ margin: 16px 0 4px; padding-left: 22px; max-width: 930px; }}
    .findings li {{ margin: 9px 0; }}
    .pill-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }}
    .pill {{ border: 1px solid var(--line); border-radius: 999px; padding: 4px 9px; background: #fff; color: #333; font-size: 13px; }}
    .method p {{ border-left: 2px solid var(--line); padding-left: 12px; }}
    .bar {{ display: grid; grid-template-columns: 160px 1fr 42px; gap: 10px; align-items: center; margin: 8px 0; }}
    .bar-label {{ color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .bar-track {{ display: block; height: 10px; border-radius: 999px; background: var(--soft); overflow: hidden; }}
    .bar-track i {{ display: block; height: 100%; background: var(--blue); }}
    .bar-value {{ color: var(--muted); text-align: right; }}
    .note {{ border-left: 4px solid var(--amber); background: #fff8ea; padding: 12px 14px; border-radius: 6px; margin-bottom: 12px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid var(--line); }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 9px 10px; text-align: left; vertical-align: top; }}
    th {{ position: sticky; top: 0; z-index: 1; background: #eee9df; color: #504b45; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    td {{ font-size: 13px; }}
    td strong, td small {{ display: block; }}
    tr:last-child td {{ border-bottom: 0; }}
    .table-wrap {{ max-height: 700px; overflow: auto; border-radius: 8px; }}
    .badge {{ display: inline-block; border-radius: 999px; padding: 3px 8px; font-size: 12px; white-space: nowrap; }}
    .buildable-now {{ color: var(--green); background: #e8f4f1; }}
    .blocked-for-now {{ color: var(--red); background: #f8eaea; }}
    .small {{ font-size: 12px; color: var(--muted); }}
    @media (max-width: 900px) {{
      main {{ padding: 28px 14px 48px; }}
      .metrics, .two {{ grid-template-columns: 1fr; }}
      .bar {{ grid-template-columns: 120px 1fr 34px; }}
    }}
  </style>
</head>
<body>
<main>
  <header>
    <p class="eyebrow">AI Product Ops Intern take-home | Composio app research automation</p>
    <h1>I researched 100 requested apps with an agent, then checked the rows where automation was weakest.</h1>
    <p class="lede">The useful finding is not the table itself. Composio already covers most mainstream SaaS requests. The remaining misses are concentrated in partner-gated APIs, thin developer docs, and ambiguous products that need a human before engineering scopes a toolkit.</p>
  </header>

  <section class="grid metrics">
    <div class="card metric"><b>{resolved}/100</b><span>apps classified</span></div>
    <div class="card metric"><b>{pct(len(buildable), resolved)}</b><span>buildable today</span></div>
    <div class="card metric"><b>{source_counts['Catalog match']}</b><span>already in Composio</span></div>
    <div class="card metric"><b>{source_counts['Manual check']}</b><span>manual checks after failures</span></div>
  </section>

  <section>
    <h2>Decision Memo</h2>
    <ol class="findings">
      <li><b>Ship the easy wins first.</b> {len(buildable)} apps are buildable today based on a public API, existing Composio coverage, a CLI wrapper path, or a documented MCP/API surface.</li>
      <li><b>Use OAuth2 as the default path for mature SaaS.</b> API keys still matter in infra, data, scraping, and fintech, but OAuth2 is the recurring pattern across broad SaaS tools.</li>
      <li><b>Pause outreach-gated rows before engineering.</b> Amazon SP-API, PitchBook, Consensus, Fanbasis, Waterfall, and Paygent-style rows need access or partner conversations before implementation.</li>
      <li><b>Keep a human review step.</b> The agent scaled the research, but the risky mistakes were identity mistakes: Copper vs Copperx, Salesforce Commerce Cloud vs Service Cloud, and prompt-like content in fetched docs.</li>
    </ol>
  </section>

  <section class="grid two">
    <div class="card">
      <h2>Patterns</h2>
      <div class="pill-row">
        <span class="pill">OAuth2 in mature SaaS</span>
        <span class="pill">API keys in data and infra</span>
        <span class="pill">Gating is the main blocker</span>
      </div>
      <p>Existing Composio coverage is strongest in CRM, support, developer platforms, productivity, marketing, and finance. The rows that remain blocked are rarely blocked by raw API complexity; they are blocked by missing docs, paid or partner access, or product ambiguity.</p>
      <p>Among the 100 rows, {len(blocked)} are blocked for now and {len(buildable)} are buildable today.</p>
    </div>
    <div class="card method">
      <h2>What I Built</h2>
      <p><b>Layer 1:</b> matched the 100 apps against Composio's toolkit catalog and reused known auth schemes, categories, evidence URLs, and action counts.</p>
      <p><b>Layer 2:</b> fetched docs with Composio search, then used Groq to extract fields into a Pydantic schema. Fetched page content was treated as untrusted data.</p>
      <p><b>Verification:</b> manually checked false matches, low-confidence rows, failed fetches, and products where the public page did not answer the integration question.</p>
    </div>
  </section>

  <section class="grid two">
    <div class="card">
      <h2>Auth Mix</h2>
      {auth_bars}
    </div>
    <div class="card">
      <h2>Access Mix</h2>
      {access_bars}
    </div>
  </section>

  <section class="grid two">
    <div class="card">
      <h2>Blocked Rows</h2>
      {blocker_bars}
    </div>
    <div class="card">
      <h2>Verification Notes</h2>
      <p><b>Accuracy movement:</b> the automated run produced 82 usable rows; verification brought coverage to 100/100 and corrected the highest-risk failure mode: wrong product identity.</p>
      <p><b>Copper:</b> rejected a fuzzy match to Copperx, which is a different product.</p>
      <p><b>Salesforce Commerce Cloud:</b> kept separate from generic Salesforce and Service Cloud.</p>
      <p><b>NotebookLM:</b> recovered a first-pass false negative by adding the Composio alias <code>google_notebooklm</code>.</p>
      <p><b>iPayX:</b> treated prompt-like fetched content as data, not instructions.</p>
      <p><b>18 failures:</b> filled through manual verification and kept labeled as manual, not agent output.</p>
    </div>
  </section>

  <section>
    <h2>Category Coverage</h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Category</th><th>Rows</th><th>Buildable</th><th>Buildable rate</th></tr></thead>
        <tbody>{category_html}</tbody>
      </table>
    </div>
  </section>

  <section>
    <h2>100-App Matrix</h2>
    <p>The source column is the audit trail: catalog match, agent extract, or manual check. I kept blocked rows visible instead of smoothing them over.</p>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th><th>App</th><th>What it does</th><th>Auth</th><th>Access</th>
            <th>API surface</th><th>Verdict</th><th>Blocker</th><th>Evidence</th><th>Source</th>
          </tr>
        </thead>
        <tbody>{table_html}</tbody>
      </table>
    </div>
  </section>

  <section>
    <h2>Reproduce</h2>
    <div class="card">
      <p><code>python pipeline_layer1_composio_match.py</code></p>
      <p><code>python -u pipeline_layer2_research_agent.py</code></p>
      <p><code>python scripts/build_case_study.py</code></p>
      <p class="small">Outputs: data JSON files, <code>case_study.html</code>, and <code>index.html</code>.</p>
    </div>
  </section>
</main>
</body>
</html>
"""

    for path in OUT_FILES:
        path.write_text(html_doc, encoding="utf-8")
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
