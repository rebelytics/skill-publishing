#!/usr/bin/env python3
"""cut-release-branch.py — cutting a release branch is ONE act with three writes.
Part of the skill-publishing skill (CC BY 4.0 — Eoghan Henn and contributors).

A release branch under test has three pieces of state, each once specified as
its own rule and each forgotten at least once: the staging manifest entry
(so the next session sees a `release/` staging awaiting install), the
registry row's `under_test` field (so the publishing cycle holds the sync),
and the parked test-plan observation (so the merge review has a plan and a
date). Twice the branch was cut with only one of the three written. So the
writes are the side effects of one command, not follow-ups to remember, and
the command refuses to run at all if any target is unwritable — a partial cut
is the shape nothing downstream can detect.

  cut   <skill> <version> <install-date>   perform the three writes; refused
                                           for a skill the configuration's
                                           `test_branch_skills:` line does
                                           not name (absent: no skill)
  withdraw <skill> <reason>                undo a cut in one act: clear the
                                           hold with the reason, mark the
                                           newest manifest entry WITHDRAWN
                                           (no `release/` token left) and
                                           decline the test plan; refused
                                           before any write if one of the
                                           three is missing
  check [<skill>]                          reader side: the registry's
                                           `under_test` must equal the newest
                                           `release/` staging in the manifest;
                                           exit 1 on any mismatch (cycle step 0).
                                           A row cleared `by merge vX.Y.Z`
                                           retires a staging of that same
                                           version (OK); any other version
                                           is still a mismatch.
                                           Where a review clone exists under
                                           <workspace>/skill-publishing/repos/
                                           <repo>/ (--repos overrides; <repo>
                                           is the row's repository name, the
                                           skill name only where the row
                                           names none), the
                                           remote's `release/*` heads are listed
                                           (`git ls-remote --heads origin
                                           'release/*'`) and every ref other
                                           than the row's `under_test` branch
                                           is reported as a leftover to delete —
                                           a merged test branch nothing deleted.
                                           A leftover is reported, not a stop:
                                           it does not change the exit code.
                                           A skipped listing for a row that
                                           carries `under_test` turns the
                                           RESULT line into a WARNING.
  --selftest                               run the check against a throwaway
                                           registry and manifest (a Published
                                           row plus numbered candidate rows)
                                           and against fake remotes carrying
                                           leftover release branches; then
                                           cut and withdraw in a throwaway
                                           workspace

Only the skills the configuration names get a release branch: the line
`test_branch_skills: a, b` in <workspace>/skill-publishing/config.md
(--config overrides), task-observer when the line or the file is absent.
Every other skill ships each change on `main` with a version bump, so a cut
for it is refused before anything is read or written.

The registry is read in its full shape, not only the rows the check cares
about: candidate tables key their rows by number (`| 4 | some-skill |`), and
a bare number would match inside `release/v3.4.0` in a manifest heading. So a
row key must be a letter-led kebab-case name, and a skill is matched in a
manifest heading only between delimiters (space, backtick, asterisk,
parenthesis, slash, colon, comma), never across a dot.

The merge review date is derived ONE way everywhere it is written: the
publishing session on a fixed weekday (default Friday) that falls at least
--min-days (default 3) after the branch line is INSTALLED — not cut. A
Monday install merges that Friday (the maintainer's decided case); an
install on Wednesday or later runs to the second Friday, so the line always
has several real sessions behind it before the merge decision.

Workspace layout assumed (override with --registry, --manifest, --obs-log,
--repos, --config):
  <workspace>/skill-publishing/registry.md
  <workspace>/skill-publishing/config.md        (`test_branch_skills:` only)
  <workspace>/skill-publishing/repos/<repo>/    (review clones; `check` only)
  <workspace>/skill-updates/PENDING.md          (created if absent)
  <workspace>/skill-updates/<install-date>/<skill>/   (created if absent)
  <workspace>/skill-observations/observation-log/{,archive/,archive/.id-floor}

The observation id is derived exactly as task-observer's How to Log does:
max of (highest prefix in the log, highest in archive/, the .id-floor) + 1,
the floor written back, and a refusal if ANY file with that 4-digit prefix
exists in the log or its archive. (The archival sweep task-observer folds
into that command is not repeated here — it moves files between the two
directories the max already spans, so it cannot change the id.)

Never run this against a workspace you are not entitled to write: test
against a throwaway copy of the layout.
"""
import argparse, datetime, os, pathlib, re, subprocess, sys

WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6}
UT_VALUE_RE = re.compile(
    r"under_test:\s*(release/v[^\s`*|]+(?:\s*\([^)]*\))?|cleared\b[^`*|]*)")
RELEASE_RE = re.compile(r"release/v(\d+\.\d+\.\d+)")
# The version a cleared value records as merged (`cleared <date> by merge vX.Y.Z`).
MERGED_RE = re.compile(r"\bby merge v(\d+\.\d+\.\d+)\b")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
# The configuration line naming the skills that use release branches.
TEST_BRANCH_RE = re.compile(r"(?m)^[ \t>*-]*`?test_branch_skills:`?[ \t]*(.*)$")
DEFAULT_TEST_BRANCH_SKILLS = ()  # absent line: no skill gets a release branch
# The test-plan id a cut writes into the row and the manifest entry.
PLAN_ID_RE = re.compile(r"test plan(?: entry)?:?\s*(?:entry\s*)?\**(\d+)\**", re.I)
SKILL_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# A registry row key that can name a skill: letter-led kebab-case. Numbered
# candidate rows (`| 4 |`, `| 7a |`) are not skills.
ROW_RE = re.compile(r"^\|\s*(?:\*\*|`)?([a-z0-9-]+)(?:\*\*|`)?\s*\|")
ROW_KEY_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
# The repository a row names in its second cell (`owner/repo`): its review
# clone is repos/<repo>, which need not equal the skill name.
REPO_CELL_RE = re.compile(r"[A-Za-z0-9_.-]+/([A-Za-z0-9_.-]+?)(?:\.git)?(?=[`*\s]|$)")

OBSERVATION_TEMPLATE = """---
id: {id}
title: "Test plan for {skill} release/v{version} — installed {install}, merge review {merge}"
status: parked
type: internal
skill: [{skill}]
proposes_skill: []
target_file: []
siblings_checked: "n/a — release-branch test plan, generated by skill-publishing scripts/cut-release-branch.py"
area: "{skill} — release/v{version} branch line under test; skill-publishing registry row (under_test) and staging manifest"
date: {today}
session_context: "Branch line cut and staged at skill-updates/{install}/{skill}; installed {install}"
parked_until: {merge}
resolved:
resolution:
reference: "release/v{version}; staging skill-updates/{install}/{skill}; registry under_test written by the same act"
---

**Issue:** `{skill}` is running the `release/v{version}` line locally from {install}. The sync of its repo is held (`under_test` in the registry). A test period tests only what the period's activity happens to touch; every change on the branch needs evidence before it merges.

**Test plan — one row per change on the branch.** Classify each as *exercised naturally* (say what would exercise it during the period) or *unlikely to fire naturally* (give the fixture, the procedure and the pass criterion). Fill this in before the session that cut the branch ends.

| # | change | class | evidence to collect | result |
|---|---|---|---|---|
| 1 | | natural / synthetic | | |

**Merge review:** {merge_weekday} {merge} — the publishing session at least {min_days} days after the INSTALL date ({install}), not after the cut. The merge report lists every change beside its evidence; a change with neither does not merge. The merge clears `under_test` in the same act (`under_test: cleared <date> by merge v{version} (<sha>)`).

**Principle:** a branch is cut together with its test plan, its hold and its manifest entry, in one act — this observation, the registry field and the manifest entry were written by the same command and must never disagree.
"""

MANIFEST_ENTRY = """## {install} — {skill} `release/v{version}` branch line — release-branch staging (cut by cut-release-branch.py)

Staging anchor: `skill-updates/{install}/{skill}` — the `release/v{version}` line, installed {install}. Registry row carries `under_test: release/v{version} (since {install})` (previous value: {replaced}). Test plan: entry **{id}** (parked; unparks for the {merge_weekday} {merge} merge review — the publishing session at least {min_days} days after install). While `under_test` is set, any staged copy of this skill seeds from the branch line, never from live.

"""


def test_branch_skills(config):
    """(names, where they came from): the configuration's
    `test_branch_skills:` list, or the default when the file or line is
    absent. Names are comma- or space-separated, backticks ignored."""
    config = pathlib.Path(config)
    text = config.read_text(encoding="utf-8") if config.is_file() else ""
    m = TEST_BRANCH_RE.search(text)
    if not m:
        why = "no test_branch_skills: line" if text else "no configuration file"
        return set(DEFAULT_TEST_BRANCH_SKILLS), f"default ({why} at {config})"
    names = {n for n in re.split(r"[\s,`]+", m.group(1)) if SKILL_RE.match(n)}
    return names, f"test_branch_skills: in {config}"


def merge_review_date(install, min_days, weekday):
    d = install + datetime.timedelta(days=min_days)
    while d.weekday() != weekday:
        d += datetime.timedelta(days=1)
    return d


def writable(p):
    p = pathlib.Path(p)
    if p.exists():
        return p.is_file() and os.access(p, 2)
    return p.parent.is_dir() and os.access(p.parent, 2)


def find_row(lines, skill):
    rx = re.compile(r"^\|\s*(?:\*\*|`)?" + re.escape(skill) + r"(?:\*\*|`)?\s*\|")
    for i, l in enumerate(lines):
        if rx.match(l):
            return i
    return None


def derive_id(log_dir):
    archive = log_dir / "archive"
    nums = []
    for d in (log_dir, archive):
        for p in d.iterdir():
            m = re.match(r"^(\d+)", p.name)
            if m and p.suffix == ".md":
                nums.append(int(m.group(1)))
    floor = archive / ".id-floor"
    if floor.exists():
        raw = floor.read_text(encoding="utf-8").strip()
        if raw.isdigit():
            nums.append(int(raw))
    if not nums and any(log_dir.glob("*.md")):
        sys.exit("FATAL: ID COMMAND BROKEN — log is non-empty but no ids extracted")
    next_id = (max(nums) if nums else 0) + 1
    prefix = f"{next_id:04d}"
    clash = [p for d in (log_dir, archive) for p in d.glob(prefix + "-*")]
    if clash:
        sys.exit(f"FATAL: COLLISION — a file with prefix {prefix} exists: "
                 f"{clash[0]}; re-derive the id")
    return next_id, floor


def cmd_cut(a):
    if not SKILL_RE.match(a.skill):
        sys.exit(f"FATAL: skill name {a.skill!r} is not kebab-case")
    if not VERSION_RE.match(a.version):
        sys.exit(f"FATAL: version {a.version!r} is not X.Y.Z")
    ws = pathlib.Path(a.workspace)
    allowed, where = test_branch_skills(a.config or ws / "skill-publishing" / "config.md")
    if a.skill not in allowed:
        sys.exit(f"REFUSED — no write performed: {a.skill} does not use release "
                 f"branches ({where}: {', '.join(sorted(allowed)) or 'none'}); "
                 f"it ships on main with a version bump")
    install = datetime.date.fromisoformat(a.install_date)
    weekday = WEEKDAYS[a.weekday.lower()]
    merge = merge_review_date(install, a.min_days, weekday)
    merge_wd = a.weekday.capitalize()
    today = datetime.date.today().isoformat()

    registry = pathlib.Path(a.registry or ws / "skill-publishing" / "registry.md")
    manifest = pathlib.Path(a.manifest or ws / "skill-updates" / "PENDING.md")
    anchor = ws / "skill-updates" / a.install_date / a.skill
    log_dir = pathlib.Path(a.obs_log or ws / "skill-observations" / "observation-log")

    # --- refuse before writing anything -----------------------------------
    problems = []
    if not registry.is_file() or not writable(registry):
        problems.append(f"registry not writable: {registry}")
    else:
        reg_lines = registry.read_text(encoding="utf-8").splitlines(keepends=True)
        row = find_row(reg_lines, a.skill)
        if row is None:
            problems.append(f"no table row for {a.skill!r} in {registry}")
    if not writable(manifest):
        problems.append(f"manifest not writable: {manifest}")
    if not (log_dir.is_dir() and (log_dir / "archive").is_dir()
            and os.access(log_dir, 2)):
        problems.append(f"observation log (with archive/) not writable: {log_dir}")
    if not os.access(anchor.parent if anchor.parent.exists()
                                   else ws / "skill-updates", 2):
        problems.append(f"staging root not writable: {ws / 'skill-updates'}")
    if problems:
        sys.exit("REFUSED — no write performed:\n  " + "\n  ".join(problems))

    obs_id, floor = derive_id(log_dir)
    print(f"cut {a.skill} release/v{a.version}: installed {install}, "
          f"merge review {merge_wd} {merge} (>= {a.min_days} days after install)")
    if a.dry_run:
        print(f"dry run — would write: test-plan entry {obs_id:04d}, {registry.name} row, "
              f"{manifest}, {anchor}")
        return

    # (c) observation first: the other two writes point at its id
    obs_path = log_dir / f"{obs_id:04d}-test-plan-{a.skill}-release-v{a.version.replace('.', '-')}.md"
    with open(obs_path, "x", encoding="utf-8") as fh:      # noclobber create
        fh.write(OBSERVATION_TEMPLATE.format(
            id=obs_id, skill=a.skill, version=a.version, install=install,
            merge=merge, merge_weekday=merge_wd, today=today,
            min_days=a.min_days))
    floor.write_text(f"{obs_id}\n", encoding="utf-8")
    print(f"  wrote {obs_path}")

    # (b) registry row: replace any previous under_test value, record it
    line = reg_lines[row]
    m = UT_VALUE_RE.search(line)
    # keep the previous value short: its branch and since-date, not its own
    # replaced-chain, or the field grows by one clause per cut
    replaced = re.sub(r";[^)]*\)", ")", m.group(1).strip()) if m else "none"
    new_val = (f"under_test: release/v{a.version} (since {install}; merge review "
               f"{merge_wd} {merge}; test plan entry {obs_id}; replaced: {replaced})")
    if m:
        line = line[:m.start()] + new_val + line[m.end():]
    else:
        cells = line.split("|")
        idx = a.cell if a.cell < len(cells) - 1 else len(cells) - 2
        cells[idx] = f" **{new_val}** —" + cells[idx]
        line = "|".join(cells)
    reg_lines[row] = line
    registry.write_text("".join(reg_lines), encoding="utf-8")
    print(f"  wrote {registry} row for {a.skill} (replaced: {replaced})")

    # (a) staging anchor + manifest entry (newest first, under the H1)
    anchor.mkdir(parents=True, exist_ok=True)
    entry = MANIFEST_ENTRY.format(install=install, skill=a.skill,
                                  version=a.version, replaced=replaced,
                                  id=obs_id, merge=merge, merge_weekday=merge_wd,
                                  min_days=a.min_days)
    if manifest.exists():
        text = manifest.read_text(encoding="utf-8")
        hm = re.search(r"(?m)^## ", text)
        text = (text[:hm.start()] + entry + text[hm.start():]) if hm \
            else text.rstrip("\n") + "\n\n" + entry
    else:
        text = "# Staged skill updates awaiting review\n\n" + entry
    manifest.write_text(text, encoding="utf-8")
    print(f"  wrote {manifest} entry; anchor {anchor}")
    print("DONE — three writes performed by one act")


def set_frontmatter(text, fields):
    """`text` with each `key: value` of `fields` set inside its leading
    frontmatter block (replaced where the key exists, appended otherwise)."""
    m = re.match(r"---\n(.*?\n)---\n", text, re.S)
    if not m:
        return None
    fm = m.group(1)
    for k, v in fields.items():
        line = f"{k}: {v}\n"
        fm, n = re.subn(rf"(?m)^{re.escape(k)}:.*\n", lambda _: line, fm, count=1)
        if not n:
            fm += line
    return "---\n" + fm + "---\n" + text[m.end():]


def cmd_withdraw(a):
    """Undo a cut: the three writes of `cut`, reversed by one act."""
    if not SKILL_RE.match(a.skill):
        sys.exit(f"FATAL: skill name {a.skill!r} is not kebab-case")
    reason = " ".join(a.reason.split())
    if not reason or re.search(r"[|`*\"]", reason):
        sys.exit("FATAL: the reason must be non-empty and free of | ` * \" "
                 "(it is written into a table cell and a quoted field)")
    today = datetime.date.today().isoformat()
    ws = pathlib.Path(a.workspace)
    registry = pathlib.Path(a.registry or ws / "skill-publishing" / "registry.md")
    manifest = pathlib.Path(a.manifest or ws / "skill-updates" / "PENDING.md")
    log_dir = pathlib.Path(a.obs_log or ws / "skill-observations" / "observation-log")

    # --- refuse before writing anything -----------------------------------
    problems, plan_ids = [], []
    row = reg_lines = mline = man_lines = branch = None
    if not registry.is_file() or not writable(registry):
        problems.append(f"registry not writable: {registry}")
    else:
        reg_lines = registry.read_text(encoding="utf-8").splitlines(keepends=True)
        row = find_row(reg_lines, a.skill)
        m = UT_VALUE_RE.search(reg_lines[row]) if row is not None else None
        rm = RELEASE_RE.search(m.group(1)) if m else None
        if row is None:
            problems.append(f"no table row for {a.skill!r} in {registry}")
        elif not rm:
            problems.append(f"{a.skill}: the registry row carries no release/ "
                            f"hold to withdraw")
        else:
            branch = f"release/v{rm.group(1)}"
            plan_ids += PLAN_ID_RE.findall(m.group(1))
    if not manifest.is_file() or not writable(manifest):
        problems.append(f"manifest not writable: {manifest}")
    elif branch:
        man_lines = manifest.read_text(encoding="utf-8").splitlines(keepends=True)
        skill_rx = re.compile(r"(?:^|(?<=[\s`*(/:,]))" + re.escape(a.skill)
                              + r"(?=[\s`*)/:,]|$)")
        for i, l in enumerate(man_lines):
            if l.startswith("## ") and RELEASE_RE.search(l) and skill_rx.search(l):
                mline = i          # newest first: the first heading wins
                break
        if mline is None or RELEASE_RE.search(man_lines[mline]).group(0) != branch:
            problems.append(f"{a.skill}: the newest manifest release staging is not "
                            f"{branch} (run check first)")
        else:
            for l in man_lines[mline + 1:]:
                if l.startswith("## "):
                    break
                plan_ids += PLAN_ID_RE.findall(l)
    plan = None
    ids = sorted(set(plan_ids))
    if branch and len(ids) != 1:
        problems.append(f"{a.skill}: the hold and the manifest entry name "
                        f"{len(ids)} test-plan ids ({', '.join(ids) or 'none'}), "
                        f"not one")
    elif branch:
        found = [p for d in (log_dir, log_dir / "archive") if d.is_dir()
                 for p in d.glob(f"{int(ids[0]):04d}-*.md")]
        if len(found) != 1 or not writable(found[0]):
            problems.append(f"test plan {ids[0]}: not exactly one writable file "
                            f"in {log_dir}")
        else:
            plan = found[0]
    if problems:
        sys.exit("REFUSED — no write performed:\n  " + "\n  ".join(problems))

    plan_text = set_frontmatter(plan.read_text(encoding="utf-8"), {
        "status": "declined", "resolved": today,
        "resolution": f'"{a.skill}: withdrawn {today} — {reason}"'})
    if plan_text is None:
        sys.exit(f"REFUSED — no write performed: {plan} has no frontmatter block")
    # (c) test plan declined
    plan.write_text(plan_text, encoding="utf-8")
    print(f"  wrote {plan} (status: declined)")
    # (b) registry hold cleared, the reason in the value
    line = reg_lines[row]
    m = UT_VALUE_RE.search(line)
    reg_lines[row] = (line[:m.start()] + f"under_test: cleared {today} — "
                      f"withdrawn {branch[len('release/'):]}: {reason}" + line[m.end():])
    registry.write_text("".join(reg_lines), encoding="utf-8")
    print(f"  wrote {registry} row for {a.skill} (hold cleared)")
    # (a) manifest heading: WITHDRAWN, the release/ token gone, the rest kept
    h = man_lines[mline].rstrip("\n")
    man_lines[mline] = ("## WITHDRAWN " + today + " — " + h[3:].replace(
        branch, branch[len("release/"):]) + f" — withdrawn: {reason}\n")
    manifest.write_text("".join(man_lines), encoding="utf-8")
    print(f"  wrote {manifest} entry heading (WITHDRAWN)")
    print(f"DONE — {a.skill} {branch} withdrawn by one act; it ships on main")


def row_key(line):
    """The skill a registry table row names in its first cell, or None for a
    header, a separator or a numbered candidate row."""
    cm = ROW_RE.match(line)
    if cm and ROW_KEY_RE.match(cm.group(1)):
        return cm.group(1)
    return None


def published_rows(registry):
    """Skills keyed in the table under a `## Published` heading; None when the
    registry has no such heading (then every letter-led row counts)."""
    out, inside, seen = set(), False, False
    for l in registry.read_text(encoding="utf-8").splitlines():
        if l.startswith("## "):
            inside = l[3:].strip().lower().startswith("published")
            seen = seen or inside
            continue
        if inside:
            k = row_key(l)
            if k:
                out.add(k)
    return out if seen else None


def registry_under_test(registry):
    """{skill: branch or 'cleared'} for every table row carrying the field."""
    out = {}
    for l in registry.read_text(encoding="utf-8").splitlines():
        k = row_key(l)
        if not k:
            continue
        m = UT_VALUE_RE.search(l)
        if m:
            v = m.group(1)
            rm = RELEASE_RE.search(v)
            out[k] = f"release/v{rm.group(1)}" if rm else "cleared"
    return out


def registry_merged(registry):
    """{skill: release/vX.Y.Z} for every row whose field is cleared by a
    merge of a named version: that version's staging is retired."""
    out = {}
    for l in registry.read_text(encoding="utf-8").splitlines():
        k = row_key(l)
        m = UT_VALUE_RE.search(l) if k else None
        if m and m.group(1).startswith("cleared"):
            mm = MERGED_RE.search(m.group(1))
            if mm:
                out[k] = f"release/v{mm.group(1)}"
    return out


def registry_repos(registry):
    """{skill: repository name} from each row's second cell (`owner/repo`);
    a row that names no repository is absent, and its clone is looked up
    under the skill name."""
    out = {}
    for l in registry.read_text(encoding="utf-8").splitlines():
        k = row_key(l)
        cells = l.split("|")
        if k and len(cells) > 2:
            m = REPO_CELL_RE.search(cells[2].strip())
            if m:
                out[k] = m.group(1)
    return out


def manifest_release_stagings(manifest, skills):
    """{skill: newest release/ branch named in an H2 entry heading}; the file
    is newest-first, so the first heading per skill wins."""
    out = {}
    if not manifest.exists():
        return out
    for l in manifest.read_text(encoding="utf-8").splitlines():
        if not l.startswith("## "):
            continue
        rm = RELEASE_RE.search(l)
        if not rm:
            continue
        for s in skills:
            if re.search(r"(?:^|(?<=[\s`*(/:,]))" + re.escape(s)
                         + r"(?=[\s`*)/:,]|$)", l) and s not in out:
                out[s] = f"release/v{rm.group(1)}"
    return out


def remote_release_refs(clone):
    """({branch: short sha} for origin's `release/*` heads, None) read from a
    review clone with `git ls-remote --heads origin 'release/*'`; (None,
    reason) when there is no clone or the remote cannot be listed — the
    check then says so rather than guessing that the remote is clean."""
    clone = pathlib.Path(clone)
    if not ((clone / ".git").exists() or (clone / "HEAD").is_file()):
        return None, f"no review clone at {clone}"
    try:
        r = subprocess.run(["git", "-C", str(clone), "ls-remote", "--heads",
                            "origin", "release/*"], capture_output=True,
                           text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"git ls-remote failed: {e.__class__.__name__}"
    if r.returncode != 0:
        why = (r.stderr.strip().splitlines() or ["exit %d" % r.returncode])[0]
        return None, f"git ls-remote failed: {why}"
    out = {}
    for l in r.stdout.splitlines():
        sha, _, ref = l.partition("\t")
        if ref.startswith("refs/heads/"):
            out[ref[len("refs/heads/"):]] = sha[:12]
    return out, None


def leftover_release_refs(skills, reg, repos, only=None, names=None):
    """(leftover list, held skills whose listing was skipped): for each skill
    with a review clone — repos/<the row's repository name> — every remote
    `release/*` head that is not the row's `under_test` branch. A cleared or
    absent field means no branch is expected, so any `release/` ref is a
    leftover."""
    leftovers, skipped_held = [], []
    names = names or {}
    for s in sorted(skills):
        if only and s != only:
            continue
        refs, why = remote_release_refs(pathlib.Path(repos) / names.get(s, s))
        if refs is None:
            print(f"[SKIP] {s}: remote release/ refs not listed — {why}")
            if reg.get(s) not in (None, "cleared"):
                skipped_held.append(s)
            continue
        held = reg.get(s) if reg.get(s) not in (None, "cleared") else None
        extra = sorted(b for b in refs if b != held)
        print(f"[OK]   {s}: remote release/ refs: "
              f"{', '.join(sorted(refs)) or 'none'}; expected: {held or 'none'}")
        for b in extra:
            leftovers.append(f"{s}: {b} ({refs[b]}) — leftover release branch "
                             f"— delete after confirming it merged "
                             f"(git push origin --delete {b})")
    return leftovers, skipped_held


def cmd_check(a):
    ws = pathlib.Path(a.workspace)
    registry = pathlib.Path(a.registry or ws / "skill-publishing" / "registry.md")
    manifest = pathlib.Path(a.manifest or ws / "skill-updates" / "PENDING.md")
    repos = pathlib.Path(getattr(a, "repos", None)
                         or ws / "skill-publishing" / "repos")
    reg = registry_under_test(registry)
    skills = set(reg) | ({a.skill} if a.skill else set())
    # every published skill can have a manifest staging; candidate tables
    # are input too, but only their letter-led keys, and only when the
    # registry has no Published table to restrict to
    pub = published_rows(registry)
    if pub is None:
        pub = {k for k in map(row_key, registry.read_text(
            encoding="utf-8").splitlines()) if k}
    skills |= pub
    man = manifest_release_stagings(manifest, skills)
    merged = registry_merged(registry)
    bad = []
    for s in sorted(skills):
        if a.skill and s != a.skill:
            continue
        r, m = reg.get(s), man.get(s)
        if r is None and m is None:
            continue
        held = r is not None and r != "cleared"
        if held and m == r:
            print(f"[OK]   {s}: registry {r} == newest manifest release staging {m}")
        elif not held and m is None:
            print(f"[OK]   {s}: registry {r}, no release staging in the manifest")
        elif r == "cleared" and merged.get(s) == m:
            print(f"[OK]   {s}: registry cleared by merge v{m[len('release/v'):]}; "
                  f"newest manifest release staging {m} is retired (same version)")
        elif not held and m is not None:
            state = (f"cleared by merge {merged[s][len('release/'):]}"
                     if s in merged else r or "absent")
            bad.append(f"{s}: manifest names {m} but registry under_test is "
                       f"{state} — the hold was not written, or the merge "
                       f"cleared a different version")
        else:
            bad.append(f"{s}: registry under_test {r} but newest manifest release "
                       f"staging is {m or 'absent'}")
    for b in bad:
        print("[MISMATCH] " + b)
    leftovers, skipped = leftover_release_refs(skills, reg, repos, a.skill,
                                               registry_repos(registry))
    for l in leftovers:
        print("[LEFTOVER] " + l)
    print("RESULT: " + ("STOP — ask the maintainer before syncing" if bad
                        else "WARNING — under_test and manifest agree, but the "
                        "remote release/ refs were not listed for "
                        + ", ".join(skipped) + " (held rows), so leftovers are "
                        "unchecked" if skipped
                        else "under_test and manifest agree")
          + (f"; {len(leftovers)} leftover release branch(es) to delete"
             if leftovers else ""))
    sys.exit(1 if bad else 0)


def selftest():
    """The check against a registry in its full shape: a Published table
    (one row held, one cleared) plus numbered candidate tables, and a
    manifest whose heading carries a version with a bare digit in it; then
    against fake remotes (a bare repo as origin of a review clone) whose
    `release/*` heads do or do not match the row's `under_test` branch. Git
    runs with the global and system config ignored."""
    import contextlib, io, tempfile
    os.environ.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")

    def fake_remote(ws, skill, branches):
        """A review clone at <ws>/skill-publishing/repos/<skill> (a repository
        name) whose origin is a bare repo carrying the given release/* heads."""
        clone = pathlib.Path(ws, "skill-publishing", "repos", skill)
        bare = pathlib.Path(ws, "remotes", skill + ".git")
        bare.mkdir(parents=True)
        clone.mkdir(parents=True)
        run = lambda *c: subprocess.run(["git", *c], check=True,
                                        capture_output=True, text=True)
        run("init", "-q", "--bare", str(bare))
        run("-C", str(clone), "init", "-q", "-b", "main")
        run("-C", str(clone), "config", "user.name", "Tester")
        run("-C", str(clone), "config", "user.email", "tester@example.org")
        run("-C", str(clone), "config", "commit.gpgsign", "false")
        run("-C", str(clone), "commit", "-q", "--allow-empty", "-m", "seed")
        run("-C", str(clone), "remote", "add", "origin", str(bare))
        for b in branches:
            run("-C", str(clone), "push", "-q", "origin", f"HEAD:refs/heads/{b}")

    registry = """# Registry

## Published (2)

| Skill | Repo | Notes |
|---|---|---|
| **alpha-skill** | `owner/alpha-skill` | under_test: release/v3.4.0 (since INSTALL-DATE) |
| beta-skill | `owner/beta-skill` | under_test: cleared MERGE-DATE by merge v1.1.0 (abc1234) |

## Tier 1 — candidates

| # | Skill | Lines |
|---|---|---|
| 4 | gamma-skill | 285 |
| 7a | delta-skill | 517 |
"""
    manifest = """# Staged skill updates awaiting review

## INSTALL-DATE — alpha-skill `release/v3.4.0` branch line — release-branch staging

Staging anchor: `skill-updates/INSTALL-DATE/alpha-skill`.
"""
    # An older staging of a branch the registry records as merged.
    retired = """
## CUT-DATE — beta-skill `release/v1.1.0` branch line — release-branch staging

Staging anchor: `skill-updates/CUT-DATE/beta-skill`.
"""
    # (name, registry, manifest, exit wanted, remotes {skill: [branches]},
    #  lines that must appear, lines that must not)
    cases = [("registry with numbered rows agrees", registry, manifest, 0,
              {}, [], ["[LEFTOVER]"]),
             ("hold missing for a staged branch", registry.replace(
                 "under_test: release/v3.4.0 (since INSTALL-DATE)", "clean"),
              manifest, 1, {}, [], []),
             ("no Published heading: letter-led rows still checked", registry
              .replace("## Published (2)", "## Skills"), manifest, 0, {}, [], []),
             ("held row: a second remote release/ ref is a leftover, exit 0",
              registry, manifest, 0,
              {"alpha-skill": ["release/v3.4.0", "release/v3.3.0"]},
              ["[LEFTOVER] alpha-skill: release/v3.3.0 (",
               "leftover release branch — delete after confirming it merged",
               "git push origin --delete release/v3.3.0",
               "1 leftover release branch(es) to delete"],
              ["[LEFTOVER] alpha-skill: release/v3.4.0"]),
             ("held row: only the held ref on the remote reports nothing",
              registry, manifest, 0, {"alpha-skill": ["release/v3.4.0"]},
              ["[OK]   alpha-skill: remote release/ refs: release/v3.4.0; "
               "expected: release/v3.4.0"], ["[LEFTOVER]"]),
             ("cleared row: any remote release/ ref is a leftover",
              registry, manifest, 0, {"beta-skill": ["release/v1.1.0"]},
              ["[LEFTOVER] beta-skill: release/v1.1.0 ("], []),
             ("no review clone for a held row: skipped, never a mismatch, "
              "and the RESULT is a warning", registry, manifest, 0, {},
              ["[SKIP] alpha-skill: remote release/ refs not listed — no "
               "review clone at ", "RESULT: WARNING", "for alpha-skill (held"],
              ["[LEFTOVER]", "[MISMATCH]", "RESULT: under_test and manifest agree"]),
             ("no review clone for a cleared row only: the RESULT still agrees",
              registry.replace("under_test: release/v3.4.0 (since INSTALL-DATE)",
                               "under_test: cleared MERGE-DATE by merge v3.4.0 (abc1234)"),
              "", 0, {"alpha-skill": []},
              ["[SKIP] beta-skill: remote release/ refs not listed",
               "RESULT: under_test and manifest agree"], ["RESULT: WARNING"]),
             ("the clone is resolved by the row's repository name, not the "
              "skill name", registry.replace("`owner/alpha-skill`",
                                             "`owner/one-alpha-repo`"),
              manifest, 0,
              {"one-alpha-repo": ["release/v3.4.0", "release/v3.3.0"]},
              ["[LEFTOVER] alpha-skill: release/v3.3.0 (",
               "[OK]   alpha-skill: remote release/ refs:"],
              ["[SKIP] alpha-skill", "RESULT: WARNING"]),
             ("cleared by merge v1.1.0 + manifest release/v1.1.0 heading: the "
              "staging is retired, OK", registry, manifest + retired, 0, {},
              ["[OK]   beta-skill: registry cleared by merge v1.1.0; newest "
               "manifest release staging release/v1.1.0 is retired"],
              ["[MISMATCH]"]),
             ("cleared by merge v1.1.0 + manifest release/v1.2.0 heading: a "
              "different version is a mismatch", registry,
              manifest + retired.replace("v1.1.0", "v1.2.0"), 1, {},
              ["[MISMATCH] beta-skill: manifest names release/v1.2.0 but "
               "registry under_test is cleared by merge v1.1.0"], [])]
    failed = 0
    for name, reg, man, want, remotes, must, must_not in cases:
        with tempfile.TemporaryDirectory() as d:
            rp, mp = pathlib.Path(d, "registry.md"), pathlib.Path(d, "PENDING.md")
            rp.write_text(reg, encoding="utf-8")
            mp.write_text(man, encoding="utf-8")
            for skill, branches in remotes.items():
                fake_remote(d, skill, branches)
            ns = argparse.Namespace(workspace=d, registry=str(rp),
                                    manifest=str(mp), skill=None, repos=None)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                try:
                    cmd_check(ns)
                    got = 0
                except SystemExit as e:
                    got = e.code or 0
            out = buf.getvalue()
            ok = got == want and "[MISMATCH] 4:" not in out \
                and "[MISMATCH] 7a:" not in out \
                and all(m in out for m in must) \
                and not any(m in out for m in must_not)
            failed += not ok
            print(f"[{'PASS' if ok else 'FAIL'}] {name} (exit {got}, want {want})")
            if not ok:
                print("        " + out.replace("\n", "\n        "))
    failed += selftest_cut_withdraw()
    print("SELFTEST: " + ("FAILED" if failed else "all cases passed"))
    sys.exit(1 if failed else 0)


def selftest_cut_withdraw():
    """cut refused outside the configured list and allowed inside it; then
    withdraw after a real cut, after which check agrees; withdraw refused
    with nothing written when there is no hold. Returns the failure count."""
    import contextlib, io, tempfile
    registry = """# Registry

## Published (2)

| Skill | Repo | Notes |
|---|---|---|
| alpha-skill | `owner/alpha-skill` | clean |
| beta-skill | `owner/beta-skill` | clean |
"""

    def run(fn, ns):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                fn(ns)
                code = 0
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
                if not isinstance(e.code, int) and e.code:
                    print(e.code)
        return code, buf.getvalue()

    def workspace(d, config):
        ws = pathlib.Path(d)
        (ws / "skill-publishing").mkdir()
        (ws / "skill-updates").mkdir()
        (ws / "skill-observations" / "observation-log" / "archive").mkdir(parents=True)
        (ws / "skill-publishing" / "registry.md").write_text(registry, encoding="utf-8")
        (ws / "skill-updates" / "PENDING.md").write_text(
            "# Staged skill updates awaiting review\n\n## OLD — unrelated entry\n\nx\n",
            encoding="utf-8")
        if config is not None:
            (ws / "skill-publishing" / "config.md").write_text(config, encoding="utf-8")
        return ws

    def ns(ws, cmd, **kw):
        base = dict(workspace=str(ws), registry=None, manifest=None, obs_log=None,
                    repos=None, config=None, skill=None)
        if cmd == "cut":
            base.update(version="2.0.0", install_date="2030-01-07", min_days=3,
                        weekday="friday", cell=3, dry_run=False)
        base.update(kw)
        return argparse.Namespace(**base)

    failed = 0

    def expect(name, ok, out=""):
        nonlocal failed
        failed += not ok
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        if not ok:
            print("        " + out.replace("\n", "\n        "))

    with tempfile.TemporaryDirectory() as d:
        ws = workspace(d, None)
        code, out = run(cmd_cut, ns(ws, "cut", skill="alpha-skill"))
        expect("cut: no config file — no skill gets a branch, alpha-skill refused",
               code == 1 and "REFUSED — no write performed" in out
               and "default (no configuration file" in out
               and "ships on main" in out
               and not list((ws / "skill-observations" / "observation-log").glob("*.md")), out)
    with tempfile.TemporaryDirectory() as d:
        ws = workspace(d, "# Config\n\n- `test_branch_skills:` task-observer, alpha-skill\n")
        code, out = run(cmd_cut, ns(ws, "cut", skill="beta-skill"))
        expect("cut: a skill outside the configured list is refused, nothing written",
               code == 1 and "test_branch_skills: in" in out
               and "alpha-skill, task-observer" in out
               and "under_test" not in (ws / "skill-publishing" / "registry.md").read_text(), out)
        code, out = run(cmd_cut, ns(ws, "cut", skill="alpha-skill"))
        reg = (ws / "skill-publishing" / "registry.md").read_text()
        expect("cut: a listed skill is cut (three writes)",
               code == 0 and "DONE — three writes" in out
               and "under_test: release/v2.0.0" in reg, out)
        code, out = run(cmd_withdraw, ns(ws, "withdraw", skill="beta-skill",
                                         reason="not needed"))
        expect("withdraw: no hold on the row — refused, nothing written",
               code == 1 and "carries no release/ hold" in out, out)
        code, out = run(cmd_withdraw, ns(ws, "withdraw", skill="alpha-skill",
                                         reason="a | b"))
        expect("withdraw: a reason with a table delimiter is refused",
               code == 1 and "free of" in out, out)
        code, out = run(cmd_withdraw, ns(ws, "withdraw", skill="alpha-skill",
                                         reason="maintainer decision: ships on main"))
        reg = (ws / "skill-publishing" / "registry.md").read_text()
        man = (ws / "skill-updates" / "PENDING.md").read_text()
        plan = next((ws / "skill-observations" / "observation-log").glob("0001-*.md")).read_text()
        expect("withdraw: hold cleared with the reason, manifest WITHDRAWN without "
               "release/, test plan declined — one act",
               code == 0 and "DONE — alpha-skill release/v2.0.0 withdrawn" in out
               and "under_test: cleared " in reg and "withdrawn v2.0.0: maintainer decision" in reg
               and "release/v2.0.0" not in reg.split("withdrawn")[1]
               and "## WITHDRAWN " in man
               and not any(l.startswith("## ") and "release/" in l for l in man.splitlines())
               and "the `release/v2.0.0` line, installed" in man
               and "`v2.0.0` branch line" in man and "## OLD — unrelated entry" in man
               and "\nstatus: declined\n" in plan and "\nresolved: " in plan
               and 'resolution: "alpha-skill: withdrawn ' in plan
               and "\nstatus: parked\n" not in plan, out)
        code, out = run(cmd_check, ns(ws, "check"))
        expect("check after withdraw: registry cleared, no release staging — agree",
               code == 0 and "[OK]   alpha-skill: registry cleared, no release staging" in out
               and "[MISMATCH]" not in out, out)
        code, out = run(cmd_withdraw, ns(ws, "withdraw", skill="alpha-skill",
                                         reason="again"))
        expect("withdraw twice: the second is refused (no hold left)",
               code == 1 and "carries no release/ hold" in out, out)
    return failed


def main():
    if "--selftest" in sys.argv[1:]:
        selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=".", help="workspace root")
    ap.add_argument("--registry"); ap.add_argument("--manifest")
    ap.add_argument("--obs-log")
    ap.add_argument("--config", help="configuration file holding the "
                    "test_branch_skills: line (default "
                    "<workspace>/skill-publishing/config.md)")
    ap.add_argument("--repos", help="directory of review clones, one per "
                    "skill (default <workspace>/skill-publishing/repos)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cut")
    c.add_argument("skill"); c.add_argument("version"); c.add_argument("install_date")
    c.add_argument("--min-days", type=int, default=3)
    c.add_argument("--weekday", default="friday", choices=sorted(WEEKDAYS))
    c.add_argument("--cell", type=int, default=3,
                   help="table cell to prepend the field to when the row has none")
    c.add_argument("--dry-run", action="store_true")
    c.set_defaults(fn=cmd_cut)
    w = sub.add_parser("withdraw")
    w.add_argument("skill"); w.add_argument("reason")
    w.set_defaults(fn=cmd_withdraw)
    k = sub.add_parser("check")
    k.add_argument("skill", nargs="?")
    k.set_defaults(fn=cmd_check)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
