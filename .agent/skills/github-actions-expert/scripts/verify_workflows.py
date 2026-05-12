import os
import yaml
import sys

def check_workflow(filepath):
    """
    Scans a GitHub Actions workflow for security and performance issues.
    """
    errors = []
    warnings = []
    
    try:
        with open(filepath, 'r') as f:
            workflow = yaml.safe_load(f)
    except Exception as e:
        return [f"Error parsing {filepath}: {e}"], []

    # 1. Check for 'on: push' without filters
    triggers = workflow.get('on', {})
    if triggers == 'push' or (isinstance(triggers, dict) and 'push' in triggers and not triggers['push']):
        warnings.append("Triggers on 'push' without branch or path filters. This may cause unnecessary builds.")

    # 2. Check for hardcoded secrets/tokens in env (obvious ones)
    jobs = workflow.get('jobs', {})
    for job_name, job_data in jobs.items():
        steps = job_data.get('steps', [])
        for i, step in enumerate(steps):
            env = step.get('env', {})
            for key, value in env.items():
                if any(k in key.upper() for k in ['TOKEN', 'SECRET', 'KEY', 'PWD', 'PASSWORD']):
                    if not str(value).startswith('${{'):
                        errors.append(f"Job '{job_name}', Step {i}: Potential hardcoded secret in env '{key}'. Use '${{{{ secrets.NAME }}}}'.")
            
            # 3. Check for unpinned actions
            uses = step.get('uses', '')
            if uses and not uses.startswith('./') and '@' in uses:
                action_part = uses.split('@')[1]
                if action_part == 'latest' or (len(action_part) < 40 and not action_part.startswith('v')):
                     warnings.append(f"Job '{job_name}', Step {i}: Action '{uses}' is not pinned to a specific SHA. High security risk.")

    return errors, warnings

def scan_all_workflows(directory=".github/workflows"):
    if not os.path.exists(directory):
        print(f"Directory {directory} not found.")
        return
    
    all_passed = True
    for filename in os.listdir(directory):
        if filename.endswith(('.yml', '.yaml')):
            path = os.path.join(directory, filename)
            print(f"Scanning {path}...")
            errors, warnings = check_workflow(path)
            
            for err in errors:
                print(f"  [ERROR] {err}")
                all_passed = False
            for warn in warnings:
                print(f"  [WARN] {warn}")
    
    if all_passed:
        print("\n✅ All workflows passed security and optimization checks!")
    else:
        print("\n❌ Some workflows have issues that need addressing.")

if __name__ == "__main__":
    scan_all_workflows()
