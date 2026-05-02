#!/usr/bin/env python3
import sys
import subprocess

def get_user_profile():
    # Simulated connection to personality_adapter
    # In a real run, it would read from .agent/bus/user_dna.json
    return "[PRAGMATIC / MINIMALIST]"

def run_war_room(intent: str):
    print(f"⚔️  Opening Hidden War Room (4-Participant Protocol) for: '{intent}'...")
    profile = get_user_profile()
    
    print(f"\n👤 USER DNA DETECTED: {profile}")
    
    print("\n🎭 [OPTIMIST]: This is a great addition! Let's use a full-featured framework to handle all edge cases. It's the modern way.")
    
    print("\n🎭 [SKEPTIC]: Complexity is too high. We'll have a hard time maintaining this. We need to focus on stability and error boundaries.")
    
    print(f"\n🎭 [USER ADVOCATE]: Hold on. The user prefers {profile}. This framework is too heavy. I VETO any solution that isn't lean. We must stick to pure logic and minimal dependencies.")
    
    print("\n🎭 [ARBITRATOR]: The User Advocate is right. The consensus is: Proceed with a minimalist implementation. No heavy frameworks. Focus on pure logic and robust error handling as requested by Skeptic.")
    
    print("\n✅ CONSENSUS REACHED: Implementation approved (Minimalist Style Enforcement).")

if __name__ == "__main__":
    run_war_room(" ".join(sys.argv[1:]))
