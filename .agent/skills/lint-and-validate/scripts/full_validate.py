import subprocess
import os
import sys

def run_command(command, description):
    print(f"--- Running {description} ---")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} passed.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed.")
        print(e.stdout)
        print(e.stderr)
        return False

def full_validate():
    all_passed = True
    
    # 1. ESLint
    if os.path.exists("package.json"):
        if not run_command("npm run lint", "ESLint"):
            all_passed = False
            
    # 2. TypeScript
    if os.path.exists("tsconfig.json"):
        if not run_command("npx tsc --noEmit", "TypeScript Check"):
            all_passed = False
            
    # 3. Python Lint (if applicable)
    if any(f.endswith('.py') for f in os.listdir('.') if os.path.isfile(f)):
        if not run_command("flake8 .", "Python Lint (flake8)"):
            all_passed = False

    # 4. Custom Validators (Skill scripts)
    custom_validators = [
        ".agent/skills/github-actions-expert/scripts/verify_workflows.py",
        ".agent/skills/next-best-practices/scripts/check_rsc_boundaries.py",
        ".agent/skills/postgres-best-practices/scripts/verify_schema.py",
        ".agent/skills/playwright-best-practices/scripts/verify_tests.py",
        ".agent/skills/shadcn-best-practices/scripts/verify_components.py",
        ".agent/skills/prompts-best-practices/scripts/verify_prompts.py",
        ".agent/skills/database-design/scripts/analyze_normalization.py",
        ".agent/skills/better-auth-best-practices/scripts/audit_auth_config.py",
        ".agent/skills/wsl-interop/scripts/check_wsl_config.py"
    ]
    
    for validator in custom_validators:
        if os.path.exists(validator):
            if not run_command(f"python3 {validator}", f"Custom Validator: {os.path.basename(validator)}"):
                all_passed = False

    if all_passed:
        print("\n🏆 FULL VALIDATION PASSED!")
        sys.exit(0)
    else:
        print("\n⚠️ SOME VALIDATIONS FAILED. Check the logs above.")
        sys.exit(1)

if __name__ == "__main__":
    full_validate()
