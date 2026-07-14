"""
Run this once before Layer 2. Prints the real input schema for
COMPOSIO_SEARCH_FETCH_URL_CONTENT so you can confirm the argument key
pipeline_layer2_research_agent.py assumes ("url") is actually correct.

Run: python3 scripts/check_tool_schema.py
"""
import json
import os

from composio import Composio
from dotenv import load_dotenv

load_dotenv()

composio = Composio(api_key=os.environ["COMPOSIO_API_KEY"])
tool = composio.tools.get(user_id="default", slug="COMPOSIO_SEARCH_FETCH_URL_CONTENT")
print(json.dumps(tool, indent=2, default=str))
