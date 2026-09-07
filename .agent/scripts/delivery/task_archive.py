#!/usr/bin/env python3
"""Task Archive — partitions tasks/done/ into tasks/done/YYYY-MM/ and regenerates
tasks/done/INDEX.md. Never deletes or prunes cards; that stays a separate, explicit,
human-triggered step (see LESSONS_LEARNED.md [2026-08-14] [DRIFT] entry for why).
"""

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

import argparse
import re
import subprocess
from pathlib import Path

try:
    from lib.paths import REPO_ROOT
except ImportError:
    REPO_ROOT = Path(__file__).resolve().parents[3]

DATE_RE = re.compile(r"^(\d{4}-\d{2})-\d{2}-(.+)\.md$")
HASH_SUFFIX_RE = re.compile(r"-[0-9a-f]{6}$")
STOPWORDS = {"and", "the", "for", "with", "to", "of", "in", "a", "on", "at", "is", "not", "but"}

# Matches a flat, pre-partition reference such as `done/` + a `YYYY-MM-DD-slug.md` filename.
# Anchoring on the literal
# `done/` token (rather than requiring a `tasks/` prefix) catches both the repo-relative form used
# in comments/docs (`tasks/done/...`) and the bare form used from within tasks/ itself (`done/...`)
# with one pattern. Idempotent by construction: after rewriting, the text right after `done/` is
# `YYYY-MM/` (a slash), not `YYYY-MM-` (a dash), so this can't match its own output on a re-run.
STALE_DONE_RE = re.compile(r"done/(\d{4}-\d{2})-(\d{2}-[\w.-]+\.md)")

INDEX_HEADER = "| Date | Card | Topic tags | Distilled? | Wiki link |\n|---|---|---|---|---|\n"
ROW_RE = re.compile(
    r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*([^|]*)\|\s*([^|]*)\|\s*([^|]*)\|\s*$"
)
DATA_ROW_PREFIX_RE = re.compile(r"^\|\s*\d{4}-\d{2}-\d{2}\s*\|")


def topic_tags(slug: str) -> str:
    slug = HASH_SUFFIX_RE.sub("", slug)
    words = [w for w in slug.split("-") if w and w not in STOPWORDS]
    return ", ".join(words[:4])


def find_done_dir(root: Path) -> Path:
    return root / "tasks" / "done"


def load_existing_index(index_path: Path) -> dict:
    """Returns {link_path: (distilled, wiki_link)} to preserve manually-set columns.
    Keyed on the link exactly as it appears in the table (relative to INDEX.md itself)."""
    preserved = {}
    if not index_path.exists():
        return preserved
    for line in index_path.read_text(encoding="utf-8").splitlines():
        m = ROW_RE.match(line)
        if m:
            _, _, link_path, _, distilled, wiki_link = m.groups()
            preserved[link_path.strip()] = (distilled.strip(), wiki_link.strip())
        elif DATA_ROW_PREFIX_RE.match(line):
            # Looks like a data row but doesn't fit the strict cell format — most likely an
            # unescaped `|` in a hand-filled Distilled?/Wiki link cell. Warn instead of silently
            # dropping the preserved columns on the next regeneration.
            print(f"  ⚠️  could not parse INDEX.md row, preserved columns will be lost: {line!r}")
    return preserved


def is_tracked(f: Path, root: Path = REPO_ROOT) -> bool:
    return subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(f)],
        cwd=root, capture_output=True,
    ).returncode == 0


def partition(done_dir: Path, dry_run: bool, root: Path = REPO_ROOT) -> list:
    """Moves top-level dated cards into tasks/done/YYYY-MM/. Returns list of (src, dst).
    Freshly-created cards may not be committed/staged yet — `git mv` requires a tracked file,
    so untracked cards fall back to a plain filesystem move (git picks them up as new/untracked
    at the destination, same as before the move). `root` must be the actual git repo `done_dir`
    lives under (defaults to this checkout) — passing a mismatched root makes `is_tracked()`
    check the wrong repo and silently fall back to the plain-rename path instead of `git mv`."""
    moves = []
    for f in sorted(done_dir.glob("*.md")):
        if f.name in ("INDEX.md", "README.md"):
            continue
        m = DATE_RE.match(f.name)
        if not m:
            print(f"  ⚠️  skipping (no YYYY-MM-DD prefix): {f.name}")
            continue
        month = m.group(1)
        dst = done_dir / month / f.name
        moves.append((f, dst))
        if dry_run:
            print(f"  [dry-run] move {f.relative_to(root)} -> {dst.relative_to(root)}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if is_tracked(f, root):
            subprocess.run(["git", "mv", str(f), str(dst)], cwd=root, check=True)
        else:
            f.rename(dst)
    return moves


def list_tracked_files(root: Path) -> list:
    """All git-tracked files under root, as absolute Paths. Read-only; excludes untracked files
    and gitignored build artifacts by construction (they're simply not in `git ls-files`)."""
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True)
    if result.returncode != 0:
        return []
    names = result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
    return [root / n for n in names if n]


def rewrite_links(root: Path, done_dir: Path, dry_run: bool) -> tuple:
    """Rewrites flat `done/YYYY-MM-DD-slug.md` references into their partitioned
    `done/YYYY-MM/YYYY-MM-DD-slug.md` form, across every git-tracked file under root.

    Only rewrites a match whose computed destination actually exists on disk. Anything else — a
    pruned card, a reference that was already broken, or one pointing at a card that only exists in
    a different repo — is left untouched and reported as dangling instead of guessed at.

    Returns (changed: {Path: [(old, new), ...]}, dangling: [(Path, old_token), ...]).
    """
    changed = {}
    dangling = []

    for f in list_tracked_files(root):
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "\x00" in text[:8192] or "done/" not in text:
            continue

        file_changes = []

        def _sub(m):
            month, rest = m.group(1), m.group(2)
            old, new = m.group(0), f"done/{month}/{month}-{rest}"
            if not (done_dir / month / f"{month}-{rest}").exists():
                dangling.append((f, old))
                return old
            file_changes.append((old, new))
            return new

        new_text = STALE_DONE_RE.sub(_sub, text)
        if file_changes:
            changed[f] = file_changes
            if not dry_run:
                f.write_text(new_text, encoding="utf-8")

    return changed, dangling


def _print_capped(label: str, items: list, formatter, cap: int = 10) -> None:
    print(f"{label} ({len(items)}):")
    for item in items[:cap]:
        print(f"  {formatter(item)}")
    if len(items) > cap:
        print(f"  ... and {len(items) - cap} more.")


def build_index(done_dir: Path, preserved: dict) -> str:
    rows = []
    for month_dir in sorted(done_dir.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]"), reverse=True):
        for f in sorted(month_dir.glob("*.md"), reverse=True):
            m = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$", f.name)
            if not m:
                continue
            date, slug = m.groups()
            # Link must be relative to INDEX.md's own location (tasks/done/), i.e. relative to
            # done_dir — also used as the lookup key for preserved manual columns.
            link = f.relative_to(done_dir).as_posix()
            distilled, wiki_link = preserved.get(link, ("", ""))
            rows.append(f"| {date} | [{f.name}]({link}) | {topic_tags(slug)} | {distilled} | {wiki_link} |")
    return INDEX_HEADER + "\n".join(rows) + ("\n" if rows else "")


def main():
    parser = argparse.ArgumentParser(description="Partition tasks/done/ by month and regenerate INDEX.md")
    parser.add_argument("--check", action="store_true", help="Dry-run; exit 1 if drift found (CI use)")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Override repository root path")
    args = parser.parse_args()

    done_dir = find_done_dir(args.root)
    index_path = done_dir / "INDEX.md"

    if args.check:
        stray = [f for f in done_dir.glob("*.md") if f.name not in ("INDEX.md", "README.md")]
        if stray:
            print(f"❌ {len(stray)} unpartitioned card(s) in tasks/done/: {[f.name for f in stray]}")
            raise SystemExit(1)
        preserved = load_existing_index(index_path)
        expected = build_index(done_dir, preserved)
        actual = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
        if expected != actual:
            print("❌ tasks/done/INDEX.md is out of date. Run: python3 .agent/scripts/delivery/task_archive.py")
            raise SystemExit(1)

        changed, dangling = rewrite_links(args.root, done_dir, dry_run=True)
        if dangling:
            _print_capped(
                "⚠️  Dangling done/ reference(s) (card not found in this repo)", dangling,
                lambda fd: f"{fd[0].relative_to(args.root)}: {fd[1]}",
            )
        if changed:
            total_links = sum(len(v) for v in changed.values())
            print(f"❌ {total_links} stale done/ reference(s) in {len(changed)} file(s) need rewriting. "
                  f"Run: python3 .agent/scripts/delivery/task_archive.py")
            raise SystemExit(1)

        print("✅ tasks/done/ is partitioned and INDEX.md is current.")
        return

    print("Partitioning tasks/done/ ...")
    moves = partition(done_dir, dry_run=False, root=args.root)

    preserved = load_existing_index(index_path)
    index_path.write_text(build_index(done_dir, preserved), encoding="utf-8")
    print(f"✅ Wrote {index_path.relative_to(args.root)}")

    changed, dangling = rewrite_links(args.root, done_dir, dry_run=False)
    total_links = sum(len(v) for v in changed.values())
    print(f"🔗 Rewrote {total_links} stale done/ reference(s) in {len(changed)} file(s).")
    if changed:
        pairs = [(f, old, new) for f, cs in changed.items() for old, new in cs]
        _print_capped("  Rewritten", pairs, lambda t: f"{t[0].relative_to(args.root)}: {t[1]} -> {t[2]}")
    if dangling:
        _print_capped(
            "⚠️  Dangling done/ reference(s) left as-is (card not found in this repo)", dangling,
            lambda fd: f"{fd[0].relative_to(args.root)}: {fd[1]}",
        )

    print(f"✅ Partitioned {len(moves)} card(s).")


if __name__ == "__main__":
    main()
