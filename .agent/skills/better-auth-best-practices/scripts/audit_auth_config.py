import os
import re

def audit_auth(filepath):
    """
    Audits authentication configuration for security best practices.
    """
    with open(filepath, 'r') as f:
        content = f.read()

    errors = []
    warnings = []
    
    # 1. Check for Secure Cookies
    if 'cookies:' in content and 'secure: true' not in content:
        errors.append("Session cookies might be missing 'secure: true' flag. This is critical for production.")

    # 2. Check for CSRF protection (if using custom handlers)
    if 'csrf' not in content.lower():
        warnings.append("Explicit CSRF protection not found in the config. Ensure your framework handles it or enable it explicitly.")

    # 3. Check for Session Max Age
    if 'maxAge' not in content:
        warnings.append("Session 'maxAge' not explicitly set. Default might be too long for some security standards.")

    # 4. Check for hardcoded secrets
    if re.search(r'secret:\s*[\'"][^\$].+?[\'"]', content):
        errors.append("Hardcoded secret found in auth config. Use environment variables (e.g., process.env.AUTH_SECRET).")

    return errors, warnings

def scan_auth_files(directory="src/lib/auth"):
    if not os.path.exists(directory):
        print(f"Directory {directory} not found. Skipping scan.")
        return

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(('.ts', '.js')):
                path = os.path.join(root, file)
                print(f"Auditing {path}...")
                errors, warnings = audit_auth(path)
                
                if errors or warnings:
                    for err in errors: print(f"  [ERROR] {err}")
                    for warn in warnings: print(f"  [WARN] {warn}")

if __name__ == "__main__":
    scan_auth_files()
