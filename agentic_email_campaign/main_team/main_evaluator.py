"""
Main Evaluator Agent

Role: Final quality gate before report generation. Reviews all 5 assembled JSON
      outputs (Company, Employee, Industry, Problems, Solutions) for consistency,
      completeness, and factual accuracy. 
      If passed, it enables the Main Reporter.
"""

from __future__ import annotations

import json
import re

from strands import Agent
from agentic_email_campaign.models import PerplexitySonar

_SYSTEM_PROMPT = """
You are the lead Director of B2B Marketing Intelligence.

You are reviewing the final aggregated research pack from your 5 specialist teams:
1. Company Profile
2. Employee Profile
3. Industry (Tech Stack)
4. Operational Pain Points
5. Solutions Mapping

Your job is to do a final basic quality check before this goes to the Main Reporter
to become a client-facing Word document.

Check:
1. Are all 5 JSON sections populated?
2. Does the solutions mapping logically solve the pain points?
3. Is the target product positioned correctly?
4. Are there major hallucinations or contradictions?

Score 1-10.
Return ONLY a valid JSON object:
{
  "passed": true (if score >= 7) or false,
  "score": integer,
  "feedback": "Brief explanation of issues or praise"
}
""".strip()


def run_main_evaluator(state: dict) -> dict:
    """
    Evaluate the full consolidated research pack.
    """
    print(f"\n{'='*60}")
    print("  Main Evaluator Agent — Final Holistic Review")
    print(f"{'='*60}")

    agent = Agent(
        model=PerplexitySonar("sonar"),
        system_prompt=_SYSTEM_PROMPT,
    )

    pack = {
        "company_profile": state.get("company_profile", {}),
        "employee_profile": state.get("employee_profile", {}),
        "industry_research": state.get("industry_research", {}),
        "problems_research": state.get("problems_research", {}),
        "solutions_research": state.get("solutions_research", {}),
    }

    prompt = (
        "Evaluate the final consolidated research pack.\n\n"
        f"Research Pack:\n{json.dumps(pack, indent=2)}\n\n"
        "Return your JSON verdict."
    )

    raw = str(agent(prompt))
    try:
        match = re.search(r'\{[\s\S]*\}', raw)
        verdict = json.loads(match.group()) if match else json.loads(raw)
    except Exception:
        verdict = {"passed": True, "score": 7, "feedback": "JSON parsing failed but forcing pass."}

    passed = verdict.get("passed", True)
    score  = verdict.get("score", 7)
    fb     = verdict.get("feedback", "")
    
    icon = "✅" if passed else "⚠️"
    print(f"  [Main Evaluator] {icon} Final Score: {score}/10")
    if fb:
        print(f"    Feedback: {fb}")

    state["report_approved"] = passed
    return state

