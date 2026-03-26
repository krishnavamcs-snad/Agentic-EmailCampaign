import argparse
import os
import subprocess
import json
import boto3
from pathlib import Path

from dotenv import load_dotenv
from strands import Agent, tool

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Tools for the Presentation Agent
# ─────────────────────────────────────────────────────────────────────────────

@tool
def write_file(filename: str, content: str) -> str:
    """Writes textual content to a file. Use this to save presentation.js."""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {filename}"
    except Exception as e:
        return f"Error writing file: {e}"


@tool
def run_command(command: str) -> str:
    """Runs a shell command and returns the output (stdout/stderr).
    
    Use this to run your generated code (e.g., 'node presentation.js')
    and your visual QA pipeline ('soffice', 'pdftoppm').
    """
    try:
        print(f"  [Agent Executing]: {command}")
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=120
        )
        output = result.stdout + "\n" + result.stderr
        output = output.strip()
        if result.returncode != 0:
            return f"Command exited with code {result.returncode}:\n{output}"
        return output if output else "Command completed with no output."
    except Exception as e:
        return f"Error running command: {e}"


@tool
def read_file(filename: str) -> str:
    """Reads the textual content from a local file."""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# Pre-processing Helpers
# ─────────────────────────────────────────────────────────────────────────────

def extract_content(file_path: str) -> str:
    """Uses markitdown to extract text if it's a docx/pdf/xlsx, otherwise returns raw text."""
    path = Path(file_path)
    if path.suffix.lower() in [".docx", ".pdf", ".pptx", ".xlsx", ".csv"]:
        print(f"📦 Auto-extracting binary content from '{path.name}' using markitdown...")
        result = subprocess.run(
            f'python -m markitdown "{file_path}"', 
            shell=True, capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        print(f"⚠️ markitdown failed (code {result.returncode}), returning raw error...")
        return f"Warning: Failed to extract document.\n{result.stderr}"
    
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Warning: Failed to read text file. {e}"


# ─────────────────────────────────────────────────────────────────────────────
# Core Agent Builder
# ─────────────────────────────────────────────────────────────────────────────

def run_presentation_agent(input_path: str):
    """
    Initializes and runs the AWS Bedrock Claude agent to build the presentation.
    
    NEW APPROACH (Dynamic & Intelligent):
    - Uses DYNAMIC_SYSTEM_PROMPT.md which emphasizes content analysis
    - Agent generates pptxgenjs code from scratch for each slide
    - No hardcoded templates — purely adaptive to report content
    - Agent decides layout, structure, and visual formats intelligently
    
    PREVIOUS APPROACH (Template-Based):
    - Used BEDROCK_SYSTEM_PROMPT.md + PPTX_MASTER_DOCUMENTATION.md
    - Contained hardcoded template functions (titleSlide, statsSlide, etc.)
    - Less flexible, more cookie-cutter results
    - Files kept for reference: BEDROCK_SYSTEM_PROMPT.md, PPTX_MASTER_DOCUMENTATION.md
    """
    # Use new dynamic system prompt that focuses on analysis and adaptive generation
    dynamic_prompt_path = Path("DYNAMIC_SYSTEM_PROMPT.md")
    
    if not dynamic_prompt_path.exists():
        print("Error: DYNAMIC_SYSTEM_PROMPT.md not found in the current directory.")
        print("Ensure you're running from the project root.")
        return

    # Load the dynamic system prompt (no hardcoded templates)
    system_prompt = dynamic_prompt_path.read_text(encoding="utf-8")
    
    print("\n🚀 Initializing Dynamic Presentation Agent...")
    print("   - Loaded Analysis-Driven System Prompt")
    print("   - Agent will adapt to report structure dynamically")
    print("   - No hardcoded templates — pure intelligence")
    print("   - Injecting Shell and File tools")
    print("   - Model: Claude Sonnet 4.5 (AWS Bedrock us cross-region profile)\n")

    agent = Agent(
        name="presentation_agent",
        # Cross-region inference profile required for on-demand throughput
        model="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        system_prompt=system_prompt,
        tools=[write_file, read_file, run_command],
    )
    
    print(f"🎯 Objective: Generate presentation for '{input_path}'\n")
    print("-" * 60)
    
    # Pre-parse the file into Markdown using Python locally so the agent 
    # gets the clean text immediately without needing to invoke extra tools.
    document_content = extract_content(input_path)
    
    # Generate a smart output name instead of generic "output.pptx"
    input_stem = Path(input_path).stem
    output_pptx = f"{input_stem}_presentation.pptx"
    
    user_prompt = (
        f"You are receiving a business document extracted from '{input_path}'.\n\n"
        f"=== DOCUMENT CONTENT ===\n"
        f"{document_content}\n"
        f"=== END DOCUMENT ===\n\n"
        "**YOUR TASK:**\n"
        "1. **ANALYZE**: Deeply understand this document's structure, key messages, data, and narrative flow\n"
        "2. **DESIGN**: Plan an adaptive presentation structure that tells the story effectively\n"
        "3. **GENERATE**: Write pptxgenjs JavaScript code dynamically (no templates) that creates slides "
        "tailored to THIS specific content\n"
        "4. **EXECUTE**: Run the code to generate the .pptx file\n"
        "5. **VERIFY**: Perform visual QA on the output\n\n"
        f"**CRITICAL REQUIREMENTS:**\n"
        f"- Save the final .pptx as '{output_pptx}' (not 'output.pptx')\n"
        f"- Adapt layout and structure to the document content (no cookie-cutter templates)\n"
        f"- Convert data to visual formats (stats → cards, trends → charts, lists → bullets)\n"
        f"- Vary slide layouts — avoid repetition\n"
        f"- Complete visual QA before declaring success\n"
    )
    
    # Run the agent (this will trigger tool loops)
    agent(user_prompt)
    
    # Verify the file was created
    output_path = Path(output_pptx)
    if output_path.exists():
        print("\n" + "=" * 60)
        print(f"✅ Presentation generated: {output_path.absolute()}")
        print("=" * 60)
    else:
        print("\n⚠️ Warning: Expected output file not found.")


if __name__ == "__main__":
    # =========================================================================
    # OPTION 1: HARDCODE YOUR FILE PATH HERE
    # Paste your .docx file path between the quotes below.
    # =========================================================================
    HARDCODED_REPORT_PATH = ""


    parser = argparse.ArgumentParser(description="Run the Presentation Agent")
    parser.add_argument("--input", required=False, help="Path to the source file (e.g., data.json, input.docx)")
    args = parser.parse_args()
    
    # 1. Check if they used the CLI argument
    if args.input:
        input_filepath = args.input
    # 2. Check if they hardcoded the path above
    elif HARDCODED_REPORT_PATH:
        input_filepath = HARDCODED_REPORT_PATH
    # 3. Otherwise, interactively ask for it
    else:
        print("\n🤖 Presentation Agent Ready.")
        input_filepath = input("Please paste the full path to your document/report: ").strip()
        
    if input_filepath:
        run_presentation_agent(input_filepath)
    else:
        print("No file path provided. Exiting.")
