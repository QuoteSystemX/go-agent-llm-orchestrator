import subprocess
import os
import sys

def run_command(command, description):
    print(f"--- {description} ---")
    try:
        subprocess.run(command, shell=True, check=True)
        print(f"✅ {description} successful.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        return False

def harden_env():
    print("🚀 Hardening Go Environment for QuoteSystemX...")
    
    # 1. Set GOPRIVATE
    os.environ["GOPRIVATE"] = "github.com/QuoteSystemX/*"
    print(f"Setting GOPRIVATE=github.com/QuoteSystemX/*")

    # 2. Configure Git Authentication
    # Check for GitHub token (for CI/CD or local environments with GH_TOKEN)
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    
    if token:
        print("💡 Detected GitHub Token. Configuring Git to use HTTPS with token auth.")
        # Pattern: https://x-access-token:<token>@github.com/QuoteSystemX/
        git_cmd = f'git config --global url."https://x-access-token:{token}@github.com/QuoteSystemX/".insteadOf "https://github.com/QuoteSystemX/"'
        run_command(git_cmd, "Configuring Git to use Token-based HTTPS")
    else:
        print("💡 No GitHub Token detected. Falling back to SSH-based auth.")
        # Pattern: git@github.com:QuoteSystemX/
        git_cmd = 'git config --global url."git@github.com:QuoteSystemX/".insteadOf "https://github.com/QuoteSystemX/"'
        run_command(git_cmd, "Configuring Git to use SSH")

    # 3. Verify Go modules
    if os.path.exists("go.mod"):
        run_command("go mod download", "Downloading Go dependencies")
        run_command("go mod verify", "Verifying Go dependencies")
    
    print("\n✅ Go environment is now hardened for QuoteSystemX private repositories.")

if __name__ == "__main__":
    harden_env()
