"""
Main Reporter Agent

Role: Final agent in the pipeline. Receives all validated research from the
      four sub-team Swarms and generates the professional Word case study.

Model: Strands default (AWS Bedrock Claude) — uses generate_docx_report tool.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from strands import Agent

from agentic_email_campaign.tools import generate_docx_report

_SYSTEM_PROMPT = """
You are a senior B2B marketing consultant who creates compelling case study documents.

You have access to the generate_docx_report tool. Use it to produce a professional
Word document (.docx) from the validated research data you receive.

Pass all FIVE research sections as JSON strings to the tool's parameters.
Use the exact output_path value you are given — do not change it.
""".strip()


def run_main_reporter(state: dict) -> dict:
    """
    Generate the final Word document case study.

    Reads from state:  company_profile, employee_profile, industry_research,
                       problems_research, solutions_research, report_approved, output_dir
    Writes to state:   report_path
    """
    if not state.get("report_approved"):
        print("\n  [Main Reporter] Skipped — not approved.")
        return state

    company_name = state.get("company_profile", {}).get("name", state["company_name"])
    safe_name    = re.sub(r"[^\w\-]", "_", company_name)
    timestamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir   = state.get("output_dir", "./reports")
    output_path  = f"{output_dir}/{safe_name}_case_study_{timestamp}.docx"

    print(f"\n{'='*60}")
    print("  Main Reporter Agent — Generating Word document")
    print(f"  → {output_path}")
    print(f"{'='*60}")

    agent = Agent(system_prompt=_SYSTEM_PROMPT, tools=[generate_docx_report])

    prompt = (
        "Generate the marketing case study Word document.\n"
        f"Save it to: {output_path}\n\n"
        f"Company Profile JSON:\n{json.dumps(state.get('company_profile', {}))}\n\n"
        f"Employee Profile JSON:\n{json.dumps(state.get('employee_profile', {}))}\n\n"
        f"Industry Research JSON:\n{json.dumps(state.get('industry_research', {}))}\n\n"
        f"Problems Research JSON:\n{json.dumps(state.get('problems_research', {}))}\n\n"
        f"Solutions Research JSON:\n{json.dumps(state.get('solutions_research', {}))}"
    )

    agent(prompt)
    state["report_path"] = output_path
    print(f"  [Main Reporter] ✅ Report saved: {output_path}")
    return state
