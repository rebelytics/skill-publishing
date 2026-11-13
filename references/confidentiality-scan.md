# Confidentiality scan — skill-publishing reference

Reference file for the `skill-publishing` skill (CC BY 4.0 — Eoghan Henn and contributors). Load before running the
confidentiality scan in cycle step 4, before classifying any hit, and when a
hit is found in a repo that has already been pushed. Sections below were
moved from the skill core or added here as the scan grew; headings and step
numbers match the core's cross-references, which resolve by name.

Load triggers: before running the confidentiality scan in cycle step 4; before classifying any scan hit; when a hit is found in a repo that has already been pushed (Retroactive scrub); reading the dated-claim scan's shapes and the exempt pair; the standalone-or-companion reference check before a commit

### Open-source skills are clean everywhere — no dual criteria

There is exactly one confidentiality boundary, and it runs between skill **types**
(a skill declared `internal` vs one declared `open-source`), not between the installed
copy and the published copy of the same skill. An **open-source skill must be 100%
client-clean in its installed/live version too**, not only in the repo. The published
copy is a byte copy of the installed copy; a skill is not "cleaned on the way out".

Consequences:

- The confidentiality scan (cycle step 4) is a **tripwire**, not a sanitiser. On an
  open-source skill it should never fire. If it does, a client identifier has leaked
  into the installed skill — fix it in the live skill and re-install, so installed and
  published stay identical, then re-sync.
- "Repo-only sanitisation" is a contradiction: repo == installed at publish time, so
  the two can only diverge if a **later local edit** introduces something the published
  copy never had. That later edit is the bug to fix at source, at the installed skill —
  never a patch applied to the repo alone. (This has happened: on one already-published
  repo, a post-publish local edit to the installed skill reintroduced a client name and
  named competitor tools that the published version had deliberately removed. Nothing
  errored, the sync would have carried it straight back into the public repo, and it was
  caught only in review. The fix was to re-clean the installed skill and re-sync, not to
  hand-edit the repo. This is the single best argument for running the confidentiality
  scan on every sync rather than only at first publication.)

### The tripwire list is a floor — classify hits by role, don't count them

A name scan against the tripwire list answers *whose confidentiality do I
owe*; the risk question is *is this someone else's name*. The list is a
roster of the maintainer's own clients and projects, so it can only ever be
a subset of the names that matter — it grows when the maintainer acquires a
client, which is unrelated to when a risky name enters the content. (A
reference file naming a competitor brand once passed the scan cleanly for
exactly this reason.) So treat the list as a **floor, not the definition**:
any company name is a hit unless it is a vendor whose tool the skill
documents.

The same string can be a legitimate subject or a leak depending on role. A
tool-companion skill must name the vendor it documents, dozens of times,
correctly — and when that vendor is also a client or co-owned project, a
string-match scan flags every legitimate occurrence. Judged by count the
skill looks unpublishable; judged by role it is fine. Therefore:

- **Classify each hit by role** — *subject* (the tool/vendor the skill
  documents), *example*, or *reference* — by reading it, never by counting
  matches, and record the classification alongside the scan result so the
  decision is auditable.
- **Annotate the list itself.** Where an entry is known-ambiguous (a short
  abbreviation that is also a common technical acronym, a name that is both
  vendor and client), mark the entry with its false-positive shape and its
  dual role in the configuration file, so a future run does not re-litigate
  it — or worse, dismiss the whole flag and let a real hit ride along.

The scan nominates candidates for a human judgement; any process that reads
its output as pass/fail has quietly substituted the narrow question ("is it
on my list") for the wide one ("is this a third party's name").

### The term list has one machine-readable source — the fenced block

`config.md` states the tripwire identifiers twice: as prose under its
sub-headings, for a human reader, and as the ```` ```tripwire-terms ````
fenced block, for a scanner. **The block is the only source a scan may
read.** `scripts/confidentiality_scan.py` parses it with one regex, counts
the same block again by a fence-to-fence walk, prints both numbers
(`tripwire-terms block: N lines, N terms`) and exits non-zero when they
disagree, when the block is missing, or when it yields no terms. It never
falls back to reading bullets, headings or prose.

The rule exists because a throwaway parser written mid-session walked the
file for bullets under a heading matching `tripwire|confidential`, found
three incidental bullets in an adjacent section, and reported a clean pass —
over an eighth of the list. Nothing looked wrong except the count. So the
count is the guard and the hits are the finding: **before reading any scan
result, confirm the printed term count against the block** (count the
lines between the opening and closing fence with `awk` or `sed -n`, and
compare). A scan whose input coverage is unstated is not evidence about the corpus;
when the instrument is code written in the same session, its coverage is
unverified by construction, and printing what it ingested is the only
remedy. Comment lines (`#`) inside the block are skipped and counted as
skipped in the same print, so the block can carry a one-line note naming
itself as the canonical source.

### Dated-claim scan — shapes, baseline keys and the open exemption question

The rule (core, "No dated first-party claims"): no dated first-party
verification claim in any public artefact, in any date format. The check is
the `--dates` mode of `scripts/confidentiality_scan.py`, run in the same
pass as the term scan in cycle step 4. What it does and how to read it:

- **Shapes are enumerated in the script's `DATE_SHAPES` table**, one place
  to extend: `iso` (`2026-06-10`), `dmy` (`10/06/2026`, also month-first),
  `mon-year` (`Jun 2026`, `June 2026`), `quarter` (`Q2 2026`), `as-of-year`
  ("as of 2026"). Each matches **anywhere in a line**, so the claim word is
  not part of the pattern and a sentence position ("on 2026-06-10", "checks
  run on 2026-06-10") cannot hide a date — the one grep that found every
  dated claim in a real sweep was the least specific one. A bare year is
  deliberately not a shape: it fires on version numbers and vendor facts.
- **The output names the shapes that ran** (`date shapes run: iso, dmy,
  …`). The pre-flight copies that line, not "the date scan passed". The set
  is an enumeration, so any count it produces is a **lower bound** — a sweep
  once reported eight dated sites as "corrected" when eleven existed, the
  three extras being the same ISO shape in a position the sweep's patterns
  had not covered. Never report a `--dates` count as exhaustive.
- **Classification reuses the baseline.** A legitimate date — a vendor-
  published changelog entry, a calendar-date example — is classified once,
  keyed on the matched text: `<repo>/<path>|2026-06-10|vendor changelog
  date`. A file whose every date is legitimate takes the pseudo-term
  `__date__` instead: `<repo>/<path>|__date__|vendor API changelog`. The
  script's own docstring and shape comments are the canonical `__date__`
  entry for this skill's repo — the examples that teach the shapes are, by
  construction, hits. A whole-file `__date__` entry granted because a file
  format required dates is retired, or narrowed to the dates still there,
  once the format drops them: an exemption that outlives its reason hides
  the next date written into that file.
- **A new date hit is handled like a term hit**, with the clean-everywhere
  rule: rephrase at the live skill to "at last verification" / "a later
  re-check found" plus a re-verification instruction, re-install, re-sync.
  Never rephrase repo-only.

**Decided by the maintainer: one paired form is exempt.** A measured fact
may carry "Last verified YYYY-MM-DD · Re-test: `<one command>`" — the date
and a backticked re-test command, together. The age is what lets a reader
judge a fact that drifts, and the command keeps it from being a bare claim.
Every other dated first-party phrasing is still a hit, including the date
without its command. The exemption lives in the script
(`VERIFIED_PAIR_RE`): a date inside a complete pair is counted and reported
as exempt, never as a hit, and the run prints how many it exempted.

**The issue-number shape runs in the same pass.** `#` followed by two to
four digits inside skill content — `SKILL.md`, `references/`, `scripts/` —
is a hit, classified by role like a term hit; `README.md` and
`CONTRIBUTING.md`, where issue links are normal, are not scanned for it.
Every file in a skill directory travels with the skill, so a reference
that resolves only against the repository — an issue, a PR, an observation
— is process in product, public yet meaningless outside the tracker. The
typical carrier is a ceilings reason or a docstring written with the
tracker open; the fix is at the live skill, naming the change in words. The
gate documentation that teaches the closing-keyword shape with example
numbers is classified once in the baseline, as the date shapes' own
examples are.

### A clean scan is not a clean skill — the class of identifier the scan cannot see

`scripts/confidentiality_scan.py` reads **every file** in the tree, scripts
and fixtures included, so the file type is not the gap. The gap is the
**class of identifier**. The script matches terms: names, domains, handles.
It cannot match a bare **number**, and a vertical or category noun cannot be
put on the tripwire list to compensate — a generic category word would fire
on nearly every file in the tree and drown the real hits, trading one failure
mode for a worse one.

State plainly what a pass licenses, because the alternative is treating it as
a blanket clearance:

- **It licenses a claim about the listed terms** — no client name, domain or
  handle in the tree, subject to the floor rule above.
- **It licenses nothing about values.** Example payloads, allocation figures,
  per-cluster or per-batch counts, dates tied to a client engagement, and
  sample data pasted from a live run all survive a green scan untouched.

This is the house rule that every instrument gets the same guard, in its
confidentiality form: an empty result from an instrument that cannot see the
object is not evidence of absence.

The mitigation is one prospective rule plus one human pass:

- **Prospective** — examples, usage strings, default arguments, fixtures and
  sample payloads are authored **synthetic from the start**, never scrubbed
  afterwards. An example is pasted from a working run precisely so that it
  works, which is exactly why live data survives there; a generic label and a
  round number in the same shape teach the format just as well. The authoring
  rule lives in `task-observer/references/skill-authoring.md`, under the
  confidentiality layers.
- **Human** — the pre-publication read includes a deliberate pass over
  **every example, usage string and fixture** in the tree, read for real
  values rather than for listed terms, and every sync of a published skill
  repeats it over each example added since the last published tree. An
  example is anonymised when nothing in it — vertical, market shape,
  figures — traces back to the session it came from: published examples
  are invented, never quoted. `REVIEW.md` records one line per added
  example (where it sits, "invented"). This is the one check the script
  cannot do for the maintainer, so it is a named step with a record.

The failure shape: a script's usage docstring carries a real client's
vertical and a real count and passes every scan the pipeline runs — the
scan did what it matches on, and what it matches on was the wrong class.

Do **not** extend `scripts/confidentiality_scan.py` to chase numbers. A
numeric pattern fires on every count, version, threshold and table in a skill
tree; the resulting false-positive rate destroys the tripwire's value, and the
finding here is precisely that this class is not scannable.

**Recognisability — the second human pass.** A skill can name no client,
pass every scan and still let anyone who knows the client recognise the
engagement: the leak is in how examples and justifications add up, not in
any one line. Over every section added since the last published tree, read
twice more:

- **Vertical clustering.** Where a rule's examples all come from one
  industry, and that industry matches a current or recent client, spread
  them across several unrelated verticals or move them to a neutral stock
  vertical. Each example alone is generic; five from the same trade, in
  that trade's own vocabulary, describe one account.
- **Engagement narratives.** A rule's justification states the failure
  shape in the present tense ("the failure shape: a check that reads one
  field treats its absence as a pass"), never the case it came
  from — no "observed once", "in the case that produced this gate", the
  client's complaint, or precise counts from one project. The rule stays;
  only its illustration and its provenance change. **Exempt: counts about
  the skill's own log and process** — observations, reviews, skills,
  releases ("roughly forty of ninety-one open entries were one finding
  restated"). They are the evidence a rule exists for and trace to no
  engagement; anything pointing at a client, a site or a project is
  rewritten. The fingerprint report flags such counts like any other —
  the human read classifies them under this exemption.

**The fingerprint report bounds that reading; it does not replace it.**
`scripts/confidentiality_scan.py --fingerprint <paths>` (alias
`--examples-extract`), run over the files changed since the last published
tree, prints every sentence that carries an anecdote marker ("observed",
"once", "in one project/account/session/engagement", "the client", "went
live", "for a week", "in the case that produced") **together with a number
in the same sentence**, and, per Markdown heading, the section's
example-like tokens — backticked literals, quoted strings, capitalised
multi-word names — so the reviewer reads each section's examples as one set.
It reports and never fails: unlike a bare numeric pattern, the marker-plus-
number pair is rare enough to read in full, and the verdict stays human.
**Its output ends by naming what it did not look at** — binary files, data
and fixture files, Markdown table rows, fenced blocks, tokens in scripts,
and any story told without its markers — because an extract that bounds a
reader's attention converts a wide check into a narrow one that feels
complete unless it states its own boundary. Read the listed blind spots by
hand; the report is a required pre-flight artefact beside the date shapes.
`--selftest` checks the mode against a small fixture tree.

**A batch is read as one set — the cross-tree pass, a batch step.** For
a batch of first publications, or any sync that touches more than one
repo, run `--fingerprint` once with every tree in the one call, never
tree by tree. Given several skill trees, the report adds a
`CROSS-TREE LITERALS` list: every number of two or more digits, and every
backticked or quoted literal, that appears in anecdote sentences of more
than one tree. Read each listed literal's sentences together, as one
shared-provenance candidate, and record the verdict beside the per-skill
reads. The failure shape: one engagement's figures sit in two skills
staged together, each reads as a lone illustration, and together they
describe one account.

### Open-source skills are standalone, or depend only on published open-source companions

Standing rule: a published skill must never reference a skill the reader might
not have. Either the content is self-contained, or the dependency is a
**published open-source companion, named as such** (two published companions may
reference each other by name, each declaring the other as published).
References to internal or unpublished skills — helper `*-extras` skills, internal
observation tooling, client dossiers — must be resolved before publishing: inline
the substantive rule, or rephrase to capability language ("whatever presentation
tooling the subagent runs"). This is part of the pre-commit scan: grep the synced
content for the names of installed-but-unpublished skills **and for the names of
the skill's pattern-group siblings, published or not** (next paragraph).

**Family vs pattern group — the reference rule differs, so use the words
precisely.** A **family** is skills for the same tool (a tool's MCP companion and
its strategy companion), or a core skill and its tool companions; family members
*may* reference each other by name, each declaring the other as published. A
**pattern group** is skills that only share a *shape* — one companion per tool,
one dossier per client. A user of one pattern-group member has no reason to have,
or to be pointed at, any of the others, so **pattern-group members must never name
each other**, and a reference from one member to another is a **defect even when
both are published** — not merely when the target is unpublished. Shared rules of
a pattern group belong in cross-cutting principles, never in a sibling paragraph.
A skill can belong to more than one family, and the scan runs against every family
and group it belongs to. Group skills by what a user of one would also need, not
by what they look alike: propagating an insight and cross-referencing are
different relationships, and conflating them either blocks publication or ships
references nobody can use.

**Known hit class — sibling-sync paragraphs.** Skill-maintenance machinery
that propagates shared rules across a family or pattern group legitimately
writes "sibling sync" paragraphs into skill files so shared cores don't
drift — and those paragraphs name the members, which on a published
skill or publication candidate means naming installed-but-unpublished
skills, or naming pattern-group siblings that must not be named at all.
This is the expected shape of the hit. The fix
is to rephrase the reference **at the live skill** in capability
language ("the sibling skills implementing this methodology for other
platforms") or as a generic pointer to the private family registry — never
to delete the sync rule itself, and never a repo-only rephrase (the
clean-everywhere rule applies).

### Retroactive scrub — removing an identifier from published history

A tip fix removes a leak from the current files only; the string stays in
every historical commit, reachable by SHA and by anyone reading history. When
a tripwire hit is found in a repo that has already been pushed:

1. **Fix at source first** — live skill, re-install — as ever.
2. **Decide the depth.** Default for any client identifier: rewrite history;
   for a small skill repo it costs minutes. A tip-only fix is acceptable only
   for strings that are not client-identifying.
3. **Mechanics (fresh sandbox clone, never the workspace review clone):**
   clone under the session's home directory; rewrite with
   `git filter-repo --replace-text` on an
   `OLD==>NEW` mapping (fallback where filter-repo is unavailable:
   `git filter-branch --tree-filter 'sed -i s/OLD/NEW/g <file>' -- --all`);
   verify with BOTH a case-insensitive grep over `git log --all -p` (must be
   zero) and `git diff --stat` of old tip vs new tip (must touch only the
   intended files); bundle the FULL history (`git bundle create … main`,
   then `git bundle verify`); copy to `bundles/` beside a README carrying
   the exact push commands.
4. **The maintainer force-pushes — never any automated step:** from a clone,
   `git fetch <bundle> main`, `git push --force-with-lease origin
   FETCH_HEAD:main`, then realign every local clone:
   `git fetch origin && git reset --hard origin/main`. Run these **from a
   terminal, never the review environment's Sync button** — the rewritten ref is
   diverged and Sync hangs on it (see the diverged-branch handover in cycle
   step 6); `REVIEW.md` must say so beside the commands rather than assume the
   maintainer knows the button is wrong.
5. **Sequencing:** the force-push must land BEFORE the next scheduled sync,
   or the run syncs onto the old history and produces a competing bundle.
6. **Residual exposure — state it plainly:** existing clones and forks keep
   the old history, and the host serves overwritten commits by SHA (and in
   cached views) until its support team purges them. For anything more
   sensitive than a low-severity identifier, file the purge request with the
   hosting provider and treat the string as disclosed when assessing client
   impact. The scrub narrows exposure going forward; it cannot un-publish
   the past — which is why the full-tree scan in cycle step 4 is the layer
   that actually matters.
