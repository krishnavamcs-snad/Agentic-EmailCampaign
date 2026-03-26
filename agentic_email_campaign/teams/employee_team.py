"""
Employee Research Team — Swarm

A Strands Swarm that discovers the leadership team and known employees
at a target company, handing off until the quality bar is met.

Agents:
    employee_researcher — sonar, discovers leadership and employee list JSON
    employee_evaluator  — sonar, validates and either approves or hands back

Public API:
    run_employee_swarm(state: dict) -> dict
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
You are a B2B sales intelligence researcher specialising in company people research.

Your job is to find the current leadership team and known employees at the target company.

### Leadership Team (REQUIRED):
Find the current C-suite and key executives. For EACH person provide:
1. Full name (real, verified)
2. Exact current job title

Cover: CEO, CTO, COO, CFO, President, Co-Founders, VP-level leaders, and other C-suite.
List at least 3-5 executives. Only include real, currently employed people.

### Employees (OPTIONAL but preferred):
List any other known employees at the company (from LinkedIn, website, press coverage).
Include their name and title if available.

### Output Format — JSON with EXACTLY these keys:
{
  "company":          string,
  "leadership_team":  list of {"full_name": string, "title": string},
  "employees":        list of {"full_name": string, "title": string},
  "sources":          list of URLs
}

Return ONLY valid JSON — no markdown, no explanation.
""".strip()

_EVALUATOR_PROMPT = """
You are a strict data quality evaluator for B2B people research.

Evaluate the JSON profile against these rules:
1. **leadership_team**: Must have at least 3 real, named executives with specific titles.
   Reject if names are "Not found" or titles are vague like "Executive".
2. **company**: Must be non-empty and match the target company.
3. **sources**: Must have at least 1 URL.

Score 1-10.
- If score < 8: call handoff_to_agent(agent_name="employee_researcher") with numbered feedback.
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

def run_employee_swarm(state: dict) -> dict:
    """
    Run the Employee Research Swarm.

    Reads from state:  company_name, company_profile
    Writes to state:   employee_profile, all_sources (extended)
    """
    company_name    = state["company_name"]
    company_profile = state.get("company_profile", {})
    industry        = company_profile.get("industry", "")

    print(f"\n{'='*60}")
    print(f"  Employee Swarm — People at: {company_name}")
    print(f"{'='*60}")

    researcher = Agent(
        name="employee_researcher",
        model=PerplexitySonar("sonar"),
        system_prompt=_RESEARCHER_PROMPT,
    )
    evaluator = Agent(
        name="employee_evaluator",
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
        f"Find the current leadership team and key executives at '{company_name}'. "
        "For EACH person, provide:\n"
        "1. Full name\n"
        "2. Exact current job title\n"
        "Cover: CEO, CTO, COO, CFO, President, Co-Founders, and other C-suite leaders.\n"
        "List at least 3-5 people. Only include real, currently employed executives.\n"
        f"Also list any other known employees at '{company_name}' if available.\n"
        f"Industry context: {industry}\n\n"
        "Return the complete JSON with leadership_team, employees, and sources."
    )

    result = swarm(task)

    profile = _get_swarm_result(result)
    sources = profile.get("sources", [])

    state["employee_profile"] = profile
    state.setdefault("all_sources", []).extend(sources)

    leaders   = len(profile.get("leadership_team", []))
    employees = len(profile.get("employees", []))
    nodes_run = [n.node_id for n in result.node_history]
    print(f"  [Employee Swarm] ✅ Done — {leaders} leaders, {employees} employees, "
          f"nodes: {' → '.join(nodes_run)}")
    return state
