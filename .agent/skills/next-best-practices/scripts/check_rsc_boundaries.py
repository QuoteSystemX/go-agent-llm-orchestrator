import os
import re

def check_file(filepath):
    """
    Checks a React/Next.js file for common App Router antipatterns.
    """
    with open(filepath, 'r') as f:
        content = f.read()

    errors = []
    warnings = []
    
    is_client = '"use client"' in content or "'use client'" in content
    
    # 1. Check for Hooks in Server Components
    hooks = ['useState', 'useEffect', 'useContext', 'useReducer', 'useCallback', 'useMemo', 'useRef', 'useLayoutEffect']
    if not is_client:
        for hook in hooks:
            if re.search(r'\b' + hook + r'\b', content):
                errors.append(f"Hook '{hook}' found in a Server Component. Add 'use client' or move to a client component.")
    
    # 2. Check for Event Handlers in Server Components
    if not is_client:
        if re.search(r'\bon[A-Z][a-z]+\s*=', content):
             errors.append("Event handler (onClick, etc.) found in a Server Component. Add 'use client'.")

    # 3. Check for Browser APIs in Server Components
    browser_apis = ['window', 'document', 'localStorage', 'sessionStorage', 'navigator']
    if not is_client:
        for api in browser_apis:
            if re.search(r'\b' + api + r'\b', content):
                warnings.append(f"Browser API '{api}' used in a Server Component. This will fail on the server.")

    return errors, warnings

def scan_project(directory="src"):
    if not os.path.exists(directory):
        print(f"Directory {directory} not found.")
        return

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(('.tsx', '.jsx')):
                path = os.path.join(root, file)
                errors, warnings = check_file(path)
                
                if errors or warnings:
                    print(f"\nIssues in {path}:")
                    for err in errors:
                        print(f"  [ERROR] {err}")
                    for warn in warnings:
                        print(f"  [WARN] {warn}")

if __name__ == "__main__":
    scan_project()
