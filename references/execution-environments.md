# Execution environments — skill-publishing reference

Reference file for the `skill-publishing` skill (CC BY 4.0 — Eoghan Henn and contributors). Load at the start of every
run in the review session; before the first git
or delete command when the session is a cloud session bridged to the
maintainer machine; when the pre-flight re-run of the freshness gate (item
8) fails for a skill that received a commit this run; and before syncing
any skill from a staged copy that is not yet installed. The sections
after the cadence were moved verbatim from the skill core's Execution
model, and cross-references resolve by name through the core's Section
map.

Load triggers: the start of every run in the review session (the cadence: what this run does); before the first git or delete command in a cloud session bridged to the maintainer machine; when the pre-flight re-run of the freshness gate fails for a skill that received a commit this run; before syncing any skill from a staged copy that is not yet installed; after a bridge drop or restart, before the next mount-side git command

### The cycle inside the review session — cadence

The publishing cycle is the second part of the skill review session: one
scheduled session on the days the configuration's **Cadence** names, never
a second session chained to the review by a start-time offset. It syncs
from the review's staged copies under the unattended exception (the
freshness gate in full, below) and runs autonomously up to the commits
waiting in the review clones; the maintainer then installs, reviews and
pushes. With no cadence in the configuration, ask before the first run.

- **Every run syncs; the release day releases.** Every run commits
  safe-to-main changes on `main` as untagged version bumps and needs-test
  changes on the release branch. The release day's run adds the ceremony:
  the release merge with its evidence table, the tag, the GitHub release,
  the security-scan pair and the release notes ("Release branch under test").
- **A carried unpushed commit is a base, not a block.** New syncs to that
  repo commit on top of it, the bundle range stays `origin/main..main`,
  nothing carried is rebuilt, and `REVIEW.md` lists per repo every carried
  commit plus the new ones.
- **The triage table is applied, not presented.** Include-now rows become
  commits on `main` — through a re-stage of the skill, so installed and
  published stay identical — with their credit trailers and diff-coverage
  verdicts; needs-testing rows become commits on the release branch with
  their test-plan rows; declines get drafted replies. Only decision rows
  wait, listed at the end of the report. Nothing is public before the
  maintainer's push, so a wrong call costs a rejected commit, which is
  cheaper than a confirmation round that delays the review.
- **Replies are drafted every run and all sent after that run's pushes.**
  When the maintainer says the push is done, the same session verifies it
  on origin (`git ls-remote origin` against the bundled tips) and only then
  sends, by the route the configuration names (Responding, step 3). A push
  made after the session ended is picked up by the next run's first step:
  verify on origin, then send the carried drafts.
- **New-skill publication is its own task on the release day.** The Phase 1
  shortlist goes into the shortlist day's report; the session records the
  maintainer's pick in `registry.md`, where the publication task reads it,
  and that task stops and reports when no pick is recorded (Promotion step).

### Bridged cloud session — the third execution branch

A cloud session bridged to the maintainer's machine runs two shells: the cloud
container sees the installed skills mount; the bridge VM sees the workspace,
the staged copies and the review clones, and runs git. None of the two-branch
assumptions hold as written:

- **Grant = the connected folder root.** The device permission tool grants a
  whole connected folder, never `skill-publishing/repos` alone. Request it on
  the root and **state in the run's output that deletion is enabled
  everywhere under that root for the session**.
- **Gate = checksums across the two shells.** `diff -rq installed staged` is
  impossible in one shell; run the same listing on both sides and compare
  the outputs verbatim. In the container shell, which sees the installed
  mount:
  ```bash
  fm=$'1,/^---$/{/^(name|description|version):[[:space:]]*".*"[[:space:]]*$/{s/:[[:space:]]*"/: /;s/"[[:space:]]*$//;s/\\\\"/"/g;s/\\\\\\\\/\\\\/g;};/^(name|description|version):[[:space:]]*\'.*\'[[:space:]]*$/{s/:[[:space:]]*\'/: /;s/\'[[:space:]]*$//;s/\'\'/\'/g;};}'
  cd <skills-mount>/<skill> && find . -type f ! -path ./SKILL.md | sort | xargs md5sum && sed -E "$fm" SKILL.md | md5sum
  ```
  In the bridge shell, which sees the workspace:
  ```bash
  fm=$'1,/^---$/{/^(name|description|version):[[:space:]]*".*"[[:space:]]*$/{s/:[[:space:]]*"/: /;s/"[[:space:]]*$//;s/\\\\"/"/g;s/\\\\\\\\/\\\\/g;};/^(name|description|version):[[:space:]]*\'.*\'[[:space:]]*$/{s/:[[:space:]]*\'/: /;s/\'[[:space:]]*$//;s/\'\'/\'/g;};}'
  cd skill-updates/<date>/<skill> && find . -type f ! -path ./SKILL.md | sort | xargs md5sum && sed -E "$fm" SKILL.md | md5sum
  ```
  The last line of each listing is `SKILL.md` with its frontmatter `name:`,
  `description:` and `version:` quoting normalised (the freshness gate in
  full, below). The gate passes only if the two listings are identical, line
  for line. Where they differ on the `SKILL.md` line alone, stage the
  workspace copy of that one file into the container and run the parsed
  compare below on the pair before calling it a difference — a description
  the installer re-folded onto one line differs in text and not in value.
  **The per-skill container command above is the only container-side
  read of the installed root** — run as written, once per skill
  directory. Never improvise an aggregate listing of the synced root (a
  loop of `ls` and `grep` over every skill, an `ls | wc -l`): one was
  refused twice by the harness classifier as destructive where the
  prescribed command had passed on earlier runs, and a refusal is not
  pursued through another tool. If the prescribed command itself is
  refused, the gate's outcome is **Unverifiable** (the freshness gate in
  full, below).
  (The blocks carry no `#` comments on purpose: a pasted block runs in a
  shell the author has not tested, and interactive zsh passes `#` words to
  the command — `references/release-branches-and-contributions.md`, "Push
  gate", command-block rules.)
- **Comment pre-fill goes to the maintainer's own browser.** The prepared
  hand-off for issue and PR replies is a pre-fill in the browser the
  configuration names — one tab per item, batched by the action the
  maintainer will take, never submitted
  (`references/release-branches-and-contributions.md`, Responding, step 3).
  A harness classifier once denied that fill in a bridged session as an
  external-system write; that is one instance on one surface, not a rule.
  A denial on the surface in use is answered by the drafts-file fallback,
  never by another fill method.
- **Sandbox clone = the bridge VM's `$HOME`** — invisible to the maintainer
  and to the container, survives a bridge drop, reaches GitHub. The bundle
  copied into `bundles/` is the durable artefact, as in hard rule 1.
- **After any bridge drop, re-read the review clone's tip** (`git log -1
  --format=%H`) before assuming the last mount-side git command ran: a
  fast-forward in flight when the bridge dropped has silently not happened.
- **After any "Workspace still starting" or bridge-reconnect message, treat
  the delete grant as gone.** A restart of the bridge workspace drops the
  grant without saying so, and the next mount-side git command — even
  `git status` — strands an `index.lock` in the review clone the maintainer
  is about to push from (inspection commands run as `git
  --no-optional-locks`, Delete-grant probe). Before that command, re-request
  the grant, or probe it: create a scratch file under the connected root and
  unlink it; a refused unlink means re-request. The probe costs one call; a
  stranded lock blocks the maintainer's next command.

Pre-flight item 10 and reporting item 2 accept "bridged" as the branch taken.

### Critical: publish only installed skills — the freshness gate in full

The pipeline syncs from the **installed** skill (the read-only skills mount), which
is whatever version the maintainer last installed. The observation-driven skill
review runs as the first part of the same session (The cycle inside the review
session, above) and stages new versions of any skill with observations since the
last review to `skill-updates/<date>/<skill>/`. Those new versions only
reach the installed mount once the maintainer **installs** them. Outside the
exceptions below, a sync from the installed side while an update is pending
would publish last cycle's version — silently. (This is the same
"silently a week or two months behind" failure that once left a published skill
two months out of date.)

**Every skill is a directory.** There is no single-file skill format and no
size threshold that changes an artefact's shape: a skill is `SKILL.md` plus
whatever `references/`, `scripts/` and `assets/` it carries, delivered and
installed as one directory whether it holds one file or twenty. Nothing in the
gate, the sync, the bundle handling or the published-repo layout branches on how
many files a skill has — a rule that switches on the size of the artefact creates
two formats for one thing and a boundary every consumer has to re-derive.

**Gate, run before syncing any repo.** For each published, non-excluded skill, compare
the **installed** skill directory (skills mount) against the **newest staged**
directory found under `skill-updates/*/<skill>/` (max date wins). The comparison is a
full recursive diff of the directory, not a check of `SKILL.md` alone (in a
bridged session, a checksum listing on each side — see "Bridged cloud session"):

- **Installed == newest staged** (modulo the frontmatter normalisation below), **or
  no staged version exists** → the installed skill is current; proceed to sync
  normally.
- **Installed ≠ newest staged** (any file added, removed or changed) → an uninstalled
  update exists. **Do NOT sync that skill.** List it in `REVIEW.md` and the run summary
  under **"Blocked — install pending update first"**, naming the staged path, and move
  on to the next repo.
- **Unverifiable — the installed side could not be read** (the read was refused
  or failed) → neither outcome above. **Hold every skill** under its own
  `REVIEW.md` heading, **"Unverifiable — installed side could not be read"**,
  naming the refused command verbatim and the refusal reason as given (a
  classifier's stated category), and hand over a ready-to-run build list for
  the interactive session: per skill, the staged path, the gate command and the
  sync to build once it passes. Reading it as green would publish a possibly
  stale copy, and filing it under "Blocked" would report ready syncs as
  pending installs, so the run does neither; it never retries the refused read
  through another tool.

**Installer quoting is normalised, never judged by eye.** The installer
rewrites the frontmatter it writes back — it quotes `name:` on some installs
and not others, re-quotes `description:` and an unquoted `version:`, and
turns a folded `description: >` block into one quoted line — so a literal
comparison fails on a benign, recurring artefact and each run would re-decide
by hand what the gate exists to decide. The primary compare is by parsed
value, where both files are in one shell: `python3
task-observer/scripts/validate-skill-bundle.py --compare-frontmatter
<installed>/SKILL.md <staged>/SKILL.md && diff -rq -x SKILL.md <installed>
<staged>` (exit 0 and silent = installed == staged; a real change is named
with its key or first differing body line). Where no Python runs, compare
`SKILL.md` through one text normaliser — frontmatter only, `name:`,
`description:` and `version:` only, surrounding double quotes stripped with
`\"` and `\\` resolved, surrounding single quotes stripped with `''`
resolved — and every other file literally. Both commands are shared content:
their owner is `task-observer/references/weekly-review.md` § "Compare with
the installer's frontmatter quoting normalised", both skills quote the
identical `fm=` line, and the owner changes first. The text form needs bash
(the `$'…'` string):

```bash
fm=$'1,/^---$/{/^(name|description|version):[[:space:]]*".*"[[:space:]]*$/{s/:[[:space:]]*"/: /;s/"[[:space:]]*$//;s/\\\\"/"/g;s/\\\\\\\\/\\\\/g;};/^(name|description|version):[[:space:]]*\'.*\'[[:space:]]*$/{s/:[[:space:]]*\'/: /;s/\'[[:space:]]*$//;s/\'\'/\'/g;};}'
diff <(sed -E "$fm" <installed>/SKILL.md) <(sed -E "$fm" <staged>/SKILL.md) && diff -rq -x SKILL.md <installed> <staged>
```

Exit 0 is installed == staged: a diff consisting only of that quoting is
this state, mechanically, never a reason to re-stage; a real change on
either line still surfaces. A multi-line `description:` the installer
re-wrapped onto one line is not normalised by the text form — it surfaces
there and is cleared by the parsed compare, never by eye; where only the text
form can run, re-stage the description as one quoted line (the form the
installer writes), with its `PENDING.md` entry (`SKILL.md`, Workspace state),
so the next comparison is clean by construction. If the installer ever stops
quoting, the normaliser becomes a no-op rather than a rule to remove.

The gate self-clears: once the maintainer installs the update, installed equals
staged and the next run proceeds. It converts a silent stale-publish into an
explicit, actionable skip. It never blocks the whole run — clean skills still sync;
only skills with a pending update are held.

**The gate interlocks with the version-bump hold, which is why it is
load-bearing rather than a freshness nicety.** A re-stage that keeps its
version number (a cross-reference repair, no semantic change) turns a stale
publish into a **wedged sync**: publish the pre-fix copy at version N and the
fixed copy, also version N, can never be synced — the hold blocks it until
someone bumps by hand at source, a week later, in a run with no memory of
the cause.

**The gate is point-in-time, so it is re-run at the pre-flight** for every
skill that received a commit this run (item 8): a green result at step 0 is
an assertion about that moment, and a parallel session can re-stage a skill
while the run is building its sync. **A gate failure after a commit is a
revert instruction, not a note:** reset the review clone to its prior tip,
delete the bundle, list the skill under "Blocked — install pending update
first", and record in `REVIEW.md` that a commit was built and discarded and
why. Shipping-and-flagging is the wrong move, for the version-number reason
above. Optional: record the staging directory's newest mtime at gate time
and compare it at the pre-flight, so the re-check is a comparison.

**Two exceptions — syncing from a staged copy not yet installed.** Either
lists the skill under **"Install before push"**, not under "Blocked", with
the install as step 1 of `REVIEW.md`'s push order. *Attended:* **all four**
hold — the maintainer is present in the session; the exact staged copy has
been handed over for install; `REVIEW.md`'s push order says **install
first**; and the run records that installed == repo tree must be
re-verified before the push — and does so once the install lands.
*Unattended, same cycle:* the copy is the newest staging of the review that
opened this session (its anchor, its digest equal to that review's `.skill`
bundle), and the next run's first step verifies installed == the pushed
tree and, on a mismatch, re-presents the bundle for install. Outside these
two shapes — a staging from another session, an older anchor — the absolute
wording stands.
