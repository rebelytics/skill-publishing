#!/usr/bin/env python3
"""pr-coverage.py — how much of a PR's diff is verbatim in a tree.
Part of the skill-publishing skill (CC BY 4.0 — Eoghan Henn and contributors).

"Shipped" is a claim about a DIFF, so it is verified against the diff: the
presence of a PR's subject on main proves only that someone wrote about the
same thing. This script takes the PR's patch (`gh pr diff N > pr.patch`, or
the `.diff` URL) and a directory tree — a fresh clone of the release tag,
never the working copy — and reports what share of the patch's added lines
occur verbatim (whitespace-trimmed) anywhere in the tree, listing the lines
that do not. A low share is not a verdict either way: rewording scores low
and can still be fully shipped point by point. It is the trigger for the
per-point read the Responding procedure requires below --threshold, and the
missing-line list is that read's worksheet.

Usage:
  pr-coverage.py PATCH TREE [--threshold 70] [--min-chars 8] [--ext .md .py ...]

Exit 1 when the share is below --threshold (so a "shipped" close can be
gated on it), 0 otherwise. Added lines shorter than --min-chars after
trimming are not counted (closing fences, blank list markers, `---`).
"""
import argparse, pathlib, sys

TEXT_EXT = {".md", ".py", ".sh", ".txt", ".yml", ".yaml", ".json", ".toml",
            ".cfg", ".js", ".ts", ".html", ".css"}


def added_lines(patch_text, min_chars):
    """[(file, line)] for every '+' line that is not a file header."""
    out, current = [], None
    for raw in patch_text.splitlines():
        if raw.startswith("+++ "):
            current = raw[4:].strip()
            current = current[2:] if current.startswith("b/") else current
            continue
        if raw.startswith("--- ") or raw.startswith("@@"):
            continue
        if raw.startswith("+"):
            line = raw[1:].strip()
            if len(line) >= min_chars:
                out.append((current or "?", line))
    return out


def tree_lines(tree, exts):
    seen = set()
    for p in pathlib.Path(tree).rglob("*"):
        if not p.is_file() or ".git" in p.parts or p.suffix.lower() not in exts:
            continue
        try:
            for l in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                seen.add(l.strip())
        except OSError:
            continue
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("patch")
    ap.add_argument("tree")
    ap.add_argument("--threshold", type=float, default=70.0)
    ap.add_argument("--min-chars", type=int, default=8)
    ap.add_argument("--ext", nargs="*", default=sorted(TEXT_EXT))
    a = ap.parse_args()

    added = added_lines(pathlib.Path(a.patch).read_text(encoding="utf-8",
                                                          errors="ignore"),
                        a.min_chars)
    if not added:
        sys.exit("FATAL: no added lines >= --min-chars in the patch — is this "
                 "a unified diff?")
    have = tree_lines(a.tree, {e if e.startswith(".") else "." + e
                               for e in a.ext})
    per_file, missing = {}, []
    for f, line in added:
        hit = line in have
        n = per_file.setdefault(f, [0, 0])
        n[1] += 1
        n[0] += hit
        if not hit:
            missing.append((f, line))
    total = len(added)
    present = total - len(missing)
    pct = 100.0 * present / total
    print(f"pr-coverage: {present}/{total} added lines present verbatim "
          f"({pct:.0f} %) in {pathlib.Path(a.tree).resolve()}")
    for f, (p, t) in sorted(per_file.items()):
        print(f"  {f}: {p}/{t}")
    if missing:
        print(f"missing ({len(missing)}) — the per-point worksheet:")
        for f, line in missing:
            print(f"  - [{f}] {line[:140]}")
    verdict = ("at or above" if pct >= a.threshold else "BELOW")
    print(f"RESULT: {pct:.0f} % is {verdict} the {a.threshold:.0f} % threshold"
          + ("" if pct >= a.threshold else
             " — read every missing line against the tree and name file+line "
             "for each point before any 'shipped' close"))
    sys.exit(0 if pct >= a.threshold else 1)


if __name__ == "__main__":
    main()
