# Promotion and first publication — skill-publishing reference

Reference file for the `skill-publishing` skill (CC BY 4.0 — Eoghan Henn and contributors). Load after the sync cycle
before ranking candidates, when the maintainer picks a skill for
publication, when building or pushing a new repo, when a repo sits at
`awaiting-first-push`, and before running First inclusion. Sections below
were moved from the skill core or added here as the step grew; headings and
step numbers match the core's cross-references, which resolve by name.

Load triggers: after the sync cycle, before ranking candidates or presenting a shortlist; when the maintainer picks a skill for publication (the first-publication pass); when building or pushing a new repo; when a repo sits at awaiting-first-push (conditional sync, the squash before the first push); before running First inclusion; when a commit's attribution looks wrong (Git identity); when a published skill's attribution block, licence statement or LICENSE is migrated to the house shape

### Standard repo structure (new repos)

```
skill-name/
├── SKILL.md       ← the core: rules that fire every session, plus the pointer list
├── references/    ← at least one file loaded on demand, named from the core
├── README.md      ← aim for ~350 words; a target, not a gate
└── LICENSE
```

Existing repos keep their richer structure (`USER-GUIDE.md`, `CONTRIBUTING.md`,
`scripts/`, `assets/`) — this standard applies to **new** repos only.

The skill in a repo is always a **directory**, whatever its size: `SKILL.md` plus
whatever `references/`, `scripts/` and `assets/` the installed copy carries, at
the same paths. There is no single-file variant of the layout and nothing in the
sync branches on file count.

**Progressive disclosure is a publication gate, not a size threshold** — the
maintainer's decision after a ~1,200-line single file went public having
passed every readiness check, its restructure noted as a "standing
follow-up" for three runs without gating anything. **No flat skill is
published.** "Flat" is mechanical, so the check is a script line rather than
a judgement: a skill directory with no `references/` directory, or a
`references/` directory that `SKILL.md` never points at (no section map or
pointer list naming a file in it), or a `SKILL.md` above the line budget the
review sets with nothing loaded on demand. The budget itself is the review's
call (the authoring reference in the task-observer skill states it), so the
retrofit trigger for a large existing core belongs to the review. The
gate is checked twice: at Phase 1 readiness (below) and at the first-push
pre-flight (core, item 12), where a flat repo fails the way a missing
`LICENSE` does. The restructure is prep work done **at the live skill**
through the ordinary review-and-install path — never in the repo, because
the repo is a byte copy of the installed skill.

**README rule — extractive, not generative.** Every line traceable to the skill's own
frontmatter or body. Fixed sections only: title, one-sentence description (lifted from
the skill's description field), when it triggers, install boilerplate (identical across
repos), licence, author link. Banned: emoji headers, "Features", "Why this skill?",
roadmaps, badges beyond licence, contributing essays. If a section can't be sourced
from the skill, it doesn't get written.

The rule does not make the README non-AI-generated — it prevents a *second layer*
of ungrounded claims on top of content that has been through real use and review.
User guides are written manually, only for skills popular enough to earn one.

### Licence

One licence text across every repo, from one canonical file: the file at
the path `config.md` names under `license_canonical:`. CC BY 4.0 is the
default for prose and methodology skills; the choice is the maintainer's,
the requirement is that every repo carries the same text under the same
file name, `LICENSE`, byte-identical to the canonical file. Include that
`LICENSE` beside `SKILL.md` in the installed skill — never repo-only — and
a licence statement in the skill preamble.

**The canonical text is the licence's full, unmodified legal code**, as
the licensor publishes it — for CC BY 4.0 including the "Using Creative
Commons Public Licenses" preamble and the closing notice, and with **no
added copyright line**: the credit ("Copyright (c) <year> <author>") goes
in the README's licence section, beside one sentence and the summary
link. **The human-readable summary never goes in `LICENSE`** either. The
failure shape: a hosting platform's licence detector matches `LICENSE`
against its vendored text, and a summary, a notice, a trimmed legal code
or one with an added line can be reported as no licence at all — no
badge, no licence filter, `NOASSERTION` in the API — even where a local
copy of the matcher reports an exact match; the unmodified text is the
form observed to be detected on the platform itself. After a first push,
read what the platform detected —
`gh api repos/<owner>/<repo> --jq .license.spdx_id` — and record it in
`process-record.md`: the detection is the pass criterion, not the file's
presence.

**Byte-identity is asserted twice** — in the first-publication pass (Phase
2, below) and at every sync (core, cycle step 3): `cmp` of the repo's
`LICENSE` against the canonical file is silent, or the repo is listed
under Housekeeping with the differing file. The fix follows the
clean-everywhere rule: at the live skill where the installed skill carries
the file, in the repo commit while it is still repo-only — never by
editing the canonical file to match a repo.

### Attribution migration — every line the shape touches

Moving a published skill onto the attribution shape (the Author
Attribution Template in the task-observer skill's authoring reference) is
a migration, and a checklist that names only some of the lines the shape
touches leaves the rest to be re-decided once per skill. Every line, in
one staged update at the live skill:

1. Frontmatter: `license:` (the SPDX id), `metadata.author` ("[Author] and
   contributors"), `metadata.source` (`https://github.com/<owner>/<repo>`,
   with the scheme).
2. The body opens with what the skill does — no credits and no feedback
   offer before it.
3. The `## Feedback on this skill` section just before the footer, in the
   template's form for a published skill.
4. The one-line footer: `[Skill title]: [Author] and contributors |
   [licence name]`.
5. Every reference file's and script's header credit line, short-form —
   "[Author] and contributors": the line a frontmatter-only migration
   leaves carrying the old long-form credit.
6. `LICENSE`: the canonical file, byte-identical (Licence, above).
7. README: the long-form credit ("Created and maintained by [Author],
   improved by its community of users") and the licence section with the
   summary link.

**At a skill's ceilings the line-neutral forms are the default:** the credit
appended to the reference file's existing header sentence, a docstring line in
scripts, the feedback section paid for by the preamble item 2 removes — never a
ceiling raise for attribution. The repository string is byte-identical at every
site the list names. Before the update is staged, grep the skill directory for
the old shape's phrases — the long-form credit in headers, the source without
its scheme — and grep the synced tree again at the pre-flight.

### Git identity

Pinned **per repo** at clone time, to the maintainer identity in the configuration
file:

```bash
git config user.name  "<maintainer name from config>"
git config user.email "<maintainer commit email from config>"
git config commit.gpgsign false
git config tag.gpgsign false
```

This is not optional. A commit whose author email does not match the address
verified on the maintainer's GitHub account is attributed to a *different*
account — on one repo, five commits authored under a personal address landed
under a separate account and split the contribution graph. Per-repo config makes
recurrence impossible regardless of global config.

Signing is pinned off for the same reason: a build environment's global
config can sign every commit with a session key no account has registered,
and the platform then shows each pushed commit as unverified. The sandbox
builds unsigned; the maintainer signs at push, where the push gate compares
the key with the configured one (`--pre-bundle` refuses any signed commit).

If mis-attributed commits are found, the fix is to add that address to the
maintainer's GitHub account as a **verified secondary email** — GitHub then
re-attributes the existing commits retroactively, with no hash changes and no
history rewrite. Do **not** rewrite history to fix attribution on any repo that
has forks, stars or open PRs: a rewrite breaks every fork and every open PR for
a cosmetic gain. The configuration file records any known secondary address that
still needs adding.

### First inclusion — a published repo with no review clone

Run once, for any published repo that has no clone under
`skill-publishing/repos/`: one released through a separate workflow, or one whose
exclusion has just been lifted. A cycle written for steady state has no step for
the moment something enters it, and every "compare against last time" rule needs
last time defined explicitly, or the run invents one.

1. **Clone into `repos/` and pin the identity** to the maintainer identity in the
   configuration file, exactly as for any other review clone.
2. **Define the drift baseline explicitly.** With no local commit, "has
   `origin/main` moved?" has no answer. The baseline is the newest `origin/main`
   commit whose **skill files** (`SKILL.md`, `references/`, `scripts/`) are an
   ancestor of the installed copy. Commits after it that touch only repo-only
   files — manifest, CI workflow, README, licence — are **not drift**; the sync
   proceeds from that baseline. Record the baseline SHA in `registry.md`.
3. **Enumerate every binary in the tree** and list them in `REVIEW.md` for
   one-time classification by the maintainer. Binaries that predate the pipeline
   (logos, screenshots) are scan blind spots the pipeline never introduced, and
   "the scan must pass before anything is staged" would otherwise block every
   sync of the repo until someone classifies them. **For this first run only**,
   the confidentiality scan counts as green on a clean text result with the
   binaries listed and carried into `REVIEW.md`; from the next run they are
   classified in `scan-baseline.md` like any other hit.
4. **Require a plain exclusion status before starting.** `registry.md` and the
   configuration file must agree, and the status must be a plain value — not a
   conditional the run has to evaluate for itself ("excluded until installed ==
   merged main"). Lift the exclusion explicitly, then include the repo.

After the first inclusion the repo is an ordinary member of the roster: drift is
measured against the local commit as usual.

## Promotion step

Two phases on the configured cadence (core, Configuration): Phase 1 runs
**after** the sync cycle in the shortlist day's run and ends in that run's
report; Phase 2 is its own task on the release day, independent of the
review session.

### Phase 1 — autonomous (part of the scheduled run)

1. **Refresh the candidate list.** Scan the installed skills mount for
   open-source-typed skills not yet in `registry.md` (the list grows between
   runs); add them to the appropriate tier. Never auto-promote anything out of
   `internal` — classification stays a deliberate act.
2. **Rank the unpublished candidates** on:
   - **Usage signal:** staged-update frequency and recency
     (`skill-updates/*/<skill>` dates), observation-log mentions (frontmatter
     `skill:` fields, recent window). Frequent + recent = actively used.
   - **Maturity:** structural completeness, review history. **Structure
     gate:** a candidate whose directory is `SKILL.md` alone (or `SKILL.md`
     plus `LICENSE`), or whose `references/` the core never points at, is
     listed as **"needs progressive-disclosure restructure"** and can never
     be shortlisted as "near-zero prep" — the restructure *is* the prep,
     done at the live skill through the ordinary review-and-install path
     (Standard repo structure, above).
   - **Audience potential:** registry tier, vendor-amplification notes.
   - **Distribution boost:** an existing post or article on the maintainer's own
     site (named in the configuration file) covering the candidate's topic bumps
     the skill up the list. No post is never a blocker.
3. **Re-verify the shortlist's readiness claims against the current
   artefacts.** A readiness verdict recorded in `registry.md` decays into an
   unverified claim while sitting in the one place designed to be acted on
   without re-derivation — a top-tier "ready now, content already isolated"
   entry has been found flatly wrong on inspection. So the promotion run
   re-runs the confidentiality scan on its own shortlist before presenting
   it: no candidate reaches the maintainer on the strength of a stored
   verdict alone. Where a rating rests on a specific remedy having been
   applied ("isolated", "split", "scans clean"), record in `registry.md`
   what was checked and when, so a later reader can see the claim's age.
   Optimistic errors need this most: a ready thing marked not-ready gets
   challenged the moment someone wants to publish it, while a not-ready
   thing marked ready surfaces only when it causes the harm the rating was
   meant to prevent.
4. **End the run with a shortlist** — top ~5, one-line case each, flagged
   prep work per candidate — and stop. Zero viable candidates is a valid
   outcome; say so and skip Phase 2. The session that receives the
   maintainer's pick records it in `registry.md`, where Phase 2 reads it.

### Phase 2 — interactive (when the maintainer joins the run's conversation)

The maintainer picks up to the **promotion cap** from the configuration file
(default one); the publication task reads the pick from `registry.md` and, with
no pick recorded, stops and reports. A pick line may record an exception to the
cap in so many words; the task builds what the line says. Per pick, run the
first-publication pass:

- Confidentiality layers 2–5 incl. the cross-product re-identifiability
  sweep; client-identifier scan against the configuration file's tripwire
  list must be clean (tripwire rules apply).
- **No dated first-party claims** in any date format — the scan's `--dates`
  mode, with the shapes that ran recorded. A dated `## History` or
  changelog section in a candidate is rewritten as an undated current-method
  section plus a collapsed `<details>` block holding the old patterns, so a
  reader sees how it is done now and can still find what was retired.
  **No references to non-companion skills** (inline, declare a
  published companion, or rephrase to capability language).
- Progressive disclosure, mandatory: the skill directory passes the
  structure gate (a `references/` directory with at least one on-demand
  file, named from the core's pointer list). A flat candidate goes back to
  the review for restructure and re-install before this pass continues.
- Attribution block, licence statement, `LICENSE` file — **added at the
  live skill through review-and-install, never only in the repo**, the way
  the structure gate's restructure is: a repo-only `LICENSE` breaks
  installed == repo and is flagged under Housekeeping at every sync (core,
  cycle step 3), and the file is byte-identical to the canonical file
  (`cmp`; Licence, above). `metadata.source` is
  `https://github.com/<owner>/<repo>` — with the scheme — the one form,
  byte-identical wherever the string appears. Extractive README
  (~350 words, a target; no release notes); frontmatter description
  ≤1024 chars (warn >900); version `1.0.0`.
- Discovery metadata where the discovering system reads it, never in the
  `SKILL.md` frontmatter (no keywords or tags key — it fails the spec
  validator and nothing reads it). No plugin manifest unless the maintainer
  asks for one for that repo; where one ships, `plugin.json` carries a
  one-sentence discovery `description` and `keywords`, mirrored with a
  `category` in the marketplace entry (task-observer's
  `references/skill-authoring.md`, "The description has more than one
  reader"; its validator's `--repo-only` mode checks the mirror). Repo
  topics: the ones the skill directories index by.
- Build the repo in the sandbox: `git init`, pinned identity, initial commit
  on `main`; ship as a bundle; materialise the review clone at
  `skill-publishing/repos/<name>` from the bundle.
- The per-pick instructions go to the task's own file,
  `skill-publishing/REVIEW-first-publication-<date>.md`, with one pointer line
  to it in `REVIEW.md` that every regeneration copies verbatim (core, cycle step
  7) — the review session regenerates `REVIEW.md` in the same hour and drops a
  section it did not write. Built from the repo conventions in the configuration
  file: create the empty public GitHub repo (`gh repo create <account>/<name>
  --public`, or via the browser), add the remote, push. **First-push bundles
  include HEAD** (`git bundle create <repo>-<date>.bundle HEAD main`): a
  heads-only bundle gives `git clone` no HEAD to follow, so it fetches the
  objects, checks nothing out and leaves an unborn `master`, and the `&&` chain
  after it half-ran across retries. **The maintainer's setup line never depends
  on HEAD:** `git init -b main <repo> && cd <repo> && git fetch <bundle> main &&
  git reset --hard FETCH_HEAD && git remote add origin <url>`, then the
  gate-chained push. Update `registry.md` to `published` and stage the install
  bundle if publication changed the skill (restructure/cleanups must flow back
  to the installed copy), appending its `skill-updates/PENDING.md` entry in the
  same step (`SKILL.md`, Workspace state).

Nothing in Phase 2 is pushed by the session — the maintainer pushes, as always.

**When the maintainer does not push in the same conversation** — a batch parked
for want of review time is the normal case, not an exception — set the repo's
registry status to **`awaiting-first-push`** rather than `published`. The next run
then skips fetch and drift for it (its `origin` does not exist yet), syncs
nothing if the installed skill still matches the repo tree — or a follow-up
commit on the unpushed `main` if it does not (cycle step 3) — and reproduces
the create-and-push block in `REVIEW.md`, rewritten to the current setup line
above rather than copied verbatim: a block written before that line changed
keeps a `git clone <bundle>` form that checks nothing out. The status is what carries
the handover across runs; a one-off handoff note is not. A parked batch is
also a published skill in every respect the review cares about: from the moment
it is parked, the next skill review bumps the version at source for any of
those skills it touches, exactly as for a `published` one — otherwise the first
push ships a changed skill under the version the batch was built at.

### Awaiting-first-push repos — conditional sync while parked

**Repos at `awaiting-first-push` sync conditionally.** Their tree equalled
the installed skill on the day it was built, but a parked batch can outlive
a skill review that changes the installed copy, so check rather than
assume: `diff -rq` the installed skill directory against the review
clone's tree. Identical → sync nothing. Different → build a follow-up
commit on the unpushed `main` in a sandbox clone created from the parked
bundle, ship a **replacement full-history bundle** (`git bundle create …
HEAD main` — there is no origin to exclude), fast-forward the review clone
where the grant allows. The version-bump hold applies here too. The
multi-commit form is the **parked** shape only: **before the first push,
`main` is squashed to a single release commit at the current state** and
`REVIEW.md` hands over one commit, not a 1.0.0 plus its delta — procedure
in `references/promotion-and-first-publication.md` (First push — one
squashed release commit).

### First push — one squashed release commit

The follow-up commit on a parked repo's unpushed `main` (cycle step 3) is
the **working** shape: it is how a parked repo tracks its installed skill
between runs. It is not the **publication** shape. History is a review
artefact only once someone has seen the earlier state; on an empty remote
there is no earlier state, so every intermediate commit is review cost with
no audit value — handed over literally, three parked repos each presented
the maintainer with a 1.0.0 state plus a 1.0.0→1.2.0 diff to review, two
reviews for a state nobody outside had seen. The call was general: on a
first push, review only the current state.

**Before a repo's first push, squash `main` to a single release commit at
the current state.** Keep the multi-commit form only while the repo is
parked. In a sandbox clone created from the parked bundle, with the identity
pinned:

```bash
old=$(git rev-parse main)
git checkout --orphan squash && git add -A
git commit -m "<message that describes the skill, not the delta>"
[ "$(git rev-parse HEAD^{tree})" = "$(git rev-parse $old^{tree})" ] || echo "TREE DIFFERS — stop"
git branch -M squash main
git bundle create <repo>-<date>.bundle HEAD main && git bundle verify <repo>-<date>.bundle
```

- **The message describes the skill** — what it is and does for a user —
  not the sequence of edits that produced it; the delta was never public.
- **The tree is verified identical** to the pre-squash tip (the
  `HEAD^{tree}` comparison above) before the bundle is built; a squash that
  changes the tree is not a squash.
- **Ship a replacement full-history bundle** (one commit) into `bundles/`
  and reset the review clone to it where the grant allows.
- **Delete the review clone's bundle-era `refs/remotes/origin/main` at
  reset time** (`git update-ref -d refs/remotes/origin/main`): it was
  created when the clone was materialised from a bundle, points at a commit
  that does not exist upstream, and leaves the editor showing an
  ahead/behind count instead of offering to publish the branch.
- The pre-flight (core, item 9) checks that every repo at
  `awaiting-first-push` carries exactly one commit before `REVIEW.md`
  hands it over.
