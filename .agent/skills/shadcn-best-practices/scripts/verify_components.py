import os
import re

def check_component(filepath):
    """
    Verifies if a component follows the shadcn/ui development patterns.
    """
    with open(filepath, 'r') as f:
        content = f.read()

    errors = []
    warnings = []
    
    # 1. Check for 'cn' utility usage for classNames
    if 'className=' in content and 'cn(' not in content:
        warnings.append("Component uses 'className' but doesn't seem to use the 'cn' utility for merging. This can lead to class conflicts.")

    # 2. Check for ForwardRef components missing displayName
    if 'forwardRef' in content and '.displayName =' not in content:
        errors.append("Component uses 'forwardRef' but is missing '.displayName'. This makes debugging harder in React DevTools.")

    # 3. Check for Tailwind hardcoded values instead of CSS variables
    # (Simplified: check for colors like bg-white or text-black instead of bg-background)
    hardcoded_colors = ['bg-white', 'bg-black', 'text-white', 'text-black', 'border-gray-200']
    for color in hardcoded_colors:
        if color in content:
            warnings.append(f"Hardcoded Tailwind color '{color}' found. Use CSS variables like 'bg-background' or 'text-foreground' for better theming.")

    return errors, warnings

def scan_components(directory="src/components/ui"):
    if not os.path.exists(directory):
        print(f"Directory {directory} not found.")
        return

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(('.tsx', '.jsx')):
                path = os.path.join(root, file)
                errors, warnings = check_component(path)
                
                if errors or warnings:
                    print(f"\nIssues in {path}:")
                    for err in errors:
                        print(f"  [ERROR] {err}")
                    for warn in warnings:
                        print(f"  [WARN] {warn}")

if __name__ == "__main__":
    scan_components()
