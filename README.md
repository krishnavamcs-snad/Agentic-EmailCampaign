# Agentic Email Campaign 🚀

A multi-agent system for marketing email generation using the Strands Pipeline architecture. This system orchestrates specialized research teams (Company, Employee, Industry, Problems, Solutions) to gather robust context, evaluates findings, and constructs highly personalized marketing emails.

## 📋 Prerequisites

- **Python 3.9+**
- A **Perplexity API Key** for the research agents to pull relevant data.

## 🛠️ Setup & Installation

**1. Create & Activate a Virtual Environment**
It is highly recommended to isolate dependencies in a virtual environment (`.venv`).
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**2. Install Dependencies**
With the virtual environment activated, install the require packages:
```bash
pip install -r agentic_email_campaign/requirements.txt
```

**3. Configure Environment Variables**
Create a `.env` file at the root of the project to store your Perplexity API Key securely:
```env
PPLX_API_KEY=your-api-key-here
```

## 🚀 Usage

Ensure your virtual environment is activated before running the scripts! It is also recommended to run the scripts from inside the `agentic_email_campaign` folder.

```bash
cd agentic_email_campaign
```

### Running the Full Generation Pipeline
The main entry point (`run.py`) kicks off the complete email campaign generation.

```bash
# Basic usage targeting a specific company
python run.py --company "Dimension Consulting"

# Advanced usage targeting an employee and specific product positioning
python run.py --company "Acme Corp" --employee "John Smith" --product "NetSuite"
```
*Generated reports will default to being saved in a `./reports` directory within that folder.*

### Testing Individual Agent Teams
If you are developing or debugging, you can isolate and run specific agent swarms using (`run_team.py`):

```bash
# Test the company research team:
python run_team.py --company "Dimension Consulting" --team company

# Test the employee research team:
python run_team.py --company "Dimension Consulting" --team employee --employee "John Smith"
```

**Available Teams:** `company`, `employee`, `industry`, `problems`, `solutions`.