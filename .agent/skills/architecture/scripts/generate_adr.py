import re
import sys
from datetime import datetime
from pathlib import Path


def get_repo_root() -> Path:
    """Find the repo root by searching upwards for .git or CLAUDE.md, same as lib/paths.py."""
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists() or (parent / "CLAUDE.md").exists():
            return parent
    return Path(__file__).resolve().parents[4]


REPO_ROOT = get_repo_root()
ADR_DIR = REPO_ROOT / "wiki" / "decisions"

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


def slugify(title):
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "untitled"


def next_adr_id():
    """Max existing ADR-NNN id + 1. Counting files undercounts after deletions/renumbering."""
    max_id = 0
    for f in ADR_DIR.glob("ADR-*.md"):
        match = re.match(r"ADR-(\d+)-", f.name)
        if match:
            max_id = max(max_id, int(match.group(1)))
    return max_id + 1


def generate_adr(title):
    ADR_DIR.mkdir(parents=True, exist_ok=True)

    next_id = next_adr_id()
    slug = slugify(title)
    filepath = ADR_DIR / f"ADR-{next_id:03d}-{slug}.md"
    while filepath.exists():
        next_id += 1
        filepath = ADR_DIR / f"ADR-{next_id:03d}-{slug}.md"

    content = TEMPLATE.format(
        id=f"{next_id:03d}",
        title=title,
        date=datetime.now().strftime("%Y-%m-%d")
    )

    with open(filepath, "w") as f:
        f.write(content)

    print(f"✅ Created ADR: {filepath.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 generate_adr.py 'My Decision Title'")
        sys.exit(1)

    generate_adr(sys.argv[1])
