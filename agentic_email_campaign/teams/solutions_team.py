"""
Solutions Research Team — Swarm

A Strands Swarm that reads a company's identified problems and maps them
to specific NetSuite and AI solutions.

Agents:
    solutions_researcher — sonar, maps NetSuite/AI tools to problems
    solutions_evaluator  — sonar, validates specificity of the solutions

Public API:
    run_solutions_swarm(state: dict) -> dict
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
You are a B2B enterprise solutions architect specialising in NetSuite and AI technologies.

You will receive a list of operational problems a target company is facing.
Your job is to solve these problems.

For EACH problem identified, provide a concrete solution using:
1. Specific NetSuite ERP modules (e.g. SuiteAnalytics, ARM, OneWorld, SuiteCommerce) AND/OR
2. Specific AI/automation technologies (e.g. AI invoice matching, predictive forecasting, chatbots)

### Output Format — JSON with EXACTLY these keys:
{
  "company":           string,
  "solutions_summary": string (2-3 sentences summarizing the vision),
  "mapped_solutions":  list of {
                         "problem_title": string (matching the input problem),
                         "recommended_solution": string (specific NetSuite/AI tool),
                         "how_it_solves_it": string (specific mechanism),
                         "business_value": string
                       },
  "sources":           list of URLs
}

Return ONLY valid JSON — no markdown, no explanation.
""".strip()

_EVALUATOR_PROMPT = """
You are a strict quality evaluator for B2B solutions mapping.

Evaluate the solutions JSON against these rules:
1. **mapped_solutions**: Must provide a specific NetSuite module or AI tool
   for every problem. Reject vague solutions like "use NetSuite".
2. **how_it_solves_it**: Must describe the actual mechanism of the solution.
3. **solutions_summary**: Must be an inspiring, tailored vision.

Score 1-10.
- If score < 8: call handoff_to_agent(agent_name="solutions_researcher") with feedback.
- If score >= 8: return ONLY the approved JSON as your final response.
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

def run_solutions_swarm(state: dict) -> dict:
    """
    Run the Solutions Mapping Swarm.

    Reads from state:  company_name, problems_research
    Writes to state:   solutions_research, all_sources (extended)
    """
    company_name      = state["company_name"]
    problems_research = state.get("problems_research", {})

    print(f"\n{'='*60}")
    print(f"  Solutions Swarm — {company_name}")
    print(f"{'='*60}")

    researcher = Agent(
        name="solutions_researcher",
        model=PerplexitySonar("sonar"),
        system_prompt=_RESEARCHER_PROMPT,
    )
    evaluator = Agent(
        name="solutions_evaluator",
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
        f"Solve the identified problems for '{company_name}'.\n\n"
        f"Identified Problems:\n{json.dumps(problems_research, indent=2)}\n\n"
        "For each problem, recommend a specific NetSuite module and/or AI technology "
        "that solves it. Return the complete mapped_solutions JSON."
    )

    result = swarm(task)

    research  = _get_swarm_result(result)
    sources   = research.get("sources", [])

    state["solutions_research"] = research
    state.setdefault("all_sources", []).extend(sources)

    count     = len(research.get("mapped_solutions", []))
    nodes_run = [n.node_id for n in result.node_history]
    print(f"  [Solutions Swarm] ✅ Done — {count} solutions mapped, "
          f"nodes: {' → '.join(nodes_run)}")
    return state
