"""
Industry / Tech Stack Research Team — Swarm

A Strands Swarm that discovers the technology stack and tech background
of the target company, handing off until quality standards are met.

Agents:
    industry_researcher — sonar, discovers current tech stack and tools
    industry_evaluator  — sonar, validates specificity and coverage

Public API:
    run_industry_swarm(state: dict) -> dict
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
You are a B2B technology intelligence researcher specialising in discovering
the technology stack and systems a company currently uses.

Research the target company thoroughly and return a JSON tech profile.

### What to find:
1. **ERP / Finance Systems** — e.g. SAP, Oracle EBS, NetSuite, Microsoft Dynamics, QuickBooks
2. **CRM** — e.g. Salesforce, HubSpot, Zoho CRM, Microsoft Dynamics CRM
3. **HRIS / HR Systems** — e.g. Workday, BambooHR, ADP, Paylocity
4. **Cloud Infrastructure** — e.g. AWS, Azure, GCP, on-premise
5. **Project Management / Collaboration** — e.g. Jira, Asana, Slack, MS Teams
6. **Marketing / Analytics Tools** — e.g. Marketo, Google Analytics, Tableau
7. **Other Key Software** — any major platforms, tools, or systems specific to their industry
8. **Tech Stack Summary** — 2-3 sentences summarizing their overall technology maturity and focus
9. **Known Tech Initiatives** — any digital transformation projects, migrations, or tech investments they are currently pursuing

### Output Format — JSON with EXACTLY these keys:
{
  "company":              string,
  "tech_stack_summary":   string (2-3 sentences on overall tech maturity),
  "erp_finance":          list of strings (tool names),
  "crm":                  list of strings (tool names),
  "hris":                 list of strings (tool names),
  "cloud_infrastructure": list of strings (tool names),
  "collaboration_tools":  list of strings (tool names),
  "marketing_analytics":  list of strings (tool names),
  "other_tools":          list of strings (tool names),
  "tech_initiatives":     list of strings (current/recent projects),
  "sources":              list of URLs
}

Use "Not identified" as the list entry if a category truly cannot be found.
Return ONLY valid JSON — no markdown, no explanation.
""".strip()

_EVALUATOR_PROMPT = """
You are a strict data quality evaluator for B2B technology intelligence.

Evaluate the tech stack JSON against these rules:
1. **tech_stack_summary**: Must be 2-3 specific sentences. Reject if generic.
2. **Coverage**: At least 3 of the 7 category lists (erp_finance, crm, hris,
   cloud_infrastructure, collaboration_tools, marketing_analytics, other_tools)
   must have real tool names (not "Not identified").
3. **Specificity**: Tool names must be specific products, not categories
   (e.g. "Salesforce" not "a CRM").
4. **tech_initiatives**: At least 1 known initiative or "Not publicly disclosed".
5. **sources**: At least 1 URL.

Score 1-10.
- If score < 8: call handoff_to_agent(agent_name="industry_researcher") with numbered feedback.
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
    try:
        for node in reversed(result.node_history):
            node_result = result.results.get(node.node_id)
            if node_result and node_result.result:
                data = _extract_json(str(node_result.result))
                if data and "raw_response" not in data:
                    return data
        for _, node_result in result.results.items():
            if node_result and node_result.result:
                data = _extract_json(str(node_result.result))
                if data and "raw_response" not in data:
                    return data
    except Exception:
        pass
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Swarm Runner
# ─────────────────────────────────────────────────────────────────────────────

def run_industry_swarm(state: dict) -> dict:
    """
    Run the Tech Stack Research Swarm.

    Reads from state:  company_name, company_profile (for industry context)
    Writes to state:   industry_research, all_sources (extended)
    """
    company_name    = state["company_name"]
    company_profile = state.get("company_profile", {})
    industry        = company_profile.get("industry", "")
    website         = company_profile.get("website", "")

    print(f"\n{'='*60}")
    print(f"  Tech Stack Swarm — {company_name}")
    print(f"{'='*60}")

    researcher = Agent(
        name="industry_researcher",
        model=PerplexitySonar("sonar"),
        system_prompt=_RESEARCHER_PROMPT,
    )
    evaluator = Agent(
        name="industry_evaluator",
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

    task = (
        f"Discover the complete technology stack and systems currently used by '{company_name}'. "
        f"Industry: {industry}. Website: {website}.\n\n"
        "Find their ERP/finance, CRM, HRIS, cloud infrastructure, collaboration tools, "
        "marketing/analytics platforms, and any other key software. "
        "Also identify any current digital transformation or tech initiatives they are pursuing. "
        "Return the complete tech stack JSON with all required fields."
    )

    result = swarm(task)

    research = _get_swarm_result(result)
    sources  = research.get("sources", [])

    state["industry_research"] = research
    state.setdefault("all_sources", []).extend(sources)

    covered   = sum(
        1 for k in ["erp_finance", "crm", "hris", "cloud_infrastructure",
                     "collaboration_tools", "marketing_analytics", "other_tools"]
        if research.get(k) and research[k] != ["Not identified"]
    )
    nodes_run = [n.node_id for n in result.node_history]
    print(f"  [Tech Stack Swarm] ✅ Done — {covered}/7 categories covered, "
          f"nodes: {' → '.join(nodes_run)}")
    return state
