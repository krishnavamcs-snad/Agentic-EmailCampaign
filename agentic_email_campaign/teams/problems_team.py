"""
Problems Research Team — Swarm

A Strands Swarm that reads the company's tech stack and identifies
operational and industry-specific problems they face.

Agents:
    problems_researcher  — sonar, finds actual documented problems
    problem_finder       — sonar, deduces problems from tech stack if none found
    problems_evaluator   — sonar, validates specificity of pain points

Public API:
    run_problems_swarm(state: dict) -> dict
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
You are a B2B enterprise business analyst identifying operational pain points.

You will receive a company's profile and their current tech stack.
Your job is to identify real, specific problems this company faces in their
industry that stem from gaps, limitations, or fragmentation in their current tech stack.

### Problem Categories to investigate:
1. **Financial & Reporting Pain** — manual reconciliation, slow close cycles, fragmented data
2. **Operational Inefficiency** — disconnected systems, manual workflows, lack of automation
3. **Inventory / Supply Chain** — visibility gaps, forecasting errors, vendor management
4. **Customer Management** — CRM gaps, poor visibility into pipeline or billing
5. **HR & Workforce** — manual onboarding, compliance tracking, payroll inefficiencies
6. **Data & Analytics** — no real-time dashboards, siloed data, poor forecasting
7. **Scalability** — legacy systems that cannot grow with the business

### Output Format — JSON with EXACTLY these keys:
{
  "company":          string,
  "problems_summary": string (2-3 sentences on the overall pain landscape),
  "problems":         list of {
                        "title": string,
                        "description": string (specific to this company),
                        "business_impact": string (cost, time, or risk impact)
                      },
  "sources":          list of URLs
}

Identify at least 4 specific problems based on real web data. 
CRITICAL FALLBACK: If you CANNOT find actual documented problems for this specific company, 
you MUST deduce and predict 4 highly probable operational problems they face based strictly 
on their industry, sector, and the gaps or fragmentation in their current tech stack.

Return ONLY valid JSON — no markdown, no explanation.
""".strip()

_FINDER_PROMPT = """
You are a brilliant B2B software consultant. The primary researcher could not find 
publicly documented pain points for this company on the web.

Your job is to strictly DEDUCE and PREDICT the operational problems this company 
HIGHLY LIKELY faces based on their industry, sector, and the gaps or fragmentation 
in their current tech stack.

Look at the tech stack provided. Are there missing systems? Are they using outdated 
legacy tools? Do they lack an integrated CRM, HRIS, or ERP?

### Output Format — JSON with EXACTLY these keys:
{
  "company":          string,
  "problems_summary": string (2-3 sentences on the PREDICTED pain landscape based on tech gaps),
  "problems":         list of {
                        "title": string,
                        "description": string (specific, logical deduction based on their tech stack),
                        "business_impact": string (cost, time, or risk impact)
                      },
  "sources":          ["Deduced from Tech Stack Analysis"]
}

Deduce at least 4 highly probable problems. Return ONLY valid JSON — no markdown.
""".strip()


_EVALUATOR_PROMPT = """
You are a strict quality evaluator for B2B problem identification.

Evaluate the problems JSON against these rules:
1. **problems**: Must have at least 4 entries with specific pain points.
2. **business_impact**: Must be clearly stated for each problem.
3. **problems_summary**: Must be specific to this company, not generic boilerplate.

CRITICAL FALLBACK RULE:
If the problems_researcher returns an empty list, OR if they hallucinate generic problems
because they couldn't find real ones, DO NOT approve it. 
Instead, you MUST hand off to the problem_finder agent to deduce the problems:
→ call handoff_to_agent(agent_name="problem_finder") and tell it to deduce the problems from the tech stack.

Score 1-10.
- If score < 8: call handoff_to_agent(agent_name="problems_researcher" OR "problem_finder") with feedback.
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

def run_problems_swarm(state: dict) -> dict:
    """
    Run the Problems Research Swarm.

    Reads from state:  company_name, company_profile, industry_research (tech stack)
    Writes to state:   problems_research, all_sources (extended)
    """
    company_name      = state["company_name"]
    company_profile   = state.get("company_profile", {})
    industry_research = state.get("industry_research", {})

    print(f"\n{'='*60}")
    print(f"  Problems Swarm — {company_name}")
    print(f"{'='*60}")

    researcher = Agent(
        name="problems_researcher",
        model=PerplexitySonar("sonar"),
        system_prompt=_RESEARCHER_PROMPT,
    )
    finder = Agent(
        name="problem_finder",
        model=PerplexitySonar("sonar"),
        system_prompt=_FINDER_PROMPT,
    )
    evaluator = Agent(
        name="problems_evaluator",
        model=PerplexitySonar("sonar"),
        system_prompt=_EVALUATOR_PROMPT,
    )

    swarm = Swarm(
        [researcher, finder, evaluator],
        entry_point=researcher,
        max_handoffs=6,
        max_iterations=8,
        repetitive_handoff_detection_window=4,
        repetitive_handoff_min_unique_agents=2,
    )

    task = (
        f"Identify the key operational and industry problems faced by '{company_name}'. "
        f"Industry: {company_profile.get('industry', '')}. "
        f"Sector: {company_profile.get('sector', '')}.\n\n"
        f"Their current KNOWN tech stack:\n{json.dumps(industry_research, indent=2)}\n\n"
        "Start with problems_researcher. If no real documented problems are found, "
        "evaluator should pass to problem_finder to deduce them based on tech stack gaps."
    )

    result = swarm(task)

    research  = _get_swarm_result(result)
    sources   = research.get("sources", [])

    state["problems_research"] = research
    state.setdefault("all_sources", []).extend(sources)

    count     = len(research.get("problems", []))
    nodes_run = [n.node_id for n in result.node_history]
    print(f"  [Problems Swarm] ✅ Done — {count} problems found, "
          f"nodes: {' → '.join(nodes_run)}")
    return state
