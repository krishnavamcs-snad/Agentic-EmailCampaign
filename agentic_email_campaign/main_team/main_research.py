"""
Main Research Agent

Role: The first agent in the pipeline. Takes raw user inputs and produces a
      structured research brief that gives each sub-team the context they need.

Model: Perplexity sonar — searches the web for the initial company snapshot.

Output: A context dict injected into `state["initial_context"]` that carries:
  - Confirmed company name, industry, sector
  - Preliminary employee title if found
  - Key facts to seed the sub-team swarms
"""

from __future__ import annotations

import json
import re

from strands import Agent

from agentic_email_campaign.models import PerplexitySonar

_SYSTEM_PROMPT = """
You are the lead research coordinator for a B2B marketing intelligence team.

Your job is to do a rapid initial lookup of a company and produce a structured
research brief that seeds the specialist teams.

From the company name alone, discover:
1. The exact official company name and website
2. Their primary industry and business sector
3. The top 2-3 C-suite or VP-level contacts (name, title)
   — pick the most relevant buyer personas (CFO, CIO, COO, VP Finance, VP Ops, VP IT)
4. The main ERP or business software they currently use, OR the best-fit software
   product to pitch to them based on their industry and size
   (e.g. NetSuite for mid-market, Oracle Fusion for enterprise, SAP for manufacturing)
5. A 'guidance_dossier': 1-2 paragraphs of foundational research on this company
   to guide the downstream specialist teams (what to look for regarding their tech,
   known issues, and overall strategy to prevent hallucination).

Return ONLY a valid JSON object:
{
  "company_name":     "exact official name",
  "company_website":  "official URL",
  "industry":         "primary industry",
  "sector":           "business sector",
  "employee_count":   "size range",
  "key_contacts": [
    {"name": "full name", "title": "exact title"},
    {"name": "full name", "title": "exact title"}
  ],
  "primary_contact": {"name": "full name", "title": "exact title"},
  "product":          "best-fit ERP/software product name",
  "product_category": "ERP | CRM | SCM | HCM | etc.",
  "guidance_dossier": "1-2 paragraphs of foundational research for downstream teams"
}

JSON only — no extra text.
""".strip()


def run_main_research(state: dict) -> dict:
    """
    Run the main research agent to build the initial context brief.

    Reads from state:  company_name (required), employee_name (optional override),
                       product (optional override)
    Writes to state:   initial_context, employee_name, product
    """
    company_name  = state["company_name"]
    # These may be None — the agent will discover them
    employee_name = state.get("employee_name")  
    product       = state.get("product")

    print(f"\n{'='*60}")
    print("  Main Research Agent — Building initial context")
    print(f"{'='*60}")

    agent = Agent(
        model=PerplexitySonar("sonar"),
        system_prompt=_SYSTEM_PROMPT,
    )

    # Build prompt — tell the agent what we already know vs what to discover
    known_parts = []
    if employee_name:
        known_parts.append(f'  Contact (provided): "{employee_name}" — confirm their title')
    if product:
        known_parts.append(f'  Product (provided): "{product}" — confirm category')

    known_text = ("\nAlready known:\n" + "\n".join(known_parts)) if known_parts else \
        "\nDiscover: the most relevant buyer persona (C-suite/VP) and best-fit product."

    prompt = (
        f'Build the initial research brief for company: "{company_name}".'
        f'{known_text}\n\n'
        "Return the complete JSON research brief."
    )

    raw = str(agent(prompt))

    try:
        match = re.search(r'\{[\s\S]*\}', raw)
        context = json.loads(match.group()) if match else json.loads(raw)
    except Exception:
        context = {
            "company_name":  company_name,
            "industry":      "",
            "guidance_dossier": raw[:200],
        }

    state["initial_context"] = context

    # Update state with discovered values (do not overwrite if user provided them)
    state["company_name"] = context.get("company_name", company_name)

    # Discover primary contact if not provided by user
    if not state.get("employee_name"):
        primary = context.get("primary_contact", {})
        state["employee_name"] = primary.get("name", "") or context.get("employee_name", "")

    # Discover product if not provided by user
    if not state.get("product"):
        state["product"] = context.get("product", "")

    print(f"  [Main Research] ✅ Context built")
    print(f"    Company:  {state['company_name']}")
    print(f"    Industry: {context.get('industry')}")
    print(f"    Contact:  {state['employee_name']}")
    print(f"    Product:  {state['product']}")
    if context.get("key_contacts"):
        print(f"    Other contacts discovered:")
        for c in context["key_contacts"]:
            print(f"      • {c.get('name')} — {c.get('title')}")
    return state
