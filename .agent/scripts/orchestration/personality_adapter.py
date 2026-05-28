#!/usr/bin/env python3

# Antigravity Domain-Aware Import Logic
try:
    from lib.paths import REPO_ROOT
except ImportError:
    import sys
    from pathlib import Path
    SCRIPTS_DIR = Path(__file__).resolve().parents[1]
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.append(str(SCRIPTS_DIR))
    for domain in ["health", "context", "delivery", "orchestration", "analysis", "models", "knowledge", "dev"]:
        d_path = str(SCRIPTS_DIR / domain)
        if d_path not in sys.path:
            sys.path.append(d_path)

import sys
import re
from pathlib import Path

# Try to find REPO_ROOT from common lib, or use default
try:
    from lib.paths import REPO_ROOT, RULES_DIR
    PERSONA_FILE = RULES_DIR / "PERSONA.md"
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
    PERSONA_FILE = REPO_ROOT / ".agent" / "rules" / "PERSONA.md"

def adapt_personality():
    print("🎭 Analyzing user stylistic DNA...")
    
    if not PERSONA_FILE.exists():
        print("⚠️  PERSONA.md not found. Using default profile: [BALANCED].")
        dna = "BALANCED"
        prefs = ["Standard clarity", "Balanced explanation"]
    else:
        content = PERSONA_FILE.read_text(encoding="utf-8")
        dna_match = re.search(r'## 🧬 Core DNA: \[(.*?)\]', content)
        dna = dna_match.group(1) if dna_match else "UNKNOWN"
        
        print(f"🧠 Profile Detected: [{dna}]")
        
        # Extract bullets under preferences
        prefs = []
        in_prefs = False
        for line in content.splitlines():
            if "Stylistic Preferences" in line: in_prefs = True
            elif line.startswith("## ") and in_prefs: break
            if in_prefs and line.strip().startswith("- "):
                prefs.append(line.strip().replace("- ", ""))
    
    for pref in prefs:
        print(f"  - Preference: {pref}")
    
    # Save to context bus — canonical user_dna.json (extended schema)
    bus_file = REPO_ROOT / ".agent" / "bus" / "user_dna.json"
    bus_file.parent.mkdir(parents=True, exist_ok=True)
    
    import json
    payload = {
        "dna": dna,
        "preferences": prefs,
        "veto_config": {
            "mode": "soft",
            "threshold": 0.4,
            "auto_reject": False,
            "confidence_decay": 0.2,
        },
        "metadata": {
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "source": "PERSONA.md",
        },
    }
    with open(bus_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    
    # Legacy cleanup: remove old personality_profile.json if present
    legacy = REPO_ROOT / ".agent" / "bus" / "personality_profile.json"
    if legacy.exists():
        legacy.unlink()
        print("  🗑 Cleaned up legacy personality_profile.json")
    
    print(f"\n✅ Personality Bridge established. Data saved to bus (user_dna.json).")

if __name__ == "__main__":
    adapt_personality()
