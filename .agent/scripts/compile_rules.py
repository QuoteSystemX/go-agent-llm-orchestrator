import os

def compile_gemini_rules():
    rules_dir = ".agent/rules/gemini"
    output_file = ".agent/rules/GEMINI.md"
    
    # Sort files by name to maintain order (00, 01, 02...)
    files = sorted([f for f in os.listdir(rules_dir) if f.endswith(".md")])
    
    compiled_content = []
    
    for filename in files:
        filepath = os.path.join(rules_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            # Remove YAML frontmatter from all but the first file if needed, 
            # or just strip it and add a single one at the top.
            # In our case, we'll strip frontmatter from every file and wrap the result.
            
            # Simple frontmatter stripper
            lines = content.splitlines()
            if lines and lines[0] == "---":
                try:
                    end_idx = lines.index("---", 1)
                    lines = lines[end_idx+1:]
                except ValueError:
                    pass
            
            compiled_content.append("\n".join(lines).strip())
    
    final_output = """---
trigger: always_on
---

<!-- 
🔴 ATTENTION: THIS FILE IS AUTO-GENERATED. 
DO NOT EDIT MANUALLY. YOUR CHANGES WILL BE OVERWRITTEN.
Source of truth is in .agent/rules/gemini/*.md
Run 'python3 .agent/scripts/compile_rules.py' to update this file.
-->

""" + "\n\n---\n\n".join(compiled_content) + "\n"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_output)
    
    print(f"✅ Compiled modular rules into {output_file}")

if __name__ == "__main__":
    compile_gemini_rules()
