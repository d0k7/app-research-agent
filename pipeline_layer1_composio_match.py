"""
Layer 1: Fast path.
Match the 100-app seed list against Composio's own toolkit catalog
(pulled from ComposioHQ/composio's docs/public/data/toolkits.json on GitHub).

If an app already exists as a Composio toolkit, that's direct evidence of:
  - auth method(s) (authSchemes)
  - API surface breadth (toolCount = number of agent-callable actions)
  - buildability verdict = TRUE (Composio already built it)
  - evidence = the toolkit's page on composio.dev/toolkits/<slug>

Anything NOT matched here goes to the Layer 2 research queue.

Run: python3 pipeline_layer1_composio_match.py
"""
import json
import re
import difflib
from pathlib import Path

DATA = Path(__file__).parent / "data"

apps = json.load(open(DATA / "apps_seed.json"))
toolkits = json.load(open(DATA / "toolkits_lean.json"))

# index toolkits by normalized slug and normalized name
def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\(.*?\)", "", s)          # drop parentheticals: "Lark (Larksuite)" -> "Lark "
    s = re.sub(r"\.(io|com|ai|dev)\b", "", s)  # drop trailing .io/.com/.ai/.dev
    s = re.sub(r"[^a-z0-9]+", "", s)       # strip spaces/punctuation
    return s.strip()

by_slug = {norm(t["slug"]): t for t in toolkits}
by_name = {norm(t["name"]): t for t in toolkits}
all_norm_names = list(by_name.keys())

# manual aliases where the assignment's app name won't naturally match Composio's slug/name
ALIASES = {
    "zohocrm": "zoho",
    "whatsappbusiness": "whatsapp",
    "linkedinads": "linkedin",
    "magentoadobecommerce": "magento",
    "amazonsellingpartner": "amazonsellingpartnerapi",
    "mondaycom": "monday",
    "mermaidcli": "mermaid",
    "notebooklm": "googlenotebooklm",
}

# confirmed by hand: catalog has near-miss names that are NOT the same product.
# block these so fuzzy matching can't silently paper over the difference.
BLOCKLIST_FUZZY = {
    "copper": "copperx",                                  # CRM (copper.com) != Copperx (crypto payments)
    "salesforcecommercecloud": "salesforce_service_cloud", # Commerce Cloud != Service Cloud, no CC toolkit exists
}

results = []
for a in apps:
    key = norm(a["name"])
    key = ALIASES.get(key, key)

    match = by_slug.get(key) or by_name.get(key)
    confidence = "exact" if match else None
    rejected_note = None

    if not match:
        # fuzzy fallback, but don't trust it blindly, flag it
        close = difflib.get_close_matches(key, all_norm_names, n=1, cutoff=0.82)
        if close:
            candidate = by_name[close[0]]
            if BLOCKLIST_FUZZY.get(key) == candidate["slug"]:
                rejected_note = (
                    f"fuzzy match to '{candidate['slug']}' rejected by hand: "
                    f"different product, not the same company"
                )
            else:
                match = candidate
                confidence = "fuzzy_needs_check"

    row = {
        "number": a["number"],
        "app": a["name"],
        "category_given": a["category"],
        "hint": a["hint"],
    }
    if rejected_note:
        row["fuzzy_rejected"] = rejected_note
    if match:
        row.update({
            "composio_toolkit_found": True,
            "match_confidence": confidence,
            "composio_slug": match["slug"],
            "composio_category": match["category"],
            "auth_schemes": match["authSchemes"],
            "tool_count": match["toolCount"],
            "description": match["description"],
            "evidence_url": f"https://composio.dev/toolkits/{match['slug']}",
        })
    else:
        row.update({
            "composio_toolkit_found": False,
            "match_confidence": None,
        })
    results.append(row)

found = [r for r in results if r["composio_toolkit_found"]]
fuzzy = [r for r in found if r["match_confidence"] == "fuzzy_needs_check"]
missing = [r for r in results if not r["composio_toolkit_found"]]

json.dump(results, open(DATA / "layer1_results.json", "w"), indent=1)

print(f"Matched via Composio's own toolkit catalog: {len(found)}/100")
print(f"  of which exact:              {len(found) - len(fuzzy)}")
print(f"  of which fuzzy (needs check): {len(fuzzy)}")
print(f"Needs Layer 2 research:         {len(missing)}/100")
print()
print("--- fuzzy matches, verify these by hand ---")
for r in fuzzy:
    print(f"  #{r['number']:>3} {r['app']:<28} -> {r['composio_slug']}")
print()
print("--- no Composio toolkit found, needs live research ---")
for r in missing:
    print(f"  #{r['number']:>3} [{r['category_given']}] {r['app']} ({r['hint']})")
