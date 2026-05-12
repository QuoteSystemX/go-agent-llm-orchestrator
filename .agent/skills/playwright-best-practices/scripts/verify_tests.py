import os
import re

def check_test_file(filepath):
    """
    Scans a Playwright test file for anti-patterns.
    """
    with open(filepath, 'r') as f:
        content = f.read()

    errors = []
    warnings = []
    
    # 1. Check for hardcoded waits
    if 'page.waitForTimeout(' in content:
        errors.append("Hardcoded wait 'page.waitForTimeout()' found. Use web-first assertions or 'waitForSelector' instead.")

    # 2. Check for missing assertions (simplified check)
    if 'await expect(' not in content:
        warnings.append("No 'expect' assertions found in the file. A test without assertions is just a script.")

    # 3. Check for non-semantic selectors
    selectors = re.findall(r'page\.locator\([\'"](.+?)[\'"]\)', content)
    for selector in selectors:
        if any(s in selector for s in ['.', '#', 'div', 'span']) and 'data-testid' not in selector:
            warnings.append(f"Potentially brittle CSS/ID selector found: '{selector}'. Prefer semantic locators like 'getByRole' or 'data-testid'.")

    return errors, warnings

def scan_tests(directory="tests"):
    if not os.path.exists(directory):
        print(f"Directory {directory} not found.")
        return

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(('.spec.ts', '.spec.js')):
                path = os.path.join(root, file)
                errors, warnings = check_test_file(path)
                
                if errors or warnings:
                    print(f"\nIssues in {path}:")
                    for err in errors:
                        print(f"  [ERROR] {err}")
                    for warn in warnings:
                        print(f"  [WARN] {warn}")

if __name__ == "__main__":
    scan_tests()
