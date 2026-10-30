#!/usr/bin/env python3
"""confidentiality_scan.py — tripwire scan for published/publishable skill trees.
Part of the skill-publishing skill (CC BY 4.0 — Eoghan Henn and contributors).

Scans every file under the given paths (skipping .git/) for the terms in the
config's ```tripwire-terms``` fenced block — case-insensitively, as
substrings, over the FULL tree, never only a diff. The fenced block is the
ONLY source of terms: the script prints the block's line count beside the
term count it parsed and exits non-zero when the two disagree or the block is
missing — it never falls back to a heuristic read of the config. Binary files
cannot be text-scanned; they are reported as hits on the pseudo-term
__binary__ so each gets one deliberate human classification instead of silent
exemption. Hits classified in the baseline pass; any NEW hit exits non-zero.

With --dates the same files are also scanned for dated first-party claim
shapes (DATE_SHAPES below). A shape matches anywhere in a line, whatever the
words around it ("verified 2026-06-10", "on 2026-06-10", "as of June 2026"
all hit) — the claim word is not part of the pattern, so sentence position
cannot hide a date. The set of shapes is an enumeration: the output names
the shapes that ran, and a clean --dates pass is a lower bound, not a proof.
Date hits classify in the baseline like term hits, keyed on the matched text
(a vendor-published changelog date, a calendar example) or on the pseudo-term
__date__ to classify every date in one file.

Skill content — SKILL.md and every file under a references/ or scripts/
directory — is also read for the repository-bound reference shape `#NN` to
`#NNNN` (an issue, PR or observation number): a number that resolves only
against a tracker is process leaking into the bundle. README, CONTRIBUTING,
LICENSE and other repo-root prose are never read for it, since issue links
belong there. A hit classifies like a term hit, keyed on the matched text
(a three-digit colour code, say) or on the pseudo-term __ref__ for every
reference in one file. The shape runs on every scan, not only with --dates.

A drafts file — replies.md or prefill.json by name, or any file scanned
with --drafts — is public text written before posting, so --dates judges it
differently: a date that has fully elapsed is a fact and passes; a date
that is today or later (iso, dmy and mon-year shapes; an ambiguous
day/month order counts whichever reading is later) is a promise of a
schedule and is a draft defect. Tripwire terms still apply to it; the
reference shape does not (a reply may cite the issue it answers).

With --fingerprint the script runs a different pass and REPORTS, never
fails: the recognisability read the term list cannot make. Over a tree or a
file list (pass the files changed since the last published tree), it prints
(a) every sentence carrying an anecdote marker ("observed", "once", "in one
project/account/session/engagement", "the client", "went live", "for a week",
"in the case that produced") together with a number in the same sentence —
the shape of an engagement story; and (b) per Markdown heading section, the
example-like tokens (backticked literals, quoted strings, capitalised
multi-word names), so a reviewer reads a section's examples as one set and
sees when they all come from one vertical. The output ENDS by naming what it
did not look at — binaries, data and fixture files, Markdown tables, fenced
blocks, tokens in non-Markdown files — because an extract that bounds a
reader's attention must state its own boundary, or reading it passes for the
check.

Usage:
  confidentiality_scan.py --config CONFIG.md [--baseline BASELINE.md] [--dates] PATH...
  confidentiality_scan.py --config CONFIG.md --dates [--drafts] replies.md
  confidentiality_scan.py --fingerprint PATH...
  confidentiality_scan.py --selftest

Baseline line format ('|'-separated, one classified hit per line):
  <repo-name>/<path-in-repo>|<term, matched date or reference, __binary__, __date__ or __ref__>|<role and reason>
The key is the hit's path relative to the PARENT of the scanned root, i.e.
the scanned directory's own name followed by the path inside it — so a file
under .../repos/my-skill/ and the same file under $HOME/x/my-skill/ both key
as my-skill/<path>. A single-file root keys as <parent-dir-name>/<file>.
A hit is classified when a baseline line's key occurs in the hit's repo-
relative key OR in its full path (backwards compatibility) AND the term
matches (case-insensitive).
"""
import argparse, datetime, pathlib, re, sys

# Dated first-party claim shapes — extend HERE, never as a prose pattern.
# Each is (name, regex); all run case-insensitively. Bare years are not a
# shape ("2026" alone fires on version numbers and vendor facts).
DATE_SHAPES = [
    ("iso",        r"\b20\d{2}-\d{2}-\d{2}\b"),                   # 2026-06-10
    ("dmy",        r"\b\d{1,2}/\d{1,2}/20\d{2}\b"),                # 10/06/2026, 6/10/2026
    ("mon-year",   r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)"
                   r"[a-z]*\.? 20\d{2}\b"),                         # Jun 2026, June 2026
    ("quarter",    r"\bq[1-4] 20\d{2}\b"),                          # Q2 2026
    ("as-of-year", r"\bas of 20\d{2}\b"),                           # as of 2026
]

# The one exempt dated form (maintainer decision): a measured fact's paired
# verification line, "Last verified YYYY-MM-DD · Re-test: `<one command>`".
# A date inside such a pair is reported as exempt, never as a hit; the pair
# without its backticked re-test command is not exempt.
VERIFIED_PAIR_RE = re.compile(
    r"\bLast verified (20\d{2}-\d{2}-\d{2}) · Re-test: `[^`]+`")

# Repository-bound reference shape, read in skill content only: an issue, PR
# or observation number. Two to four digits — `#1` is a list marker or a
# footnote more often than a reference, five digits is not a tracker number
# the scan has met. `&#123;` (an HTML entity) and `a#12` are not references.
REF_SHAPE = ("issue-ref", r"(?<![\w&])#\d{2,4}\b")
SKILL_CONTENT_DIRS = {"references", "scripts"}
# Drafts files: public replies written before posting, judged for future
# dates rather than for any date.
DRAFTS_NAMES = {"replies.md", "prefill.json"}
FUTURE_SHAPES = ("iso", "dmy", "mon-year")
MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
     "nov", "dec"), 1)}


def skill_content(path, root):
    """True for a file that ships inside a skill — SKILL.md, or anything
    under a references/ or scripts/ directory of the scanned root. The path
    is read relative to the root so a directory above it named `scripts`
    cannot make a README skill content."""
    root = pathlib.Path(root).resolve()
    if root.is_file():
        parts = (root.parent.name, root.name)
    else:
        parts = pathlib.Path(path).resolve().relative_to(root).parts
    return parts[-1] == "SKILL.md" or bool(SKILL_CONTENT_DIRS & set(parts[:-1]))


def elapsed(shape, text, today):
    """True when a matched date lies wholly before the run date. A date that
    could still be today or later — an ambiguous day/month order counts
    whichever reading is later; a month that has not ended; a malformed
    date — is not elapsed, so a drafts file reports it."""
    nums = [int(x) for x in re.findall(r"\d+", text)]
    readings = []
    if shape == "iso":
        y, m, d = nums
        candidates = [(y, m, d)]
    elif shape == "dmy":
        a, b, y = nums
        candidates = [(y, b, a), (y, a, b)]
    elif shape == "mon-year":
        return (nums[0], MONTHS[text[:3].lower()]) < (today.year, today.month)
    else:
        return False
    for y, m, d in candidates:
        try:
            readings.append(datetime.date(y, m, d))
        except ValueError:
            continue
    return bool(readings) and all(r < today for r in readings)

# Fingerprint pass — anecdote markers and the number shapes they travel with.
ANECDOTE_RE = re.compile(
    r"\b(?:observed|once|in one (?:project|account|session|engagement|client|"
    r"run|market|release)|the client(?:'s)?|went live|for a week|"
    r"in the case that produced)\b", re.I)
NUMBER_RE = re.compile(
    r"\b\d[\d,.]*\b|\b(?:two|three|four|five|six|seven|eight|nine|ten|eleven|"
    r"twelve|dozen|dozens|hundred|hundreds|thousand)\b", re.I)
TOKEN_RES = [re.compile(r"`([^`\n]+)`"),
             re.compile(r"\"([^\"\n]{2,80})\"|\u201c([^\u201d\n]{2,80})\u201d"),
             re.compile(r"\b[A-Z][\w&'-]*(?:\s+[A-Z][\w&'-]*)+")]
DATA_SUFFIXES = {".csv", ".tsv", ".json", ".jsonl", ".yaml", ".yml", ".xml",
                 ".ndjson", ".parquet", ".xlsx", ".xls"}
FIXTURE_PARTS = {"fixture", "fixtures", "testdata", "samples", "sample-data"}


def fingerprint(paths):
    """Report lines for the fingerprint pass; never a verdict."""
    anecdotes, sections = [], []
    skipped = {"binary": [], "data/fixture": [], "tables": {}, "fenced": {},
               "non-markdown": []}
    for root in paths:
        rootp = pathlib.Path(root)
        files = [rootp] if rootp.is_file() else sorted(
            f for f in rootp.rglob("*") if f.is_file() and ".git" not in f.parts)
        for f in files:
            try:
                raw = f.read_bytes()
            except OSError:
                continue
            if b"\x00" in raw[:8192]:
                skipped["binary"].append(str(f))
                continue
            if f.suffix.lower() in DATA_SUFFIXES or \
                    FIXTURE_PARTS & {x.lower() for x in f.parts}:
                skipped["data/fixture"].append(str(f))
                continue
            md = f.suffix.lower() in (".md", ".markdown")
            if not md:
                skipped["non-markdown"].append(str(f))
            text = raw.decode("utf-8", errors="ignore")
            heading, head_line, para = f"{f.name} (top)", 1, []
            tokens = {}
            fence = False

            def flush():
                # para holds (line number, text); a sentence reports the line
                # it starts on
                sent_text, starts = "", []
                for ln, t in para:
                    starts.append((len(sent_text), ln))
                    sent_text += t.replace("**", "") + " "
                pos = 0
                for sent in re.split(r"(?<=[.!?])\s+", sent_text):
                    at = sent_text.find(sent, pos)
                    pos = at + len(sent)
                    ln = max((l for o, l in starts if o <= at), default=0)
                    if ANECDOTE_RE.search(sent) and NUMBER_RE.search(sent):
                        anecdotes.append(f"{f}:{ln}: {sent.strip()[:220]}")
                    if not md:
                        continue
                    for i, rx in enumerate(TOKEN_RES):
                        for m in rx.finditer(sent):
                            tok = next((g for g in m.groups() if g), m.group(0))
                            if i == 2 and m.start() == 0:
                                tok = tok.split(None, 1)[1] if " " in tok else ""
                                if " " not in tok:
                                    continue
                            tokens.setdefault(tok.strip(), None)
                para.clear()

            def close_section():
                if md and tokens:
                    sections.append(f"{f}:{head_line} {heading}\n    "
                                    + " · ".join(tokens))
                tokens.clear()

            for n, line in enumerate(text.splitlines(), 1):
                if md and re.match(r"^\s*(```|~~~)(?!.*(```|~~~))", line):
                    fence = not fence
                    skipped["fenced"][str(f)] = skipped["fenced"].get(str(f), 0) + 1
                    flush()
                    continue
                if fence:
                    skipped["fenced"][str(f)] = skipped["fenced"].get(str(f), 0) + 1
                    continue
                if md and line.lstrip().startswith("|"):
                    skipped["tables"][str(f)] = skipped["tables"].get(str(f), 0) + 1
                    flush()
                    continue
                if md and re.match(r"^#{1,6}\s", line):
                    flush()
                    close_section()
                    heading, head_line = line.strip(), n
                    continue
                if not line.strip():
                    flush()
                    continue
                para.append((n, line.strip()))
            flush()
            close_section()
    out = [f"ANECDOTE SENTENCES (marker + number in one sentence): {len(anecdotes)}"]
    out += ["  " + a for a in anecdotes]
    out.append(f"EXAMPLE TOKENS PER SECTION (read each set for one vertical): "
               f"{len(sections)} sections")
    out += ["  " + x for x in sections]
    out.append("NOT LOOKED AT — read these by hand; this report is silent about them:")
    out.append(f"  binary files: {len(skipped['binary'])}"
               + "".join("\n    " + x for x in skipped["binary"]))
    out.append(f"  data and fixture files (csv/json/yaml/xml, fixture paths): "
               f"{len(skipped['data/fixture'])}"
               + "".join("\n    " + x for x in skipped["data/fixture"]))
    out.append(f"  Markdown table rows: {sum(skipped['tables'].values())} in "
               f"{len(skipped['tables'])} files"
               + "".join(f"\n    {k}: {v}" for k, v in skipped["tables"].items()))
    out.append(f"  fenced-block lines: {sum(skipped['fenced'].values())} in "
               f"{len(skipped['fenced'])} files"
               + "".join(f"\n    {k}: {v}" for k, v in skipped["fenced"].items()))
    out.append(f"  example tokens in non-Markdown files (docstrings, usage strings, "
               f"defaults): {len(skipped['non-markdown'])} files — anecdote "
               f"sentences were read there, tokens were not"
               + "".join("\n    " + x for x in skipped["non-markdown"]))
    out.append("  always: numbers with no anecdote marker, and any story or "
               "vertical told without these markers — the vertical-clustering "
               "and engagement-narrative reads are human")
    return out


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        t = pathlib.Path(d, "tree")
        (t / "references").mkdir(parents=True)
        (t / "SKILL.md").write_text(
            "# Guide\n\n## Scoring\n\nIn one engagement, 42 prompts went live "
            "broken. Use `--market` with \"sample label\" and Northwind Traders "
            "as the example.\nThis gate checks 3 rows.\n\n| a | 99 |\n|---|---|\n\n"
            "```\nobserved once in 7 runs\n```\n", encoding="utf-8")
        (t / "scripts").mkdir()
        (t / "scripts" / "tool.py").write_text(
            '"""Tool.\n\nThis was observed once across 3 accounts.\n"""\n')
        (t / "references" / "data.csv").write_text("a,b\n1,2\n")
        (t / "logo.png").write_bytes(b"\x89PNG\x00\x00")
        out = "\n".join(fingerprint([str(t)]))
    checks = {
        "two anecdote sentences (md prose + script docstring)":
            "ANECDOTE SENTENCES (marker + number in one sentence): 2" in out,
        "a number without a marker is not an anecdote": "checks 3 rows" not in out,
        "fenced text is not read as prose": "7 runs" not in out.split("NOT LOOKED")[0],
        "tokens listed as a set":
            all(x in out for x in ("--market", "sample label", "Northwind Traders")),
        "boundary names the binary": "logo.png" in out.split("NOT LOOKED")[1],
        "boundary names the data file": "data.csv" in out.split("NOT LOOKED")[1],
        "boundary names the table rows": "Markdown table rows: 2 in 1" in out,
        "boundary names the fenced lines": "fenced-block lines: 3 in 1" in out,
        "the report ends with its boundary": out.rstrip().endswith("reads are human"),
    }
    # The tripwire scan: the reference shape in skill content only, and the
    # future-date rule on a drafts file beside the any-date rule elsewhere.
    today = datetime.date(2026, 6, 15)
    # Reference fixtures are built at run time ("#" + digits) so this
    # script, itself skill content, does not carry the shape it scans for.
    r42, r289, r333, r1234, r1001, r2026 = ("#" + n for n in
                                          ("42", "289", "333", "1234", "1001", "2026"))
    with tempfile.TemporaryDirectory() as d:
        t = pathlib.Path(d, "my-skill")
        (t / "references").mkdir(parents=True)
        (t / "scripts").mkdir()
        (t / "SKILL.md").write_text(f"# Guide\n\nSee issue {r42} and `{r333}`.\n"
                                    "Verified 2026-06-10.\n", encoding="utf-8")
        (t / "references" / "ceilings.txt").write_text(
            f"notes.md 120 2026-06-01 raised for {r289}\n", encoding="utf-8")
        (t / "scripts" / "tool.py").write_text(f"# fixed in {r1234}\nx = 1\n")
        (t / "README.md").write_text(f"see {r289} and {r42}\n", encoding="utf-8")
        (t / "CONTRIBUTING.md").write_text(f"open {r1001} first\n", encoding="utf-8")
        (t / "LICENSE").write_text(f"MIT {r2026}\n", encoding="utf-8")
        drafts = pathlib.Path(d, "replies.md")
        drafts.write_text("Shipped in v1.2.0, released 2026-06-10 (13/06/2026, "
                          "May 2026).\nThe merge review is on 2026-06-19.\n"
                          "Planned for 19/06/2026, i.e. June 2026.\n"
                          f"Also fixed {r289}.\n", encoding="utf-8")
        plain = scan([str(t)], ["acmeclient"], [], dates=False, today=today)
        dated = scan([str(t)], ["acmeclient"], [], dates=True, today=today)
        drafted = scan([str(drafts)], ["acmeclient"], [], dates=True, today=today)
        undated = scan([str(drafts)], ["acmeclient"], [], dates=False, today=today)
        forced = scan([str(t / "README.md")], ["acmeclient"], [], dates=True,
                      drafts=True, today=today)
        base = [("my-skill/references/ceilings.txt", r289),
                ("my-skill/scripts/tool.py", "__ref__")]
        classified_run = scan([str(t)], ["acmeclient"], base, today=today)
    refs = [h for h in plain["new"] if "[issue-ref:" in h]
    checks.update({
        "a reference line 'raised for <ref>' is a hit":
            any(f"ceilings.txt:1: [issue-ref:{r289}]" in h for h in refs),
        "a README line 'see <ref>' is not":
            not any("README.md" in h for h in plain["new"]),
        "CONTRIBUTING and LICENSE are not skill content":
            not any("CONTRIBUTING" in h or "LICENSE" in h for h in plain["new"]),
        "SKILL.md and scripts/ are read for the shape (2, 3 and 4 digits)":
            sorted(h.split("[issue-ref:")[1].split("]")[0] for h in refs)
            == sorted([r1234, r289, r333, r42]),
        "the shape runs without --dates and counts skill files":
            plain["skill_files"] == 3 and len(plain["new"]) == 4,
        "a date in skill content is a hit under --dates whatever its age":
            any("[date:iso] Verified 2026-06-10" in h for h in dated["new"]),
        "drafts: elapsed iso, dmy and mon-year dates pass":
            drafted["past_ok"] == 3,
        "drafts: future iso, dmy and mon-year dates are defects":
            sorted(h.split("[future-date:")[1].split("]")[0]
                   for h in drafted["new"] if "[future-date:" in h)
            == ["dmy", "iso", "mon-year"],
        "drafts: an issue reference in a reply is not a hit":
            not any("[issue-ref:" in h for h in drafted["new"]),
        "drafts: without --dates no date is read":
            not undated["new"] and undated["past_ok"] == 0,
        "--drafts applies the rule to any file": forced["drafts"] and not forced["new"],
        "a baseline classifies a reference by its text or by __ref__":
            classified_run["known"] == 2 and len(classified_run["new"]) == 2,
        "elapsed: today and the current month are not elapsed":
            not elapsed("iso", "2026-06-15", today)
            and not elapsed("mon-year", "June 2026", today)
            and elapsed("mon-year", "May 2026", today),
        "elapsed: an ambiguous day/month order takes the later reading":
            elapsed("dmy", "1/2/2026", today) and not elapsed("dmy", "6/7/2026", today),
    })
    for name, ok in checks.items():
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not all(checks.values()):
        print(out)
        print("\n".join(plain["new"] + dated["new"] + drafted["new"]))
    print("SELFTEST: " + ("all cases passed" if all(checks.values()) else "FAILED"))
    sys.exit(0 if all(checks.values()) else 1)


def load_terms(config_path):
    text = pathlib.Path(config_path).read_text(encoding="utf-8")
    m = re.search(r"```tripwire-terms\n(.*?)```", text, re.S)
    if not m:
        sys.exit("FATAL: no ```tripwire-terms``` block in " + str(config_path))
    block = m.group(1).splitlines()
    # Independent count of the same block by a fence-to-fence walk (no regex):
    # a parser that reads only part of the block fails here instead of
    # reporting a green scan over a fraction of the list.
    lines = text.splitlines()
    start = lines.index("```tripwire-terms") + 1
    count = lines[start:].index("```")
    terms = [l.strip() for l in block
             if l.strip() and not l.lstrip().startswith("#")]
    print(f"tripwire-terms block: {count} lines, {len(terms)} terms "
          f"({count - len(terms)} blank/comment lines skipped)")
    if count != len(block) or not terms:
        sys.exit("FATAL: tripwire-terms block unparsable or empty — "
                 "no heuristic fallback")
    return terms

def load_baseline(path):
    entries = []
    if path and pathlib.Path(path).exists():
        for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "|" not in line:
                continue
            parts = line.split("|", 2)
            entries.append((parts[0].strip().lower(), parts[1].strip().lower()))
    return entries

def repo_key(path, root):
    """Path keyed relative to the scanned root's parent: <root-name>/<path-in-root>.
    For a single-file root this is <parent-dir-name>/<file>."""
    root = root.resolve()  # a relative root such as '.' has no name otherwise
    if root.is_file():
        return pathlib.Path(root.parent.name, root.name).as_posix()
    return pathlib.Path(root.name, path.resolve().relative_to(root)).as_posix()

def classified(baseline, path, term, root=None):
    p, t = str(path).lower(), term.lower()
    keys = [p]
    if root is not None:
        keys.append(repo_key(path, root).lower())
    return any(bt == t and any(bp in k for k in keys) for bp, bt in baseline)

def main():
    if "--selftest" in sys.argv[1:]:
        selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", help="required except with --fingerprint")
    ap.add_argument("--baseline")
    ap.add_argument("--dates", action="store_true",
                    help="also scan for dated first-party claim shapes; on a "
                         "drafts file (replies.md, prefill.json, or --drafts) "
                         "only a date that has not elapsed is a hit")
    ap.add_argument("--drafts", action="store_true",
                    help="treat every scanned file as a drafts file")
    ap.add_argument("--fingerprint", "--examples-extract", action="store_true",
                    help="report anecdote sentences and per-section example "
                         "tokens; never fails")
    ap.add_argument("paths", nargs="+")
    a = ap.parse_args()
    if a.fingerprint:
        print("\n".join(fingerprint(a.paths)))
        sys.exit(0)
    if not a.config:
        ap.error("--config is required for the tripwire scan")
    terms = load_terms(a.config)
    baseline = load_baseline(a.baseline)
    s = scan(a.paths, terms, baseline, a.dates, a.drafts)
    print(f"scanned {s['scanned']} files against {len(terms)} terms; "
          f"{s['known']} baseline-classified; {len(s['new'])} NEW hits")
    print(f"reference shape run: {REF_SHAPE[0]} ({REF_SHAPE[1]}) over skill "
          f"content only — SKILL.md, references/, scripts/ — in "
          f"{s['skill_files']} of the scanned files")
    if a.dates:
        print(f"{s['exempt_pairs']} dates exempt as 'Last verified … · Re-test:' pairs")
        print("date shapes run: " + ", ".join(n for n, _ in DATE_SHAPES)
              + " — an enumerated set; a clean pass is a lower bound")
        if s["drafts"]:
            print(f"drafts files ({', '.join(s['drafts'])}): future-date shapes "
                  f"run: {', '.join(FUTURE_SHAPES)} relative to {s['today']}; "
                  f"{s['past_ok']} elapsed dates allowed")
    for h in s["new"]:
        print("NEW:", h)
    sys.exit(1 if s["new"] else 0)


def scan(paths, terms, baseline, dates=False, drafts=False, today=None):
    """The tripwire scan over every file under the paths: terms, the
    reference shape in skill content, and with `dates` the date shapes — or
    on a drafts file, the future-date rule. Returns the counts and the NEW
    hit lines; main() prints them."""
    today = today or datetime.date.today()
    shapes = [(n, re.compile(p, re.I)) for n, p in DATE_SHAPES] if dates else []
    future = [(n, rx) for n, rx in shapes if n in FUTURE_SHAPES]
    ref_rx = re.compile(REF_SHAPE[1])
    s = {"new": [], "known": 0, "scanned": 0, "exempt_pairs": 0,
         "skill_files": 0, "drafts": [], "past_ok": 0, "today": today}
    new_hits = s["new"]
    for root in paths:
        rootp = pathlib.Path(root)
        files = [rootp] if rootp.is_file() else sorted(
            f for f in rootp.rglob("*")
            if f.is_file() and ".git" not in f.parts)
        for f in files:
            try:
                head = f.read_bytes()[:8192]
            except OSError:
                continue
            s["scanned"] += 1
            if b"\x00" in head:
                if classified(baseline, f, "__binary__", rootp):
                    s["known"] += 1
                else:
                    new_hits.append(f"{f}: [__binary__] unscannable — needs "
                                    "one-time human classification in the baseline")
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            low = text.lower()
            for term in terms:
                tl = term.lower()
                if tl not in low:
                    continue
                if classified(baseline, f, term, rootp):
                    s["known"] += 1
                    continue
                for i, line in enumerate(text.splitlines(), 1):
                    if tl in line.lower():
                        new_hits.append(f"{f}:{i}: [{term}] {line.strip()[:120]}")
            is_draft = drafts or f.name.lower() in DRAFTS_NAMES
            if is_draft:
                s["drafts"].append(str(f))
            elif skill_content(f, rootp):
                s["skill_files"] += 1
                for i, line in enumerate(text.splitlines(), 1):
                    for mo in ref_rx.finditer(line):
                        if (classified(baseline, f, mo.group(0), rootp)
                                or classified(baseline, f, "__ref__", rootp)):
                            s["known"] += 1
                        else:
                            new_hits.append(f"{f}:{i}: [{REF_SHAPE[0]}:"
                                            f"{mo.group(0)}] {line.strip()[:120]}")
            for name, rx in (future if is_draft else shapes):
                for i, line in enumerate(text.splitlines(), 1):
                    pairs = [m.span(1) for m in VERIFIED_PAIR_RE.finditer(line)]
                    for mo in rx.finditer(line):
                        if is_draft:
                            if elapsed(name, mo.group(0), today):
                                s["past_ok"] += 1
                            else:
                                new_hits.append(f"{f}:{i}: [future-date:{name}] "
                                                f"{line.strip()[:120]}")
                            continue
                        if any(st <= mo.start() and mo.end() <= e for st, e in pairs):
                            s["exempt_pairs"] += 1
                            continue
                        if (classified(baseline, f, mo.group(0), rootp)
                                or classified(baseline, f, "__date__", rootp)):
                            s["known"] += 1
                        else:
                            new_hits.append(f"{f}:{i}: [date:{name}] "
                                            f"{line.strip()[:120]}")
    return s

if __name__ == "__main__":
    main()
