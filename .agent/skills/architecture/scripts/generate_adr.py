import os
import sys
from datetime import datetime

ADR_DIR = "docs/adr"
TEMPLATE = """# ADR-{id}: {title}

*   **Status**: Proposed
*   **Date**: {date}
*   **Deciders**: [List of decision makers]
*   **Consulted**: [List of consulted people]

## Context and Problem Statement

[What is the problem we are trying to solve? Describe the context and why a decision is needed.]

## Decision Drivers

*   [Driver 1, e.g., Scalability]
*   [Driver 2, e.g., Cost]

## Considered Options

1.  **Option 1**: [Description]
2.  **Option 2**: [Description]

## Decision Outcome

Chosen option: **Option 1**, because [rationale].

### Positive Consequences

*   [Positive 1]

### Negative Consequences

*   [Negative 1, e.g., Technical debt]

## Pros and Cons of the Options

### Option 1
*   Good, because [pros]
*   Bad, because [cons]

## Links
*   [Link to related documents]
"""

def generate_adr(title):
    os.makedirs(ADR_DIR, exist_ok=True)
    
    # Find the next ID
    existing_adrs = [f for f in os.listdir(ADR_DIR) if f.startswith("adr-") and f.endswith(".md")]
    next_id = len(existing_adrs) + 1
    
    filename = f"adr-{next_id:03d}-{title.lower().replace(' ', '-')}.md"
    filepath = os.path.join(ADR_DIR, filename)
    
    content = TEMPLATE.format(
        id=f"{next_id:03d}",
        title=title,
        date=datetime.now().strftime("%Y-%m-%d")
    )
    
    with open(filepath, "w") as f:
        f.write(content)
    
    print(f"✅ Created ADR: {filepath}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 generate_adr.py 'My Decision Title'")
        sys.exit(1)
    
    generate_adr(sys.argv[1])
