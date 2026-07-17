#!/usr/bin/env python3
import json
import sys
import os
import re
from pathlib import Path
from datetime import datetime

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(REPO_ROOT / ".agent" / "scripts"))

from lib.common import load_json_safe
from lib.llm_client import query_llm

AGENTS_DIR = REPO_ROOT / ".agent" / "agents"
LESSONS_PATH = REPO_ROOT / ".agent" / "rules" / "LESSONS_LEARNED.md"
TASKS_DIR = REPO_ROOT / "tasks"

BREEDER_MODEL = "auto"

def run_breeding():
    """Analyzes history and tasks to propose new specialist agents."""
    print("🧬 Starting Agent Breeding Cycle...")
    
    # 1. Gather Context
    lessons = LESSONS_PATH.read_text() if LESSONS_PATH.exists() else ""
    tasks = []
    if TASKS_DIR.exists():
        for f in TASKS_DIR.glob("*.md"):
            tasks.append(f.read_text()[:500]) # Sample each task
            
    # Cold Start: If no tasks and few lessons, scan the repo to understand the tech stack
    repo_context = ""
    if not tasks and len(lessons) < 500:
        print("  ❄️ Cold Start detected. Scanning repository structure...")
        # Get a list of file extensions to guess the tech stack
        extensions = set()
        for f in REPO_ROOT.rglob("*"):
            if f.is_file() and "." in f.name:
                ext = f.suffix
                if ext not in [".git", ".pyc", ".png", ".jpg"]:
                    extensions.add(ext)
        repo_context = f"Detected tech stack (extensions): {', '.join(list(extensions)[:20])}"
        print(f"  🔍 {repo_context}")

    # Recursive search for existing agents
    existing_agents = []
    for f in AGENTS_DIR.rglob("*.md"):
        existing_agents.append(f"{f.parent.name}/{f.name}")
    
    print(f"  🔍 Analyzing {len(tasks)} tasks and {len(existing_agents)} existing agents...")
    
    # 2. Ask LLM to find gaps
    prompt = f"""You are the Meta-Architect Agent Breeder.
Analyze the current repository state and identify if there is a need for a NEW specialist agent.

EXISTING AGENTS (path/name):
{', '.join(existing_agents)}

RECENT LESSONS:
{lessons[-2000:]}

RECENT TASKS (SAMPLES):
{chr(10).join(tasks[-10:])}

REPO CONTEXT (Cold Start):
{repo_context}

GOAL:
Find a domain that is currently handled by generic agents but is complex enough to warrant a specialist.

CRITICAL RULE: 
DO NOT create an agent if its domain is already covered by an existing agent. 
If an existing agent can be slightly improved instead, mention that in reasoning but set 'need_new_agent' to false.
Check for semantic overlaps (e.g. 'rest-api-designer' vs 'api-architect').

OUTPUT FORMAT (JSON ONLY):
{{
  "need_new_agent": boolean,
  "reasoning": "string",
  "agent_name": "kebab-case-name",
  "description": "string",
  "domains": ["list"],
  "skills": ["list"],
  "initial_instructions": "string"
}}
"""
    
    response, stats = query_llm(prompt, BREEDER_MODEL, system_prompt="Output ONLY valid JSON.")
    
    try:
        # Clean up JSON if LLM added markdown blocks
        clean_json = re.search(r"\{.*\}", response, re.DOTALL).group(0)
        proposal = json.loads(clean_json)
        
        if proposal.get("need_new_agent"):
            create_agent_proposal(proposal)
        else:
            print("✨ No new agent specializations identified at this time.")
            
    except Exception as e:
        print(f"❌ Failed to parse breeding proposal: {e}")
        print("Raw Response:", response)

def enrich_agent_profile(proposal) -> str:
    """Enriches the proposed agent profile using the Prompt Specialist rules."""
    name = proposal["agent_name"]
    description = proposal["description"]
    domains = proposal["domains"]
    skills = proposal["skills"]
    initial_instructions = proposal.get("initial_instructions", "")

    print("🎭 Running Prompt Specialist Enrichment Phase...")
    
    prompt = f"""You are the Lead Prompt Specialist (@prompt-specialist).
Your task is to take a proposed new agent configuration and write its complete, premium system prompt file in Markdown format.

AGENT DETAILS:
Name: {name}
Description: {description}
Domains: {', '.join(domains)}
Skills: {', '.join(skills)}
Initial Instructions Context: {initial_instructions}

Follow these guidelines to make the prompt extremely precise, robust, and secure:
1. Include frontmatter with:
   - name: {name}
   - description: {description}
   - domains: (comma-separated list of domains, without square brackets)
   - skills: (comma-separated list of skills, without square brackets, including clean-code, systematic-debugging, multica-mcp, multica-cli)
   - hierarchy: (reports_to: backend-lead, delegates_to: [])
   - tools: (comma-separated list of tools, without square brackets, e.g., Read, Grep, Glob, Bash, Write, Edit, Agent, skills_load, skills_search, knowledge_read, tasks_submit)
   - model: L2
   - profile: universal
2. Structure the body with:
   - Header with a professional description of the role.
   - 🚨 TRIGGER CONDITIONS: A markdown table detailing the exact signals and triggers for activation.
   - 🛠 Operational Protocol: Phase-by-phase execution instructions (Phase 1: Audit/Reproduce, Phase 2: Design/Isolate, Phase 3: Validation/Verify).
   - ⚖️ Boundaries & Rules: What they do and what they MUST NOT do (explicit boundaries).
   - 🛡️ System Prompt Protection (Red-Teaming): Delimiters, anti-bypass rules, and execution isolation rules to prevent prompt injections.
   - 📊 Measured Quality Metrics: Key metrics table (latency, compliant rates, parity).
   - 📤 Output Protocol: The mandatory output-bridge checklist rules.

Provide ONLY the raw markdown content. Do NOT wrap it in markdown code blocks (e.g. do not put ```markdown at the start/end).
"""

    try:
        response, stats = query_llm(prompt, BREEDER_MODEL, system_prompt="You are a senior Prompt Engineer. Output only the raw markdown content.")
        if response and not response.startswith("❌"):
            # Strip markdown block wraps if model generated them anyway
            content = response.strip()
            if content.startswith("```markdown"):
                content = content[11:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            return content.strip()
    except Exception as e:
        print(f"⚠️ Enrichment failed: {e}. Using baseline template.")
    
    return ""

def create_agent_proposal(proposal):
    """Creates a new agent file based on the proposal."""
    name = proposal["agent_name"]
    file_path = AGENTS_DIR / f"{name}.md"
    
    if file_path.exists():
        print(f"⚠️ Agent '{name}' already exists. Skipping.")
        return
        
    # Attempt to enrich via Prompt Specialist
    content = enrich_agent_profile(proposal)
    
    if not content:
        print("  ⚠️ Using fallback baseline template...")
        content = f"""---
name: {name}
description: {proposal['description']}
domains: {', '.join(proposal['domains'])}
skills: {', '.join(proposal['skills'])}
---

# {name.replace('-', ' ').title()} (@{name})

{proposal['initial_instructions']}

## Core Responsibilities

1. **Focus Domain**: Specialization in {proposal['domains'][0]}.
2. **Context Awareness**: Use lessons from {LESSONS_PATH.name}.

## Operational Standards

- Follow @[skills/clean-code].
- Document specialized patterns in ARCHITECTURE.md.
"""
    
    with open(file_path, "w") as f:
        f.write(content)
        
    print(f"🎉 New agent bred: {file_path}")
    print(f"  Reason: {proposal['reasoning']}")

    # Run the intelligence quality benchmark suite to verify no regression occurred
    print("🚀 Running Intelligence Quality Benchmark to verify the system's compliance...")
    try:
        import subprocess
        bench_script = REPO_ROOT / ".agent" / "scripts" / "qa" / "intelligence_benchmark.py"
        if bench_script.exists():
            subprocess.run([sys.executable, str(bench_script)], check=True)
            print("✅ Intelligence Quality Benchmark passed successfully!")
        else:
            print("⚠️ Intelligence benchmark script not found.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Intelligence Quality Benchmark failed: {e}")

if __name__ == "__main__":
    run_breeding()
