"""
Entry point — run from inside the agentic_email_campaign/ folder:

    python run.py --company "Dimension Consulting"
    python run.py --company "Acme Corp" --employee "John Smith" --product "NetSuite"
"""

import sys
import os

# Add the parent directory to sys.path so the package can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentic_email_campaign.agent import run
import argparse

parser = argparse.ArgumentParser(description="Marketing Email Generation — Strands Pipeline")
parser.add_argument("--company",  required=True, help="Target company name")
parser.add_argument("--employee", default=None,  help="(Optional) Target contact name")
parser.add_argument("--product",  default=None,  help="(Optional) ERP product to position")
parser.add_argument("--output",   default="./reports", help="Output directory (default: ./reports)")
args = parser.parse_args()

run(
    company_name=args.company,
    employee_name=args.employee,
    product=args.product,
    output_dir=args.output,
)
