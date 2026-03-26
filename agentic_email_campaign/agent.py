"""
Marketing Email Generation — Pipeline Orchestrator
Built with Strands Agents SDK

Architecture:
  ┌─────────────────────────────────────────────────────┐
  │  MAIN TEAM                                          │
  │                                                     │
  │  1. Main Research Agent (sonar)                 │
  │     Builds initial context brief from user inputs   │
  │                    ↓                                │
  │  ┌─────────────────────────────────────────────┐    │
  │  │  Company Swarm: researcher ↔ evaluator      │    │
  │  └─────────────────────────────────────────────┘    │
  │                    ↓                                │
  │  2. Main Evaluator Agent (sonar)                    │
  │     Cross-validates each swarm output               │
  │                    ↓ approved                       │
  │  ┌─────────────────────────────────────────────┐    │
  │  │  Employee Swarm: researcher ↔ evaluator     │    │
  │  └─────────────────────────────────────────────┘    │
  │         ↓ Main Evaluator → Industry Swarm           │
  │         ↓ Main Evaluator → Solutions Swarm          │
  │                    ↓ all approved                   │
  │  3. Main Reporter Agent (Bedrock Claude)            │
  │     Generates Word case study document              │
  └─────────────────────────────────────────────────────┘

Usage:
    python -m agentic_email_campaign.agent \\
        --company  "Sysco Corporation" \\
        --employee "Kevin Hourican" \\
        --product  "NetSuite"

    Or import:
        from agentic_email_campaign.agent import run
        state = run("Acme Corp", "John Smith", "NetSuite")
"""

from __future__ import annotations

import argparse
import os
import sys

# Add parent directory to sys.path so we can import 'agentic_email_campaign' 
# smoothly even if someone runs `python agent.py` directly from inside this folder.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from agentic_email_campaign.main_team.main_research  import run_main_research
from agentic_email_campaign.main_team.main_evaluator import run_main_evaluator
from agentic_email_campaign.main_team.main_reporter  import run_main_reporter

from agentic_email_campaign.teams.company_team   import run_company_swarm
from agentic_email_campaign.teams.employee_team  import run_employee_swarm
from agentic_email_campaign.teams.industry_team  import run_industry_swarm
from agentic_email_campaign.teams.problems_team  import run_problems_swarm
from agentic_email_campaign.teams.solutions_team import run_solutions_swarm

load_dotenv()

MAX_TEAM_RETRIES = 2  # Max times main evaluator can send a team back for a redo


# ─────────────────────────────────────────────────────────────────────────────
# Human Review checkpoint
# ─────────────────────────────────────────────────────────────────────────────

def _human_review(state: dict) -> dict:
    company   = state.get("company_profile", {})
    employee  = state.get("employee_profile", {})
    industry  = state.get("industry_research", {})
    solutions = state.get("solutions_research", {})
    headwinds = [h.get("title", "") for h in industry.get("headwinds", [])]
    mapped    = [s.get("headwind_title", "") for s in solutions.get("headwind_solutions", [])]

    sep = "=" * 60
    print(f"\n{sep}")
    print("  HUMAN REVIEW — Final Research Summary")
    print(sep)
    print(f"  Company:          {company.get('name', state['company_name'])}")
    print(f"  Industry:         {company.get('industry', 'Unknown')}")
    print(f"  Contact:          {employee.get('full_name', state['employee_name'])} "
          f"({employee.get('current_title', 'Unknown title')})")
    print(f"  Product:          {state['product']}")
    print(f"  Headwinds found:  {len(headwinds)}")
    for hw in headwinds:
        print(f"    • {hw}")
    print(f"  Solutions mapped: {len(mapped)}/{len(headwinds)}")
    print(f"  Total sources:    {len(state.get('all_sources', []))}")
    print(sep)

    choice            = input("\nApprove report generation? [y/N]: ").strip().lower()
    state["report_approved"] = choice in ("y", "yes")
    print("  [Human Review] " + ("✅ Approved" if state["report_approved"] else "❌ Rejected"))
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run(
    company_name:  str,
    employee_name: str | None = None,
    product:       str | None = None,
    output_dir:    str = "./reports",
) -> dict:
    """
    Execute the full multi-agent marketing research pipeline.

    Args:
        company_name:  Target company name (only required input)
        employee_name: Optional — specific contact to research.
                       If omitted, the Main Research Agent discovers key contacts.
        product:       Optional — ERP/software product to position.
                       If omitted, the Main Research Agent selects the best fit.
        output_dir:    Directory to save the Word document

    Returns:
        Final state dict with all research data and report_path.
    """
    if not os.environ.get("PPLX_API_KEY"):
        raise EnvironmentError("PPLX_API_KEY is not set. Add it to your .env file.")

    state: dict = {
        "company_name":       company_name,
        "employee_name":      employee_name,   # None → discovered by main_research
        "product":            product,          # None → discovered by main_research
        "output_dir":         output_dir,
        # Main Team
        "initial_context":    None,
        # Sub-team results
        "company_profile":    None,
        "employee_profile":   None,
        "industry_research":  None,
        "solutions_research": None,
        # Control
        "all_sources":        [],
        "report_approved":    None,
        "report_path":        None,
    }

    sep = "=" * 60
    print(f"\n🚀  Marketing Research Pipeline — Strands Agents SDK")
    print(sep)
    print(f"  Company:  {company_name}")
    print(f"  Contact:  {employee_name if employee_name else '(to be discovered)'}")
    print(f"  Product:  {product if product else '(to be discovered)'}")
    print(f"  Output:   {output_dir}")
    print(sep)


    # ── Step 1: Main Research Agent — build initial context ──────────────────
    state = run_main_research(state)

    # ── Step 2–6: Specialist Research Teams ─────────────────────────────────
    state = run_company_swarm(state)
    state = run_employee_swarm(state)
    state = run_industry_swarm(state)
    state = run_problems_swarm(state)
    state = run_solutions_swarm(state)

    # ── Step 7: Main Evaluator (Holistic Quality Check) ─────────────────────
    state = run_main_evaluator(state)

    # ── Step 8: Human-in-the-loop review ────────────────────────────────────
    state = _human_review(state)

    # ── Step 7: Main Reporter Agent — generate Word document ────────────────
    state = run_main_reporter(state)

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{sep}")
    print("✅  Pipeline Complete")
    if state.get("report_path"):
        print(f"  📄 Report: {state['report_path']}")
    print(f"  🔗 Total sources: {len(state.get('all_sources', []))}")
    print(sep + "\n")

    return state


# ─────────────────────────────────────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Marketing Email Generation — Strands Multi-Agent Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agentic_email_campaign.agent \\
      --company "Sysco Corporation" \\
      --employee "Kevin Hourican" \\
      --product "NetSuite"

  python -m agentic_email_campaign.agent \\
      --company "Acuity Brands" \\
      --employee "Neil Ashe" \\
      --product "Oracle Fusion" \\
      --output "./my_reports"
        """,
    )
    parser.add_argument("--company",  required=True, help="Target company name")
    parser.add_argument(
        "--employee", default=None,
        help="(Optional) Target employee / contact name. "
             "If omitted, the Main Research Agent discovers the key contact."
    )
    parser.add_argument(
        "--product", default=None,
        help="(Optional) ERP product to position (e.g. \"NetSuite\", \"Oracle Fusion\"). "
             "If omitted, the Main Research Agent selects the best fit."
    )
    parser.add_argument("--output", default="./reports",
                        help="Output directory for the Word report (default: ./reports)")

    args = parser.parse_args()
    run(
        company_name=args.company,
        employee_name=args.employee,
        product=args.product,
        output_dir=args.output,
    )
