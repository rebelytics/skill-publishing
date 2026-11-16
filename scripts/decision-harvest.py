#!/usr/bin/env python3
"""decision-harvest.py — cycle step 0's "Decided, awaiting build" table.
Part of the skill-publishing skill (CC BY 4.0 — Eoghan Henn and contributors).

Decisions routed to a publishing run land in many places, written by many
sessions; the run that builds them is one reader. A table built from recall
misses the source nobody re-opened, and nothing errors. This script reads
every source it is given and prints the table, one row per item, with the
status column left for the run to fill (built this run / on branch X /
blocked by Y).

Sources:
  --obs-dir DIR      every *.md observation directly in DIR whose status is
                     not closed: a body or title line carrying `Decision` /
                     `DECIDED`, or `next_actor: publishing-run`. --skill
                     narrows to observations whose `skill:` names one.
  --publishing-dir   every `decisions-*.md` there (one row per list item,
                     else per paragraph), and its `REVIEW.md` unless
                     --review names the records to read.
  --review FILE      a previous review record: every row of its "Decided,
                     awaiting build" table not marked built.
  --queue FILE       a backlog or queue file: the list items under a
                     "Queue for the ... publishing session" heading, and
                     every list item or table row elsewhere that names the
                     publishing session or run, README, USER-GUIDE or
                     `→ main`.
  --registry FILE    (default: registry.md in --publishing-dir) every hold
                     row, printed as "Holds to re-check" with the release
                     condition after "until"; a hold with none is flagged.

A named source that cannot be read prints NOT READ and the exit code is 2:
an unread source must never look like a source with no decisions in it.

Usage:
  decision-harvest.py --obs-dir DIR --publishing-dir DIR [--skill NAME ...]
                      [--review FILE ...] [--queue FILE ...] [--registry FILE]
  decision-harvest.py --selftest
"""
import argparse, pathlib, re, sys

CLOSED = {"resolved", "closed", "rejected", "archived", "superseded", "done"}
# A decision is a line that OPENS with the marker; a line that only
# mentions the word ("Decision/DECIDED lines") is prose about decisions.
DECISION_RE = re.compile(r"^\s*[*_]*\s*(?:Decision\b|DECIDED\b)")
HEADING_RE = re.compile(r"^(#+)\s+(.*)$")
ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*\S)")
HOLD_RE = re.compile(r"\bheld\b", re.I)
QUEUE_RE = re.compile(r"queue for the .*publishing", re.I)
TARGETS_REPO_RE = re.compile(r"publishing (?:session|run)|README|USER-GUIDE|→ main")


def frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, lines
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm = {}
            for l in lines[1:i]:
                m = re.match(r"^([A-Za-z_]+):\s*(.*)$", l)
                if m:
                    fm[m.group(1)] = m.group(2).strip().strip('"\'')
            return fm, lines[i + 1:]
    return {}, lines


def short(text, n=160):
    text = " ".join(text.replace("|", "/").split())
    return text if len(text) <= n else text[:n - 1] + "…"


def from_observations(d, skills):
    rows = []
    for f in sorted(d.glob("*.md")):
        fm, body = frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        if not fm or fm.get("status", "").lower() in CLOSED:
            continue
        named = re.findall(r"[\w.-]+", fm.get("skill", ""))
        if skills and not set(skills) & set(named):
            continue
        hits = [l for l in body if DECISION_RE.search(l)]
        title = fm.get("title", "")
        if not hits and DECISION_RE.search(title):
            hits = [title]
        if not hits and fm.get("next_actor", "") == "publishing-run":
            hits = ["routed to the publishing run: " + title]
        for h in hits[-1:]:          # the latest decision line wins
            rows.append((short(h.replace("**", "").strip()), f.name))
    return rows


def from_decision_notes(f):
    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    items = [m.group(1) for l in lines for m in [ITEM_RE.match(l)] if m
             and not l.startswith((" ", "\t"))]
    if not items:
        paras, cur = [], []
        for l in lines + [""]:
            if l.strip() and not HEADING_RE.match(l):
                cur.append(l.strip())
            elif cur:
                paras.append(cur[0])
                cur = []
        items = paras
    return [(short(i), f.name) for i in items]


def from_review(f):
    rows, inside, level = [], False, 0
    for l in f.read_text(encoding="utf-8", errors="replace").splitlines():
        h = HEADING_RE.match(l)
        if h:
            if "decided, awaiting build" in h.group(2).lower():
                inside, level = True, len(h.group(1))
                continue
            if inside and len(h.group(1)) <= level:
                inside = False
        if not inside or not l.strip().startswith("|"):
            continue
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", c) for c in cells if c) or \
                cells[0].lower() in ("item", "#", "decision"):
            continue
        if "built this run" in cells[-1].lower():
            continue
        rows.append((short(" — ".join(c for c in cells if c)),
                     f.name + " (carried)"))
    return rows


def from_queue(f):
    rows, inside = [], False
    for l in f.read_text(encoding="utf-8", errors="replace").splitlines():
        h = HEADING_RE.match(l)
        if h:
            inside = bool(QUEUE_RE.search(h.group(2)))
            continue
        m = ITEM_RE.match(l)
        row = m or l.strip().startswith("|")
        if row and not re.fullmatch(r"[|:\s-]+", l.strip()) and \
                (inside or TARGETS_REPO_RE.search(l)):
            rows.append((short(m.group(1) if m else l.strip().strip("|")), f.name))
    return rows


def holds(f):
    out = []
    for l in f.read_text(encoding="utf-8", errors="replace").splitlines():
        if not HOLD_RE.search(l) or HEADING_RE.match(l):
            continue
        m = re.search(r"\buntil\b\s*(.+)", l, re.I)
        cond = short(m.group(1).strip(" |"), 120) if m else \
            "NO RELEASE CONDITION — name one or clear the hold"
        out.append((short(l.strip().strip("|"), 120), cond))
    return out


def harvest(obs_dirs, pub_dir, skills=(), reviews=(), queues=(), registry=None):
    """(rows, hold rows, source log, unread count)."""
    rows, log, unread = [], [], 0

    def take(label, path, fn):
        nonlocal unread
        p = pathlib.Path(path)
        if not p.exists():
            log.append(f"NOT READ  {label}: {p} (missing)")
            unread += 1
            return []
        got = fn(p)
        log.append(f"read      {label}: {p} — {len(got)} row(s)")
        return got

    for d in obs_dirs:
        rows += take("observations", d, lambda p: from_observations(p, skills)
                     if p.is_dir() else [])
    pub = pathlib.Path(pub_dir) if pub_dir else None
    if pub is not None:
        if not pub.is_dir():
            log.append(f"NOT READ  publishing folder: {pub} (missing)")
            unread += 1
        else:
            notes = sorted(pub.glob("decisions-*.md"))
            log.append(f"read      decisions-*.md in {pub}: {len(notes)} file(s)")
            for f in notes:
                rows += take("decision notes", f, from_decision_notes)
            if not reviews and (pub / "REVIEW.md").exists():
                reviews = [pub / "REVIEW.md"]
            if registry is None and (pub / "registry.md").exists():
                registry = pub / "registry.md"
    for f in reviews:
        rows += take("review record", f, from_review)
    for f in queues:
        rows += take("queue", f, from_queue)
    held = take("registry holds", registry, holds) if registry else []
    return rows, held, log, unread


def render(rows, held, log):
    out = ["## Decided, awaiting build", "",
           "| # | Item | Source | Status |", "|---|---|---|---|"]
    out += [f"| {i} | {item} | {src} | — |" for i, (item, src)
            in enumerate(rows, 1)]
    if not rows:
        out.append("| — | no decided items in the sources read | — | — |")
    out += ["", "## Holds to re-check", "", "| Hold | Release condition |",
            "|---|---|"]
    out += [f"| {h} | {c} |" for h, c in held] or ["| — | no holds |"]
    out += ["", "Sources:"] + ["  " + l for l in log]
    return "\n".join(out)


def selftest():
    import tempfile
    fails = []

    def expect(name, ok, detail=""):
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail
                                                       and not ok else ""))
        if not ok:
            fails.append(name)

    with tempfile.TemporaryDirectory() as d:
        obs = pathlib.Path(d, "observation-log")
        obs.mkdir()
        (obs / "a-unit-converter.md").write_text(
            "---\nid: 1\ntitle: \"Add a unit converter\"\nstatus: open\n"
            "skill: [recipe-box]\n---\n\n**Issue:** grams only.\n\n"
            "**Decision (maintainer):** yes, add the converter script.\n",
            encoding="utf-8")
        (obs / "b-closed.md").write_text(
            "---\nid: 2\ntitle: \"DECIDED: rename the index\"\nstatus: resolved\n"
            "skill: [recipe-box]\n---\n\nDone.\n", encoding="utf-8")
        (obs / "c-routed.md").write_text(
            "---\nid: 3\ntitle: \"README install line\"\nstatus: open\n"
            "skill: [recipe-box]\nnext_actor: publishing-run\n---\n\nBody.\n",
            encoding="utf-8")
        (obs / "d-other-skill.md").write_text(
            "---\nid: 4\ntitle: \"DECIDED: tidy the planner\"\nstatus: open\n"
            "skill: [garden-planner]\n---\n\nBody.\n", encoding="utf-8")
        (obs / "e-no-decision.md").write_text(
            "---\nid: 5\ntitle: \"A loose idea\"\nstatus: open\n"
            "skill: [recipe-box]\n---\n\n**Suggested:** a script that lists "
            "every Decision line.\n", encoding="utf-8")
        pub = pathlib.Path(d, "skill-publishing")
        pub.mkdir()
        (pub / "decisions-pantry.md").write_text(
            "# Decision notes\n\n- publish recipe-box next\n- keep the old "
            "install path one more release\n  (continuation, not an item)\n",
            encoding="utf-8")
        (pub / "REVIEW.md").write_text(
            "# Review\n\n## Decided, awaiting build\n\n| # | Item | Source | Status |\n"
            "|---|---|---|---|\n| 1 | add a print view | notes | built this run |\n"
            "| 2 | split the guide | obs | blocked by the install |\n\n"
            "## Ready to review\n\n| 9 | not a decision row | x | y |\n",
            encoding="utf-8")
        (pub / "registry.md").write_text(
            "| Skill | Status |\n|---|---|\n| recipe-box | published |\n"
            "| pantry-audit | HELD until garden-planner is published |\n"
            "| meal-log | held |\n", encoding="utf-8")
        queue = pathlib.Path(d, "backlog.md")
        queue.write_text("# Backlog\n\n## Queue for the next publishing session\n\n"
                         "- refresh the README figures\n\n## Later\n\n"
                         "- not for publishing\n- USER-GUIDE wording → main\n"
                         "- README badge row\n",
                         encoding="utf-8")

        rows, held, log, unread = harvest([obs], pub, ["recipe-box"],
                                          queues=[queue])
        items = [r[0] for r in rows]
        text = render(rows, held, log)
        expect("observation Decision line harvested",
               any("add the converter script" in i for i in items), items)
        expect("a closed observation is not harvested",
               not any("rename the index" in i for i in items), items)
        expect("next_actor: publishing-run is harvested",
               any("routed to the publishing run: README install line" in i
                   for i in items), items)
        expect("--skill narrows to the named skill",
               not any("tidy the planner" in i for i in items), items)
        expect("a line that only mentions Decision is not a decision",
               not any(r[1] == "e-no-decision.md" for r in rows), rows)
        expect("decisions-*.md: one row per top-level list item",
               sum(r[1] == "decisions-pantry.md" for r in rows) == 2, rows)
        expect("previous REVIEW.md: unbuilt row carried, built row dropped",
               any("split the guide" in i for i in items)
               and not any("print view" in i for i in items)
               and not any("not a decision row" in i for i in items), items)
        expect("queue: items under the queue heading and `→ main` lines",
               any("refresh the README figures" in i for i in items)
               and any("USER-GUIDE wording" in i for i in items)
               and any("README badge row" in i for i in items)
               and not any("not for publishing" in i for i in items), items)
        expect("hold with a release condition shows the condition",
               ("| pantry-audit / HELD until garden-planner is published |"
                " garden-planner is published |") in text, text)
        expect("hold with no release condition is flagged",
               "meal-log / held | NO RELEASE CONDITION" in text, text)
        expect("every source read, none unread", unread == 0, log)
        expect("total rows", len(rows) == 8, rows)

        _, _, log2, unread2 = harvest([pathlib.Path(d, "missing-log")], pub)
        expect("a missing source is NOT READ, never an empty result",
               unread2 == 1 and any(l.startswith("NOT READ") for l in log2), log2)
    print("SELFTEST: " + (f"FAILED ({len(fails)})" if fails else "all cases passed"))
    sys.exit(1 if fails else 0)


def main():
    if "--selftest" in sys.argv[1:]:
        selftest()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--obs-dir", action="append", default=[], required=True)
    ap.add_argument("--publishing-dir", required=True)
    ap.add_argument("--skill", action="append", default=[])
    ap.add_argument("--review", action="append", default=[])
    ap.add_argument("--queue", action="append", default=[])
    ap.add_argument("--registry")
    a = ap.parse_args()
    rows, held, log, unread = harvest(a.obs_dir, a.publishing_dir, a.skill,
                                      a.review, a.queue, a.registry)
    print(render(rows, held, log))
    sys.exit(2 if unread else 0)


if __name__ == "__main__":
    main()
