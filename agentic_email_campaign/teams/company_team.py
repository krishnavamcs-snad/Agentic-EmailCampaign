"""
Company Research Team — Swarm

A Strands Swarm with two agents that autonomously research and evaluate
the target company's profile, handing off between each other until the
result meets quality standards or max handoffs are reached.

Agents:
    company_researcher — sonar, gathers company profile JSON
    company_evaluator  — sonar, validates quality and either approves
                         (stops the swarm) or hands back with feedback

Public API:
    run_company_swarm(state: dict) -> dict
"""

from __future__ import annotations

import json
import re

from strands import Agent
from strands.multiagent import Swarm

from agentic_email_campaign.models import PerplexitySonar

# ─────────────────────────────────────────────────────────────────────────────
# System Prompts
# ─────────────────────────────────────────────────────────────────────────────

_RESEARCHER_PROMPT = """
You are a B2B marketing intelligence researcher specialising in company profiles.

Research the target company thoroughly and return a factual JSON profile with ONLY the keys below.

### Quality Rules:
- **description**: Write 2-3 specific sentences about what the company does, their specialisations, client base, and notable differentiators. Do NOT write generic statements.
- **employee_count** and **estimated_revenue**: Use the values from the provided `initial_context` brief. If you find clearer data from authoritative sources (ZoomInfo, D&B, LinkedIn), use that instead.
- **locations**: List all known office locations. Do NOT guess — only include confirmed locations.
- **core_products_services**: List the 3-5 most prominent products/services the company is known for, using their proper names.

### Output Format — JSON with EXACTLY these keys:
{
  "name":                  string,
  "website":               string (full URL),
  "description":           string (2-3 specific sentences),
  "industry":              string,
  "sector":                string,
  "employee_count":        string (range, e.g. "51-200"),
  "estimated_revenue":     string (range, e.g. "$5M-$15M"),
  "headquarters":          string (full address),
  "locations":             list of strings,
  "regions_served":        list of strings,
  "core_products_services": list of 3-5 strings,
  "sources":               list of URLs
}

Return ONLY valid JSON — no markdown, no explanation.
""".strip()

_EVALUATOR_PROMPT = """
You are a strict data quality evaluator for B2B company research.

Evaluate the JSON profile against these rules:
1. **All 12 keys present and non-empty**: name, website, description, industry, sector,
   employee_count, estimated_revenue, headquarters, locations, regions_served,
   core_products_services, sources.
2. **Description quality**: Must be 2-3 specific sentences. Reject if vague or generic.
3. **No empty lists**: locations, regions_served, core_products_services, and sources must all have at least 1 real entry.
4. **Revenue & employee consistency**: Must be consistent with the initial_context brief.

Score 1-10.
- If score < 8: call handoff_to_agent(agent_name="company_researcher") with numbered feedback listing every issue.
- If score >= 8: return ONLY the approved JSON as your final response, no extra text.
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    try:
        match = re.search(r'\{[\s\S]*\}', str(text))
        return json.loads(match.group()) if match else json.loads(str(text))
    except Exception:
        return {"raw_response": str(text)}


def _get_swarm_result(result) -> dict:
    """Extract the final agent's text result from a Swarm result object."""
    try:
        # Try to get the last completed node's result
        for node in reversed(result.node_history):
            node_result = result.results.get(node.node_id)
            if node_result and node_result.result:
                text = str(node_result.result)
                data = _extract_json(text)
                if data and "raw_response" not in data:
                    return data
        # Fallback: try all results
        for key, node_result in result.results.items():
            if node_result and node_result.result:
                data = _extract_json(str(node_result.result))
                if data and "raw_response" not in data:
                    return data
    except Exception:
        pass
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Swarm Factory + Runner
# ─────────────────────────────────────────────────────────────────────────────

def run_company_swarm(state: dict) -> dict:
    """
    Run the Company Research Swarm.

    Reads from state:  company_name, initial_context
    Writes to state:   company_profile, all_sources (extended)
    """
    company_name    = state["company_name"]
    initial_context = state.get("initial_context", {})

    print(f"\n{'='*60}")
    print(f"  Company Swarm — Researching: {company_name}")
    print(f"{'='*60}")

    researcher = Agent(
        name="company_researcher",
        model=PerplexitySonar("sonar"),
        system_prompt=_RESEARCHER_PROMPT,
    )
    evaluator = Agent(
        name="company_evaluator",
        model=PerplexitySonar("sonar"),
        system_prompt=_EVALUATOR_PROMPT,
    )

    swarm = Swarm(
        [researcher, evaluator],
        entry_point=researcher,
        max_handoffs=6,
        max_iterations=8,
        repetitive_handoff_detection_window=4,
        repetitive_handoff_min_unique_agents=2,
    )

    context_hint = (
        f"Initial context: industry={initial_context.get('industry','')}, "
        f"website={initial_context.get('company_website','')}"
    )
    task = (
        f'Research the company "{company_name}".\n'
        f'Brief Context to follow: {json.dumps(initial_context)}\n\n'
        "Return a complete company profile JSON with all required fields."
    )

    result = swarm(task)

    profile = _get_swarm_result(result)
    sources = profile.get("sources", [])

    state["company_profile"] = profile
    state.setdefault("all_sources", []).extend(sources)

    nodes_run = [n.node_id for n in result.node_history]
    print(f"  [Company Swarm] ✅ Done — nodes: {' → '.join(nodes_run)}, {len(sources)} sources")
    return state
