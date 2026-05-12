import os
import re

def check_prompt(filepath):
    """
    Analyzes a prompt file for effectiveness and structure.
    """
    with open(filepath, 'r') as f:
        content = f.read().lower()

    errors = []
    warnings = []
    
    # 1. Check for Persona/Role
    if not any(word in content for word in ['you are', 'persona', 'role', 'act as']):
        warnings.append("Prompt might be missing a clear persona or role definition (e.g., 'You are an expert...').")

    # 2. Check for Constraints
    if not any(word in content for word in ['constraint', 'rule', 'never', 'must', 'always']):
        warnings.append("Prompt lacks explicit constraints or rules. This can lead to hallucinations or off-topic responses.")

    # 3. Check for formatting instructions
    if not any(word in content for word in ['format', 'markdown', 'json', 'xml', 'output as']):
        warnings.append("Prompt doesn't specify an output format. Structured output is usually more reliable.")

    # 4. Check for length (too short might be vague)
    if len(content.split()) < 50:
        warnings.append("Prompt is very short (< 50 words). It might lack sufficient context for complex tasks.")

    return errors, warnings

def scan_prompts(directory=".agent/agents"):
    if not os.path.exists(directory):
        print(f"Directory {directory} not found.")
        return

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.md'):
                path = os.path.join(root, file)
                errors, warnings = check_prompt(path)
                
                if errors or warnings:
                    print(f"\nIssues in {path}:")
                    for err in errors:
                        print(f"  [ERROR] {err}")
                    for warn in warnings:
                        print(f"  [WARN] {warn}")

if __name__ == "__main__":
    scan_prompts()
