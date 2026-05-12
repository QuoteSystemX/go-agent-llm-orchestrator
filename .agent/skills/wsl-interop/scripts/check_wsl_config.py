import os
import platform
import subprocess

def check_wsl():
    """
    Checks the WSL environment for performance and interoperability settings.
    """
    print("--- WSL Interop Audit ---")
    
    # 1. Check if we are actually in WSL
    if 'microsoft' not in platform.release().lower():
        print("⚠️ Not running in WSL. Skipping audit.")
        return

    # 2. Check WSL version
    try:
        wsl_version = subprocess.check_output(['wsl.exe', '--version'], stderr=subprocess.STDOUT, text=True)
        print(f"✅ WSL Version Info: {wsl_version.strip()}")
    except:
        print("⚠️ Could not determine WSL version using wsl.exe.")

    # 3. Check /etc/wsl.conf
    if os.path.exists("/etc/wsl.conf"):
        with open("/etc/wsl.conf", "r") as f:
            content = f.read()
            if "interop" in content and "enabled=true" in content:
                print("✅ Interop is enabled in /etc/wsl.conf")
            else:
                print("⚠️ Interop might be disabled or not explicitly enabled in /etc/wsl.conf")
    else:
        print("⚠️ /etc/wsl.conf missing. Default settings applied.")

    # 4. Check for Mirrored Networking (WSL 2.0+)
    # (Typically found in %USERPROFILE%\.wslconfig on Windows side)
    # This script is in WSL, so it's hard to check Windows files directly without interop
    try:
        # Try to find the Windows user profile path
        win_home = subprocess.check_output(['wslpath', '$(powershell.exe -Command "echo $HOME")'], shell=True, text=True).strip()
        wslconfig_path = os.path.join(win_home, ".wslconfig")
        if os.path.exists(wslconfig_path):
            print(f"✅ Found .wslconfig at {wslconfig_path}")
            # Check for mirrored networking
            with open(wslconfig_path, "r") as f:
                if "networkingMode=mirrored" in f.read():
                    print("🚀 Mirrored Networking is ENABLED. Optimal for local service discovery.")
                else:
                    print("⚠️ Mirrored Networking is NOT enabled. You may have issues with localhost binding.")
    except:
        print("⚠️ Could not check .wslconfig on Windows side.")

    print("\n✅ WSL Audit complete.")

if __name__ == "__main__":
    check_wsl()
