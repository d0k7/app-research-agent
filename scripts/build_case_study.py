import html
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "case_study.html"


def load(name):
    return json.load(open(DATA / name, encoding="utf-8"))


def esc(value):
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


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
    out = []
    for value in values or []:
        raw = str(value)
        low = raw.lower()
        if "oauth" in low:
            out.append("OAuth2")
        elif "api_key" in low or "api key" in low or "apikey" in low:
            out.append("API key")
        elif "basic" in low:
            out.append("Basic")
        elif "token" in low or "bearer" in low:
            out.append("Token")
        else:
            out.append("Other / unclear")
    return out or ["Other / unclear"]


def row_from_layer1(row):
    auth = normalize_auth(row.get("auth_schemes"))
    return {
        "number": row["number"],
        "app": row["app"],
        "category": row["category_given"],
        "what": row.get("description", ""),
        "auth": ", ".join(auth),
        "access": "Existing Composio toolkit",
        "api": f"Composio toolkit with {row.get('tool_count', 0)} actions",
        "mcp": "Not checked",
        "verdict": "Buildable now",
        "blocker": "",
        "evidence": row.get("evidence_url", ""),
        "confidence": row.get("match_confidence", "catalog"),
        "status": "Resolved by catalog",
        "source_layer": "Layer 1",
        "buildable": True,
    }


def row_from_layer2(row):
    source_layer = "Manual verification" if row.get("layer") == 3 else "Layer 2"
    status = "Human verified" if row.get("layer") == 3 else "Resolved by agent"
    return {
        "number": row["number"],
        "app": row["app"],
        "category": row["category_given"],
        "what": row.get("category", ""),
        "auth": ", ".join(normalize_auth(row.get("auth_methods"))),
        "access": row.get("access", "unclear").replace("_", " "),
        "api": row.get("api_surface", ""),
        "mcp": "Yes" if row.get("has_mcp") else "No",
        "verdict": "Buildable now" if row.get("buildable_today") else "Not buildable yet",
        "blocker": row.get("blocker") or "",
        "evidence": row.get("evidence_url", ""),
        "confidence": row.get("confidence", ""),
        "status": status,
        "source_layer": source_layer,
        "buildable": bool(row.get("buildable_today")),
    }


def row_from_error(seed_row, error):
    return {
        "number": seed_row["number"],
        "app": seed_row["name"],
        "category": seed_row["category"],
        "what": "Not resolved by current automated run",
        "auth": "Unknown",
        "access": "Unknown",
        "api": "Needs manual or retry pass",
        "mcp": "Unknown",
        "verdict": "Unresolved",
        "blocker": "Layer 2 failed or timed out before extraction",
        "evidence": seed_row["hint"],
        "confidence": "none",
        "status": "Needs follow-up",
        "source_layer": "Error queue",
        "buildable": False,
    }


def pct(n, d):
    return f"{round((n / d) * 100)}%" if d else "0%"


def bar(label, value, total):
    width = max(2, round(value / total * 100)) if total else 0
    return f"""
    <div class="bar-row">
      <div class="bar-label">{esc(label)}</div>
      <div class="bar-track"><span style="width:{width}%"></span></div>
      <div class="bar-value">{value}</div>
    </div>"""


def main():
    seed = load("apps_seed.json")
    layer1 = load("layer1_results.json")
    layer2 = load("layer2_results.json")
    errors = load("layer2_errors.json")
    manual = load("manual_research_results.json") if (DATA / "manual_research_results.json").exists() else []

    seed_by_num = {r["number"]: r for r in seed}
    rows = []
    manual_nums = {r["number"] for r in manual}

    for row in layer1:
        if row.get("composio_toolkit_found"):
            rows.append(row_from_layer1(row))
    for row in layer2:
        rows.append(row_from_layer2(row))
    for row in manual:
        rows.append(row_from_layer2(row))
    for err in errors:
        if err["number"] in manual_nums:
            continue
        rows.append(row_from_error(seed_by_num[err["number"]], err))

    rows.sort(key=lambda r: r["number"])

    resolved = [r for r in rows if r["status"] != "Needs follow-up"]
    unresolved = [r for r in rows if r["status"] == "Needs follow-up"]
    buildable = [r for r in resolved if r["buildable"]]
    not_buildable = [r for r in resolved if not r["buildable"]]

    auth_counts = Counter()
    access_counts = Counter()
    category_counts = Counter()
    category_buildable = defaultdict(int)
    for row in resolved:
        category_counts[row["category"]] += 1
        if row["buildable"]:
            category_buildable[row["category"]] += 1
        for auth in row["auth"].split(", "):
            auth_counts[auth] += 1
        access_counts[row["access"]] += 1

    top_categories = sorted(category_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    table_rows = "\n".join(
        f"""
        <tr>
          <td>{row['number']}</td>
          <td><strong>{esc(row['app'])}</strong><span>{esc(row['category'])}</span></td>
          <td>{esc(row['what'])}</td>
          <td>{esc(row['auth'])}</td>
          <td>{esc(row['access'])}</td>
          <td>{esc(row['api'])}</td>
          <td>{esc(row['verdict'])}</td>
          <td>{esc(row['blocker'])}</td>
          <td><a href="{esc(href(row['evidence']))}">{esc(row['evidence'])}</a></td>
          <td>{esc(row['source_layer'])}<span>{esc(row['confidence'])}</span></td>
        </tr>"""
        for row in rows
    )

    unresolved_names = ", ".join(r["app"] for r in unresolved) or "None"
    category_cards = "\n".join(
        f"""
        <div class="mini-card">
          <b>{esc(category)}</b>
          <span>{count} resolved, {category_buildable[category]} buildable</span>
        </div>"""
        for category, count in top_categories
    )
    auth_bars = "\n".join(bar(k, v, len(resolved)) for k, v in auth_counts.most_common())
    access_bars = "\n".join(bar(k, v, len(resolved)) for k, v in access_counts.most_common())

    verification_rows = [
        ("Copper", "Rejected fuzzy match to Copperx", "Prevented a wrong-toolkit false positive."),
        ("Salesforce Commerce Cloud", "Rejected generic Salesforce/Service Cloud match", "Kept ecommerce-specific row in Layer 2."),
        ("NotebookLM", "Added explicit alias google_notebooklm", "Recovered a first-pass false negative."),
        ("iPayX", "Detected prompt-injection-like page content", "Extractor prompt treats fetched content as data, not instructions."),
        ("Podio", "Layer 2 extracted from fetched page", "Medium confidence because page text was marketing-heavy."),
        ("Pylon / Gladly / Copper", "Agent marked no public API found", "Low confidence rows are surfaced as not buildable, not hidden."),
        ("18 Layer 2 failures", "Manual verification layer added", "All 100 rows now have evidence; manually filled rows remain labeled as Manual verification."),
    ]
    verification_html = "\n".join(
        f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td></tr>"
        for a, b, c in verification_rows
    )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Composio 100-App Research Agent Case Study</title>
  <style>
    :root {{
      --bg: #f6f7f9;
      --panel: #ffffff;
      --ink: #17202a;
      --muted: #5f6b7a;
      --line: #d9dee7;
      --blue: #1d4ed8;
      --green: #0f766e;
      --amber: #b45309;
      --red: #b91c1c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font: 14px/1.45 Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Arial, sans-serif;
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 56px; }}
    header {{ border-bottom: 1px solid var(--line); padding-bottom: 20px; margin-bottom: 22px; }}
    h1 {{ font-size: clamp(28px, 4vw, 48px); line-height: 1.02; margin: 0 0 12px; letter-spacing: 0; }}
    h2 {{ font-size: 22px; margin: 30px 0 12px; }}
    h3 {{ font-size: 16px; margin: 0 0 8px; }}
    p {{ color: var(--muted); margin: 0 0 12px; }}
    a {{ color: var(--blue); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .headline {{ max-width: 900px; font-size: 17px; color: #2b3542; }}
    .grid {{ display: grid; gap: 12px; }}
    .metrics {{ grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 20px 0; }}
    .card, .mini-card, .note {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .metric b {{ display: block; font-size: 30px; line-height: 1; margin-bottom: 6px; }}
    .metric span, .mini-card span, td span {{ display: block; color: var(--muted); font-size: 12px; margin-top: 3px; }}
    .two {{ grid-template-columns: 1fr 1fr; }}
    .three {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .mini-card b {{ display: block; margin-bottom: 4px; }}
    .bar-row {{ display: grid; grid-template-columns: 150px 1fr 42px; gap: 10px; align-items: center; margin: 8px 0; }}
    .bar-label {{ color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .bar-track {{ height: 10px; background: #edf1f6; border-radius: 999px; overflow: hidden; }}
    .bar-track span {{ display: block; height: 100%; background: var(--blue); }}
    .bar-value {{ text-align: right; color: var(--muted); }}
    .callout {{ border-left: 4px solid var(--amber); background: #fff8ed; padding: 12px 14px; border-radius: 6px; }}
    .pill {{ display: inline-block; border: 1px solid var(--line); border-radius: 999px; padding: 3px 8px; margin: 2px 4px 2px 0; color: #334155; background: #fff; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 9px 10px; text-align: left; vertical-align: top; }}
    th {{ position: sticky; top: 0; background: #eef2f7; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: #475569; }}
    td {{ font-size: 13px; }}
    tr:last-child td {{ border-bottom: 0; }}
    .table-wrap {{ max-height: 720px; overflow: auto; border-radius: 8px; }}
    .small {{ font-size: 12px; color: var(--muted); }}
    @media (max-width: 900px) {{
      .metrics, .two, .three {{ grid-template-columns: 1fr; }}
      .bar-row {{ grid-template-columns: 120px 1fr 34px; }}
      main {{ padding: 22px 14px 40px; }}
    }}
  </style>
</head>
<body>
<main>
  <header>
    <p class="small">AI Product Ops Intern take-home · Composio app research automation</p>
    <h1>Most requested integrations are already agent-callable; the remaining gap is gated or poorly documented long-tail apps.</h1>
    <p class="headline">The pipeline resolved {len(resolved)}/100 apps: {sum(1 for r in rows if r['source_layer'] == 'Layer 1')} through Composio's existing toolkit catalog, {sum(1 for r in rows if r['source_layer'] == 'Layer 2')} through a Composio-search + Groq extraction agent, and {sum(1 for r in rows if r['source_layer'] == 'Manual verification')} through targeted manual verification of failed rows. {len(unresolved)} rows remain unresolved.</p>
  </header>

  <section class="grid metrics">
    <div class="card metric"><b>{len(resolved)}</b><span>resolved rows</span></div>
    <div class="card metric"><b>{pct(len(buildable), len(resolved))}</b><span>buildable among resolved rows</span></div>
    <div class="card metric"><b>{auth_counts.get('OAuth2', 0)}</b><span>resolved rows using OAuth2</span></div>
    <div class="card metric"><b>{len(unresolved)}</b><span>rows needing retry/manual research</span></div>
  </section>

  <section class="grid two">
    <div class="card">
      <h2>Patterns</h2>
      <p><span class="pill">OAuth2 dominates mature SaaS</span><span class="pill">API keys dominate infra/data</span><span class="pill">Docs quality is the main blocker</span></p>
      <p>Existing Composio coverage is strongest in CRM, support, developer platforms, productivity, marketing, and finance. The easy wins are rows with clear REST/GraphQL docs and credential flows. The hard rows are not technically hard; they are access/process hard: partner-gated APIs, unclear developer access, product pages without docs, or ambiguous product identity.</p>
      <p>Among resolved rows, {len(buildable)} are buildable today and {len(not_buildable)} are currently blocked.</p>
    </div>
    <div class="card">
      <h2>Agent Workflow</h2>
      <p><b>Layer 1:</b> match the 100 apps against Composio's toolkit catalog and reuse known auth schemes, categories, evidence URLs, and action counts.</p>
      <p><b>Layer 2:</b> for apps with no catalog match, call Composio's search fetch tool, then ask Groq to extract into a Pydantic-validated schema. Fetched docs are treated as untrusted data.</p>
      <p><b>Human loop:</b> inspect false fuzzy matches, disambiguate similar company names, and manually review low-confidence or failed rows.</p>
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

  <section>
    <h2>Category Coverage</h2>
    <div class="grid three">{category_cards}</div>
  </section>

  <section>
    <h2>Verification</h2>
    <div class="callout">
      <p><b>Honesty note:</b> this run is not a fully verified final answer. It has a working automation path and an explicit error queue. The current trustworthy claim is coverage and pattern direction, not perfect 100-row accuracy.</p>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>Sample</th><th>Check performed</th><th>Result</th></tr></thead>
        <tbody>{verification_html}</tbody>
      </table>
    </div>
  </section>

  <section>
    <h2>Open Queue</h2>
    <p>{esc(unresolved_names)}</p>
  </section>

  <section>
    <h2>100-App Matrix</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th><th>App</th><th>Category / one-line</th><th>Auth</th><th>Access</th>
            <th>API surface</th><th>Verdict</th><th>Blocker</th><th>Evidence</th><th>Source</th>
          </tr>
        </thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>
  </section>

  <section>
    <h2>Run It</h2>
    <div class="card">
      <p><code>python pipeline_layer1_composio_match.py</code></p>
      <p><code>python -u pipeline_layer2_research_agent.py</code></p>
      <p><code>python scripts/build_case_study.py</code></p>
      <p class="small">Outputs: <code>data/layer1_results.json</code>, <code>data/layer2_results.json</code>, <code>data/layer2_errors.json</code>, and this self-contained <code>case_study.html</code>.</p>
    </div>
  </section>
</main>
</body>
</html>
"""

    OUT.write_text(html_doc, encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
