# Composio 100-app research agent

Research pipeline for the AI Product for each of the 100 apps
in the assignment, determine category, auth method(s), self-serve vs gated access,
API surface, MCP existence, and a buildability verdict, with evidence for each.

## How it works

**Layer 1, fast path.** Composio's own toolkit catalog (1,403 toolkits, pulled
from `ComposioHQ/composio`'s `docs/public/data/toolkits.json` on GitHub) already
lists auth scheme, category, and action count for every app it already supports.
Matching the 100 apps against that catalog needs zero live API calls and resolved
71/100 directly. `pipeline_layer1_composio_match.py`

**Layer 2, research path.** For apps with no existing Composio toolkit, an agent
calls Composio's own `COMPOSIO_SEARCH_FETCH_URL_CONTENT` tool to fetch the docs
page given in the assignment, then Groq (`llama-3.3-70b-versatile`) extracts the
required fields into a validated schema. The extraction prompt explicitly treats
fetched page content as untrusted data, not instructions, see the iPayX note
below for why that matters. `pipeline_layer2_research_agent.py`

**Layer 3, patterns and deliverable.** `scripts/build_case_study.py` merges the
catalog matches, agent results, and error queue into one self-contained
`case_study.html`. It computes auth/access/buildability summaries and includes
the full 100-app matrix.

**Layer 4, verification.** `data/manual_research_results.json` closes the rows
where the automated Layer 2 run failed or timed out. Those rows are labeled as
manual verification in the HTML rather than mixed into the agent output. The
HTML also shows specific checks: rejected fuzzy false positives, recovered alias
false negative, prompt injection handling, and low-confidence rows surfaced
honestly.

## Setup

```bash
py -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# fill in COMPOSIO_API_KEY and GROQ_API_KEY in .env
```

Groq keys are free at console.groq.com if you need a new one.

## Run order

```bash
py pipeline_layer1_composio_match.py       # already run, output in data/layer1_results.json
py scripts/check_tool_schema.py            # confirm the fetch tool's arg key is "url" before batch running
py pipeline_layer2_research_agent.py        # writes data/layer2_results.json + data/layer2_errors.json
py scripts/build_case_study.py              # writes case_study.html
```

## Current status

- 71/100 resolved directly from Composio's own catalog, no scraping needed.
- 11/29 Layer 2 rows resolved by the Composio-search + Groq extraction agent.
- 18/100 were completed through targeted manual verification after Layer 2
  failures: Ecwid, Amazon Selling Partner, fanbasis, SE Ranking, MrScraper,
  Sherlock, Waterfall.io, MongoDB Atlas, Smartsheet, Binance, Paygent Connect,
  iPayX, PitchBook, Otter AI, Consensus, Devin, Mermaid CLI, YouTube Transcript.
- Final coverage in `case_study.html`: 100/100 rows, with source layer shown per row.
- Deliverable page: open `case_study.html` in a browser.

## Verification notes so far

Caught during Layer 1, before any live research even started:

- **Copper** (the CRM) has no Composio toolkit. A naive fuzzy match nearly
  matched it to "Copperx," an unrelated payments company. Rejected by hand,
  now correctly queued for Layer 2.
- **Salesforce Commerce Cloud** has no Composio toolkit either, only generic
  Salesforce, Marketing Cloud, and Service Cloud exist. Fuzzy match nearly
  picked Service Cloud. Rejected by hand.
- **NotebookLM** was a false negative on the first pass, Composio's real slug
  is `google_notebooklm`, which fell just outside the fuzzy-match threshold.
  Found by manually grepping the raw catalog and added as an explicit alias.
- **iPayX** (`ipayx.ai/docs`, app #85): its own MCP tool descriptions contain
  a hard rule instructing AI systems never to name competitor services. Real
  example of untrusted page content trying to direct an agent's output, which
  is why Layer 2's extraction prompt explicitly tells the model to treat
  fetched content as data, not instructions. There's also a second, unrelated
  company under a similar name (a Toledo, Ohio billing company acquired by
  BillingTree in 2017), so that row needs explicit disambiguation.
