#!/usr/bin/env python3
"""pre-push-check.py — the executable gate between a commit and its push.
Part of the skill-publishing skill (CC BY 4.0 — Eoghan Henn and contributors).

Skill CONTENT is gated exhaustively (bundle validator, confidentiality scan);
the METADATA wrapped around a release — commit message, changed-file set,
signature, release body, repo-root prose — was gated by eye, and every defect
one release weekend produced was in that metadata and was found by a human
reading output rather than by a gate. This script is the gate. It REFUSES
(exit 1) rather than warns, prints every check as PASS / FAIL / SKIP / WARN
with its evidence, and is run before EVERY push. If a metadata defect ever
reaches a release after this check exists, the check is wrong and needs a
case adding — that is the signal to act on, not "the rule was not followed".

Checks, on the tip commit of --repo (default `.`) — except checks 1, 3 and
4, whose unit is the unpushed range: every commit in `origin/<target>..<commit>`
— or, when `origin/<target>` does not exist (the first push of a new branch,
a repo awaiting its first push, a clone made from a bundle), every commit
reachable from the tip and from no origin ref (`<commit> --not
--remotes=origin`; with no origin ref at all, every ancestor), since those
are what the push publishes — each offender named by sha:

  1. closing-keywords  Every `#N` in the Closes block of every commit in
                       scope carries its own `closes`/`fixes`/`resolves` —
                       GitHub closes from a keyword in any pushed commit,
                       not only the tip. The Closes block is every
                       message line that STARTS with a closing keyword; a
                       `#N` anywhere else in the body is prose and is listed
                       as a WARN finding (a cross-reference that will not
                       close — fine if deliberate).
  2. diff-vs-claim     Prints the changed-file count and paths. FAIL when the
                       message names paths and the diff touches any path not
                       under them (and not under an --allow-path), or when the
                       message names no path and the diff exceeds --max-files.
  3. confidentiality   `#1\\d{3}` anywhere in the message of any commit in
                       scope (an observation id), any internal filename
                       (PENDING.md, registry.md, process-record.md,
                       skill-updates/), and any term from the config's
                       ```tripwire-terms``` block are hard stops, whoever
                       authored the commit — except a term the config's
                       ```vendor-as-subject```
                       block lists for THIS repo (`<repo-name>: term, term`),
                       which passes here and nowhere else. The term count
                       ingested is printed, exactly as confidentiality_scan.py
                       prints it. And over every commit in scope (not yet on
                       origin/<target-branch>) AUTHORED BY THE MAINTAINER
                       (config: Commit email): a `Claude-Session:` line, or a
                       `Co-authored-by:` whose address is not a
                       users.noreply.github.com address, refuses — the
                       pipeline's trailer block carries human credit only.
                       Contributor-authored commits and history already on
                       origin are never checked for this.
  4. signature         --pre-bundle: every commit in scope must carry NO
                       signature (no `gpgsig` header) — a sandbox signature is
                       never the maintainer's. At push to --target-branch
                       main: every commit in scope must be signed (header
                       present); a bad, expired or revoked state refuses; each
                       signing key's fingerprint must equal the config's
                       `Signing key`
                       (else "4 signing-key" is a SKIP with a line, never a
                       pass); a signature that cannot be verified here refuses
                       unless --allow-unverifiable-signature.
                       Second accepted form, both modes — a verbatim
                       contribution: a commit whose author email is not the
                       config's Commit email AND whose sha is an ancestor of
                       a `refs/pull/N/head` on origin (`git ls-remote origin
                       'refs/pull/*/head'`, then `git merge-base
                       --is-ancestor`) prints `contributor commit, PR #N,
                       signature left as submitted` and its signature is not
                       examined. The maintainer's merge commit above it is
                       judged as before. When origin cannot be listed the
                       carve-out does not apply and the check says so.
  5. credit-symmetry   With --release-body FILE: the set of `@handle` mentions
                       in the release body equals the union of the logins in
                       the `Co-authored-by:` / `Reported-by:` trailers over
                       the release's commit range — --release-range A..B, by
                       default the previous annotated tag to --commit (login
                       taken from the `ID+login@users.noreply.github.com`
                       form, else the name; AI-tool trailers are not people
                       and are excluded) — plus the GitHub login of every
                       verbatim contribution's author in that range (check
                       4's second form): from the PR head's noreply author
                       address, else from the PR on GitHub via `gh api`,
                       else the author email's login part, reported as
                       unverified. --single-commit reads --commit alone
                       (a squashed release). Every credit trailer uses one
                       class — a `Reported-by:` beside `Co-authored-by:`
                       refuses unless --allow-mixed-trailers.
                       --draft-thanks A..B prints the Thanks line from the
                       same set — one source, two renderings — for the
                       release-notes file; check 5 still runs on the result.
  6. rendered-shape    No blank line splits a tight list in any repo-root
                       `.md` (same predicate as the bundle validator).
  7. license-canonical The tip commit's `LICENSE` equals the canonical
                       licence file byte for byte. The path comes from
                       --license-canonical, else the config's
                       `license_canonical:` line (a relative path is tried
                       against the config's folder, its parent and the
                       working directory). SKIP when neither names one; a
                       named file that cannot be read, or a tip with no
                       `LICENSE`, refuses.
  8. readme-figures    The figures record (--figures, else
                       `readme-figures.md` beside the config): every table
                       row whose Repo cell is this repo's name (the
                       --repo-name key) must carry today's fetch date, and
                       every occurrence of its Anchor (`{}` where the
                       number sits) in the tip's File must show Value
                       rounded down to the Round step (digits compared,
                       separators ignored). A stale date, a differing
                       figure, an anchor the file no longer carries, an
                       unreadable cell or a missing File refuses. SKIP
                       when there is no record or no row for this repo.
                       A refresh step the run has to remember is skipped
                       on the busiest day; this turns it into a refusal.

Usage:
  pre-push-check.py --config CONFIG.md [--repo DIR] [--target-branch main]
                    [--max-files N] [--allow-path P ...]
                    [--release-body FILE [--release-range A..B | --single-commit]]
                    [--commit REF] [--pre-bundle] [--repo-name NAME]
                    [--allow-mixed-trailers] [--allow-unverifiable-signature]
                    [--license-canonical FILE] [--figures FILE]
  pre-push-check.py --draft-thanks A..B [--repo DIR] [--config CONFIG.md]
  pre-push-check.py --lint-commands REVIEW.md [FILE ...]
  pre-push-check.py --lint-commands=inline REVIEW.md [FILE ...]
  pre-push-check.py --selftest

Lint mode (--lint-commands) reads only the named files: in every fenced
shell block (untagged, bash, sh, zsh, shell, console) an argument carrying
an unquoted `? * [ ]` refuses. Commands handed to a human run in THEIR
shell, and interactive zsh aborts on an unmatched glob ("no matches found")
where bash passes the word through: `--format=%G?` stopped an `&&` chain
after a rebase had already rewritten main. Run it on REVIEW.md before
handover. `--lint-commands=inline` also reads the inline code spans
outside fenced blocks, in REPORT mode: a span with an unquoted glob
metacharacter is listed under "lint inline-spans" as a WARN and never
refuses. A span is exempt when the line before it carries the marker
`<!-- lint-commands: ignore -->` (an example of what not to type, a
pattern that is prose). The summary line counts spans read, hits and
exemptions, the three numbers a decision to make it a gate rests on.

Two runs per commit: `--pre-bundle` in the sandbox clone before the bundle
is written (check 4 asserts the commits are UNSIGNED there), and the full run
in the repository that pushes, chained `&&` before the push.

Config values read beside the term block (Maintainer table rows):
  | Commit email | `...` |     the maintainer identity (check 3 scope)
  | Signing key  | `SHA256:...` or a GPG fingerprint |   check 4 at push
and one line anywhere in the config (Repo conventions):
  `license_canonical:` `<path>`                         check 7
and one file beside the config:
  readme-figures.md   | Repo | File | Anchor | Source | Value | Round | Fetched |
                                                        check 8
"""
import argparse, base64, datetime, hashlib, pathlib, re, struct, subprocess, sys

CLOSE_KW = r"(?:closes|fixes|resolves)"
CLOSE_REF_RE = re.compile(CLOSE_KW + r"\s+#(\d+)", re.I)
CLOSE_LINE_RE = re.compile(r"^\s*" + CLOSE_KW + r"\b", re.I)
REF_RE = re.compile(r"(?<![\w/])#(\d+)\b")
OBS_ID_RE = re.compile(r"#1\d{3}\b")
INTERNAL_FILES = ["PENDING.md", "registry.md", "process-record.md",
                  "skill-updates/"]
TRAILER_RE = re.compile(r"^([A-Za-z][A-Za-z-]*-by):\s*(.+?)\s*$")
CREDIT_CLASSES = {"co-authored-by", "reported-by", "suggested-by",
                  "reviewed-by", "tested-by"}
MENTION_RE = re.compile(r"(?<![\w.`/])@([A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)")
NOREPLY_RE = re.compile(r"<\s*(?:\d+\+)?([^@\s>]+)@users\.noreply\.github\.com\s*>")
# A token that names a path in prose: contains a slash or a real extension.
# The slash alternative states its own end — the next character is not part
# of a path — because `\b` after a trailing `/` is never a boundary, so a
# directory written as `scripts/` before a space or comma would never match.
PATH_TOKEN_RE = re.compile(
    r"(?<![\w@])((?:[\w.-]+/)+[\w.-]*(?![\w.-])"
    r"|[\w-]+\.(?:md|py|sh|yml|yaml|json|txt|toml|cfg)\b)")
LIST_ITEM_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+\S")
# AI-tool attribution: not a person, never credit. A list — extend here.
AI_TOOL_RE = re.compile(
    r"@(?:anthropic\.com|openai\.com)\b|\[bot\]|"
    r"^\s*(?:claude|copilot|chatgpt|codex|gemini|cursor|devin)\b", re.I)
SESSION_RE = re.compile(r"^\s*claude-session:", re.I | re.M)
ADDR_RE = re.compile(r"<\s*([^>\s]+)\s*>")


def git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"FATAL: git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def load_terms(config_path):
    """Mirror of confidentiality_scan.load_terms: the fenced block is the
    only source; the line count is printed beside the term count and a
    block that cannot be parsed is fatal — no heuristic fallback."""
    text = pathlib.Path(config_path).read_text(encoding="utf-8")
    m = re.search(r"```tripwire-terms\n(.*?)```", text, re.S)
    if not m:
        sys.exit("FATAL: no ```tripwire-terms``` block in " + str(config_path))
    block = m.group(1).splitlines()
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


def load_config_values(config_path):
    """Two-cell `| Key | Value |` table rows anywhere in the config, keyed
    lower-case, backticks stripped — the Maintainer table's Commit email and
    Signing key are the ones this gate reads."""
    out = {}
    for l in pathlib.Path(config_path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*$", l)
        if m and not set(m.group(1)) <= set("-: "):
            out[m.group(1).strip().lower()] = m.group(2).strip().strip("`").strip()
    return out


def load_vendor_subject(config_path, repo_name):
    """Terms the ```vendor-as-subject``` block lists for this repo
    (`<repo-name>: term, term`); an absent block means none."""
    text = pathlib.Path(config_path).read_text(encoding="utf-8")
    m = re.search(r"```vendor-as-subject\n(.*?)```", text, re.S)
    terms = []
    for l in (m.group(1).splitlines() if m else []):
        if l.strip().startswith("#") or ":" not in l:
            continue
        repo, vals = l.split(":", 1)
        if repo.strip().lower() == repo_name.lower():
            terms += [v.strip() for v in vals.split(",") if v.strip()]
    return terms


def derive_repo_name(repo):
    r = subprocess.run(["git", "-C", str(repo), "remote", "get-url", "origin"],
                       capture_output=True, text=True)
    url = r.stdout.strip()
    if r.returncode == 0 and url:
        return re.sub(r"\.git$", "", url.rstrip("/").split("/")[-1].split(":")[-1])
    return pathlib.Path(repo).resolve().name


def scope_commits(repo, sha, target_branch):
    """Commits not yet on origin/<target>: the ones this run can still change.
    Without that ref (the first push of a new branch, a repo awaiting its
    first push, a clone made from a bundle) the scope is what the push
    publishes: every commit reachable from the tip and from no origin ref —
    history already public on another branch is not re-read, and with no
    origin ref at all that is every ancestor (a tip-only fallback would wave
    through every commit below it)."""
    base = f"origin/{target_branch}"
    r = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "-q",
                        base], capture_output=True, text=True)
    if r.returncode != 0:
        shas = git(repo, "rev-list", sha, "--not", "--remotes=origin").split()
        return shas, (f"{sha[:12]} --not --remotes=origin ({len(shas)} commits; "
                      f"no {base} ref: the commits on no origin ref)")
    shas = git(repo, "rev-list", f"{base}..{sha}").split()
    return shas, f"{base}..{sha[:12]} ({len(shas)} commits)"


def rebase_upstream(repo, target_branch, sha="HEAD"):
    """What a rewrite of the whole scope rebases onto: origin/<target>; else
    the parent of the oldest commit on no origin ref; else `--root` (git
    rebase refuses a missing name)."""
    base = f"origin/{target_branch}"
    r = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "-q",
                        base], capture_output=True, text=True)
    if r.returncode == 0:
        return base
    scope = git(repo, "rev-list", sha, "--not", "--remotes=origin").split()
    if scope:
        p = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify",
                            "-q", scope[-1] + "^"], capture_output=True,
                           text=True)
        if p.returncode == 0:
            return p.stdout.strip()[:12]
    return "--root"


class Report:
    def __init__(self):
        self.failed = False
        self.results = []

    def result(self, name, status, evidence):
        self.results.append((name, status))
        if status == "FAIL":
            self.failed = True
        print(f"[{status}] {name}")
        for line in evidence:
            print(f"        {line}")


def split_message(message):
    """Body lines and trailer lines. The trailer block is the final
    paragraph when every non-empty line in it is a `Key: value` trailer."""
    paras = re.split(r"\n\s*\n", message.strip("\n"))
    trailers = []
    if len(paras) > 1:
        last = [l for l in paras[-1].splitlines() if l.strip()]
        if last and all(TRAILER_RE.match(l) for l in last):
            trailers = last
            paras = paras[:-1]
    return "\n".join(paras), trailers


def check_closing_keywords(rep, message, repo=None, scope=()):
    # The unit is the unpushed range: GitHub closes from a keyword in any
    # pushed commit. `message` alone is read only without a repo or scope.
    if repo is not None and scope:
        messages = [(c[:12] + " ", git(repo, "log", "-1", "--format=%B", c))
                    for c in scope]
    else:
        messages = [("", message)]
    ev, bare, prose = [], [], []
    for tag, msg in messages:
        body, _ = split_message(msg)
        keyworded = set(CLOSE_REF_RE.findall(body))
        close_lines = [l for l in body.splitlines() if CLOSE_LINE_RE.match(l)]
        in_block = set()
        for l in close_lines:
            in_block.update(REF_RE.findall(l))
        refs = set()
        for l in body.splitlines():
            if not CLOSE_LINE_RE.match(l):
                refs.update(REF_RE.findall(l))
        if not tag or close_lines or refs:
            ev.append(f"{tag}keyword-prefixed refs: {len(keyworded)}; unique "
                      f"refs on Closes lines: {len(in_block)}; Closes lines: "
                      f"{len(close_lines)}")
        b = sorted(in_block - keyworded, key=int)
        if b:
            bare.append(tag + ", ".join("#" + x for x in b))
        if refs:
            prose.append(tag + ", ".join("#" + x for x in sorted(refs, key=int)))
    if messages[0][0]:
        ev.insert(0, f"messages read: {len(messages)} (every unpushed commit; "
                     "those with a #N listed)")
    if bare:
        ev.append("bare refs on Closes lines that will NOT close: "
                  + "; ".join(bare))
        rep.result("1 closing-keywords", "FAIL", ev)
        return
    rep.result("1 closing-keywords", "PASS", ev)
    if prose:
        rep.result("1 closing-keywords (prose refs)", "WARN",
                   ["#N in body prose outside the Closes block (closes "
                    "nothing; fine if deliberate): " + "; ".join(prose)])


def check_diff_vs_claim(rep, repo, commit, message, max_files, allow_paths):
    files = [f for f in git(repo, "diff-tree", "--no-commit-id", "--name-only",
                            "-r", "--root", commit).splitlines() if f]
    body, _ = split_message(message)
    # A token counts as a named path if it carries a file extension, or if
    # the tree knows it as a tracked file or a directory prefix of one (this
    # commit or its parent, for deletions). "and/or" in prose must not become
    # a path the diff violates; "SKILL.md" or "scripts/" must.
    tracked = set(git(repo, "ls-tree", "-r", "--name-only", commit).splitlines())
    if git(repo, "rev-list", "--parents", "-n", "1", commit).split()[1:]:
        tracked |= set(git(repo, "ls-tree", "-r", "--name-only",
                           commit + "^").splitlines())
    dirs = {"/".join(f.split("/")[:i]) for f in tracked
            for i in range(1, len(f.split("/")))}
    names = {f.split("/")[-1] for f in tracked}
    named = set()
    for tok in PATH_TOKEN_RE.findall(body):
        tok = tok[2:] if tok.startswith("./") else tok
        tok = tok.rstrip("./")
        if (tok in tracked or tok in dirs or ("/" not in tok and tok in names)
                or re.search(r"\.(md|py|sh|yml|yaml|json|txt|toml|cfg)$", tok)):
            named.add(tok)
    named |= {p.strip("/") for p in allow_paths}
    ev = [f"changed files: {len(files)}"] + [f"  {f}" for f in files]
    if named:
        ev.append("paths the message names (+ --allow-path): "
                  + ", ".join(sorted(named)))
        def covered(f):
            for n in named:
                if f == n or f.startswith(n.rstrip("/") + "/"):
                    return True
                if "/" not in n and f.split("/")[-1] == n:
                    return True          # a bare filename names it anywhere
                if f.endswith("/" + n):
                    return True
            return False
        outside = [f for f in files if not covered(f)]
        if outside:
            ev.append("changed but not named by the message: "
                      + ", ".join(outside))
            rep.result("2 diff-vs-claim", "FAIL", ev)
            return
        rep.result("2 diff-vs-claim", "PASS", ev)
        return
    if len(files) > max_files:
        ev.append(f"message names no path and the diff touches {len(files)} "
                  f"files > --max-files {max_files}")
        rep.result("2 diff-vs-claim", "FAIL", ev)
        return
    ev.append(f"message names no path; {len(files)} <= --max-files {max_files}")
    rep.result("2 diff-vs-claim", "PASS", ev)


def ai_trailer_hits(message):
    """Lines of a maintainer-built message that are not human credit."""
    hits = [f"session link: {l.strip()}" for l in message.splitlines()
            if SESSION_RE.match(l)]
    for l in message.splitlines():
        m = TRAILER_RE.match(l.strip())
        if not m or m.group(1).lower() != "co-authored-by":
            continue
        am = ADDR_RE.search(m.group(2))
        if not am or not am.group(1).lower().endswith("@users.noreply.github.com"):
            hits.append(f"non-GitHub-noreply co-author: {l.strip()}")
    return hits


def check_confidentiality(rep, message, terms, vendor_terms=(), repo_name="",
                          repo=None, scope=(), maintainer_email=""):
    # The unit is the unpushed range: every commit in scope, whoever wrote
    # it. `message` alone is read only without a repo or an empty scope.
    if repo is not None and scope:
        messages = [(c[:12] + " ", git(repo, "log", "-1", "--format=%B", c))
                    for c in scope]
    else:
        messages = [("", message)]
    hits = []
    exempt = {v.lower() for v in vendor_terms}
    for tag, msg in messages:
        for m in OBS_ID_RE.finditer(msg):
            hits.append(f"{tag}observation id shape {m.group(0)}")
        low = msg.lower()
        for name in INTERNAL_FILES:
            if name.lower() in low:
                hits.append(f"{tag}internal filename {name}")
        for t in terms:
            if t.lower() in low and t.lower() not in exempt:
                hits.append(f"{tag}tripwire term {t!r}")
    ev = [f"terms checked: {len(terms)}; internal filenames checked: "
          f"{len(INTERNAL_FILES)}; observation-id shape checked; messages "
          f"read: {len(messages)}"
          + (" (every unpushed commit)" if messages[0][0] else " (one)")]
    if exempt:
        ev.append(f"vendor-as-subject for {repo_name}: "
                  + ", ".join(sorted(vendor_terms)) + " (exempt in this repo only)")
    if repo is not None and not maintainer_email:
        ev.append("AI-tool trailer rule NOT run: no Commit email in the config "
                  "(the maintainer identity scopes it)")
    elif repo is not None:
        mine = 0
        for c in scope:
            if git(repo, "log", "-1", "--format=%ae", c).strip().lower() \
                    != maintainer_email.lower():
                continue
            mine += 1
            for h in ai_trailer_hits(git(repo, "log", "-1", "--format=%B", c)):
                hits.append(f"{c[:12]} {h}")
        ev.append(f"AI-tool trailer rule: {mine} maintainer-authored of "
                  f"{len(scope)} unpushed commits checked")
    if hits:
        rep.result("3 confidentiality", "FAIL", ev + ["hit: " + h for h in hits])
    else:
        rep.result("3 confidentiality", "PASS", ev)


def signature_header(repo, commit):
    """The commit object's gpgsig header (continuation lines joined), or ''."""
    raw = git(repo, "cat-file", "commit", commit)
    head = raw.split("\n\n", 1)[0].splitlines()
    out, inside = [], False
    for l in head:
        if l.startswith("gpgsig ") or l.startswith("gpgsig-sha256 "):
            inside = True
            out.append(l.split(" ", 1)[1])
        elif inside and l.startswith(" "):
            out.append(l[1:])
        else:
            inside = False
    return "\n".join(out)


def ssh_signature_fingerprint(sig):
    """SHA256 fingerprint of the public key embedded in an SSHSIG blob."""
    body = "".join(l for l in sig.splitlines() if l and not l.startswith("-----"))
    try:
        blob = base64.b64decode(body)
        if blob[:6] != b"SSHSIG":
            return ""
        n = struct.unpack(">I", blob[10:14])[0]
        key = blob[14:14 + n]
    except (ValueError, struct.error):
        return ""
    return "SHA256:" + base64.b64encode(hashlib.sha256(key).digest()).decode().rstrip("=")


def same_key(fp, configured):
    if configured.upper().startswith("SHA256:"):
        return fp.split(":", 1)[-1] == configured.split(":", 1)[-1]
    a, b = (re.sub(r"[^0-9A-F]", "", x.upper()) for x in (fp, configured))
    return bool(a and b) and (a.endswith(b) or b.endswith(a))


def pr_heads(repo):
    """({sha: PR number} for every refs/pull/N/head on origin, note) read with
    `git ls-remote` — the verifiable property the verbatim-contribution
    carve-out rests on. ({}, note) when origin cannot be listed: the
    carve-out then applies to nothing and the note says why."""
    cmd = "git ls-remote origin 'refs/pull/*/head'"
    try:
        r = subprocess.run(["git", "-C", str(repo), "ls-remote", "origin",
                            "refs/pull/*/head"], capture_output=True,
                           text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {}, (f"origin not listed ({e.__class__.__name__}): no "
                    "contributor carve-out this run")
    if r.returncode != 0:
        why = (r.stderr.strip().splitlines() or ["exit %d" % r.returncode])[0]
        return {}, f"origin not listed ({why}): no contributor carve-out this run"
    heads = {}
    for l in r.stdout.splitlines():
        sha, _, ref = l.partition("\t")
        m = re.match(r"refs/pull/(\d+)/head$", ref)
        if m:
            heads[sha] = int(m.group(1))
    return heads, f"PR heads on origin: {len(heads)} ({cmd})"


def contributor_pr(repo, commit, maintainer_email, heads):
    """The number of the PR whose head on origin reaches this commit, when
    the commit is not the maintainer's — the one path to the second accepted
    form of check 4; None otherwise. A maintainer-authored commit never
    qualifies, a reworked contribution is maintainer-authored by the fold-in
    rule, and a PR head absent from this repo cannot vouch (it was never
    merged here). The lowest PR number reaching the commit is named."""
    if not heads or not maintainer_email:
        return None
    author = git(repo, "log", "-1", "--format=%ae", commit).strip().lower()
    if author == maintainer_email.lower():
        return None
    for sha, n in sorted(heads.items(), key=lambda kv: kv[1]):
        r = subprocess.run(["git", "-C", str(repo), "merge-base",
                            "--is-ancestor", commit, sha],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return n
    return None


def github_slug(repo):
    """owner/name when origin is a GitHub URL, else ''."""
    r = subprocess.run(["git", "-C", str(repo), "remote", "get-url", "origin"],
                       capture_output=True, text=True)
    m = re.search(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?/?$",
                  r.stdout.strip()) if r.returncode == 0 else None
    return m.group(1) if m else ""


def pr_author_login(repo, commit, pr, heads):
    """(login, verified) for a verbatim contribution's author. The PR head's
    author address in the `ID+login@users.noreply.github.com` form names the
    login outright; else the PR's author on GitHub via `gh api` when origin
    is a GitHub repo and the call succeeds; else the author email's login
    part, reported as unverified — a reviewer confirms it by eye."""
    head = next((s for s, n in heads.items() if n == pr), None)
    ident = ""
    for c in ([head] if head else []) + [commit]:
        r = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%an <%ae>",
                            c], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            ident = r.stdout.strip()
            break
    nm = NOREPLY_RE.search(ident)
    if nm:
        return nm.group(1), True
    slug = github_slug(repo)
    if slug:
        try:
            r = subprocess.run(["gh", "api", f"repos/{slug}/pulls/{pr}", "--jq",
                                ".user.login"], capture_output=True, text=True,
                               timeout=30)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip(), True
        except (OSError, subprocess.TimeoutExpired):
            pass
    am = ADDR_RE.search(ident)
    local = (am.group(1) if am else ident).split("@")[0]
    return local or "unknown", False


def check_signature(rep, repo, commit, target_branch, allow_unverifiable,
                    pre_bundle=False, scope=(), signing_key="",
                    maintainer_email="", heads=None, heads_note=""):
    # Verbatim contributions (the second accepted form) are named first and
    # left out of the signature loop in both modes; their signature is the
    # contributor's own and is not examined.
    commits = list(scope) or [commit]
    verbatim = {}
    for c in commits:
        n = contributor_pr(repo, c, maintainer_email, heads or {})
        if n:
            verbatim[c] = n
    carve = ([heads_note] if heads_note else []) + [
        f"{c[:12]} contributor commit, PR #{n}, signature left as submitted"
        for c, n in verbatim.items()]
    own = [c for c in commits if c not in verbatim]
    if pre_bundle:
        signed = [c for c in own if signature_header(repo, c)]
        ev = [f"--pre-bundle: {len(own)} of {len(commits)} commits checked for a "
              "gpgsig header; the sandbox must build unsigned, the maintainer "
              "signs at push"] + carve
        if signed:
            rep.result("4 signature", "FAIL", ev + [
                "signed in the sandbox (never the maintainer's key): "
                + ", ".join(c[:12] for c in signed),
                "pin and rebuild: git config commit.gpgsign false && git config "
                "tag.gpgsign false && git rebase --force-rebase --no-gpg-sign "
                + rebase_upstream(repo, target_branch, commit)])
        else:
            rep.result("4 signature", "PASS", ev + ["no commit carries a signature"])
        return
    if target_branch != "main":
        rep.result("4 signature", "SKIP",
                   [f"target branch {target_branch!r} is not main"])
        return
    # The unit is the unpushed range: every commit in scope is judged on its
    # own and named by sha; the worst verdict is the check's.
    verdicts, fps = [], []
    ev = [f"{len(own)} of {len(commits)} commit(s) in scope checked"] + carve
    for c in own:
        v, lines, fp = commit_signature_verdict(repo, c, allow_unverifiable,
                                                signing_key)
        verdicts.append(v)
        fps.append(fp)
        ev.append(f"{c[:12]} {v}")
        ev += ["  " + l for l in lines]
    commits = own
    unsigned = [c for c, v in zip(commits, verdicts) if v == "FAIL"]
    if (len(unsigned) > 1 or (unsigned and unsigned[0] != commits[0])) and verbatim:
        ev.append("sign the maintainer's own commits one by one (git rebase -i "
                  "with `exec git commit --amend --no-edit -S` after each) and "
                  "re-run this check — a whole-range `rebase -S` would rewrite "
                  "the contributor commits above and void their carve-out")
    elif len(unsigned) > 1 or (unsigned and unsigned[0] != commits[0]):
        ev.append("sign every commit in the range before pushing to main: "
                  "git rebase --force-rebase -S "
                  f"{rebase_upstream(repo, target_branch, commit)} && re-run this check")
    elif unsigned:
        ev.append("sign before pushing to main: "
                  "git commit --amend --no-edit -S && re-run this check")
    status = "FAIL" if "FAIL" in verdicts else \
        "WARN" if "WARN" in verdicts else "PASS"
    rep.result("4 signature", status, ev)
    if not signing_key:
        seen = sorted({f for f in fps if f}) or ["unknown"]
        rep.result("4 signing-key", "SKIP",
                   ["signing key not configured — add a `Signing key` row "
                    "(fingerprint) to the config's Maintainer table; the key "
                    "that signed was NOT compared: " + ", ".join(seen)])


def commit_signature_verdict(repo, commit, allow_unverifiable, signing_key):
    """One commit's push-side verdict (PASS / WARN / FAIL), its evidence
    lines and the signing key's fingerprint ('' when absent)."""
    r = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%G?",
                        commit], capture_output=True, text=True)
    state = (r.stdout.strip() or "?")
    meaning = {"G": "good signature", "U": "good signature, untrusted key",
               "E": "signature present, cannot be checked here",
               "N": "NO signature", "B": "bad signature", "X": "expired",
               "Y": "expired key", "R": "revoked key"}.get(state, "unknown")
    ev = [f"git log -1 --format=%G? -> {state} ({meaning})"]
    if r.stderr.strip():
        # ssh signing with no allowedSignersFile reports N and explains on
        # stderr — show it, or a signed commit looks unsigned for no reason
        ev.append("git: " + r.stderr.strip().splitlines()[0])
    header = signature_header(repo, commit)
    if header and state == "N":
        state = "E"          # a header is present: unverifiable here, not absent
        ev.append("gpgsig header present: treated as E (cannot be checked here)")
    fp = ""
    if header:
        fp = ssh_signature_fingerprint(header) if "SSH SIGNATURE" in header else \
            git(repo, "log", "-1", "--format=%GF", commit).strip()
        ev.append(f"signing key fingerprint: {fp or 'not determinable here'}")
    if not header or state in ("B", "X", "Y", "R"):
        return "FAIL", ev, fp
    if signing_key and fp and not same_key(fp, signing_key):
        return "FAIL", ev + [
            f"signed by a key that is not the maintainer's configured key "
            f"({signing_key}) — a sandbox or foreign key"], fp
    if state in ("G", "U") and (fp or not signing_key):
        return "PASS", ev, fp
    if allow_unverifiable:
        return "WARN", ev + ["accepted under --allow-unverifiable-signature; "
                             "verify `verification.verified` on the remote "
                             "object"], fp
    return "FAIL", ev, fp


def trailer_logins(trailers):
    by_class = {}
    for t in trailers:
        m = TRAILER_RE.match(t)
        key, val = m.group(1).lower(), m.group(2)
        if key not in CREDIT_CLASSES:
            continue
        if AI_TOOL_RE.search(val):
            continue                 # an AI tool is not a contributor
        nm = NOREPLY_RE.search(val)
        login = nm.group(1) if nm else re.split(r"\s*<", val)[0].strip()
        by_class.setdefault(key, set()).add(login.lower())
    return by_class


def release_commits(repo, sha, release_range, single):
    """The commits whose trailers feed the Thanks section, and a label."""
    if single:
        return [sha], f"single commit {sha[:12]} (--single-commit)"
    if release_range:
        return git(repo, "rev-list", release_range).split(), \
            f"range {release_range}"
    r = subprocess.run(["git", "-C", str(repo), "describe", "--abbrev=0",
                        sha + "^"], capture_output=True, text=True)
    if r.returncode != 0:
        return [sha], (f"single commit {sha[:12]} (no previous annotated tag "
                       "to derive a range from)")
    prev = r.stdout.strip()
    return git(repo, "rev-list", f"{prev}..{sha}").split(), \
        f"range {prev}..{sha[:12]} (previous annotated tag to --commit)"


def credit_sources(repo, commits, maintainer_email="", heads=None):
    """The credit set check 5 compares and --draft-thanks prints: trailer
    logins by class, the AI-tool trailer count, verbatim PR authors."""
    by_class, ai, authors = {}, 0, {}
    for c in commits:
        _, trailers = split_message(git(repo, "log", "-1", "--format=%B", c))
        ai += sum(1 for t in trailers if AI_TOOL_RE.search(t))
        for k, v in trailer_logins(trailers).items():
            by_class.setdefault(k, set()).update(v)
        n = contributor_pr(repo, c, maintainer_email, heads or {})
        if n:
            login, verified = pr_author_login(repo, c, n, heads)
            authors.setdefault(login.lower(), (n, verified))
    return by_class, ai, authors


def draft_thanks(repo, commits, maintainer_email="", heads=None):
    """The release notes' Thanks line, from the same set check 5 reads."""
    by_class, _, authors = credit_sources(repo, commits, maintainer_email, heads)
    names = sorted(set().union(*by_class.values(), set(authors)))
    if not names:
        return "", by_class, authors
    at = ["@" + n for n in names]
    return ("Thanks to " + (at[0] if len(at) == 1 else
                            ", ".join(at[:-1]) + " and " + at[-1]) + "."), \
        by_class, authors


def check_credit_symmetry(rep, repo, commits, label, body_path, allow_mixed,
                          maintainer_email="", heads=None):
    by_class, ai, authors = credit_sources(repo, commits, maintainer_email,
                                           heads)
    body = pathlib.Path(body_path).read_text(encoding="utf-8")
    mentions = {m.lower() for m in MENTION_RE.findall(body)}
    trailered = set().union(*by_class.values()) if by_class else set()
    credited = trailered | set(authors)
    ev = [f"trailer source: {label}, {len(commits)} commits; AI-tool trailers "
          f"excluded: {ai}",
          f"@mentions in release body: {len(mentions)}; credit trailers: "
          f"{sum(len(v) for v in by_class.values())} "
          f"({', '.join(f'{k}={len(v)}' for k, v in sorted(by_class.items())) or 'none'})",
          f"verbatim PR authors (check 4's second form): {len(authors)}"
          + "".join(f"; @{l} (PR #{n}" + ("" if v else ", login unverified — the "
                                          "author email's login part") + ")"
                    for l, (n, v) in sorted(authors.items()))]
    ok = True
    if mentions != credited:
        ok = False
        if trailered - mentions:
            ev.append("in trailers, not mentioned: "
                      + ", ".join("@" + x for x in sorted(trailered - mentions)))
        if set(authors) - mentions:
            ev.append("verbatim PR author not mentioned: "
                      + ", ".join(f"@{x} (PR #{authors[x][0]})"
                                  for x in sorted(set(authors) - mentions)))
        if mentions - credited:
            ev.append("mentioned, no trailer: "
                      + ", ".join("@" + x for x in sorted(mentions - credited)))
    if len(by_class) > 1 and not allow_mixed:
        ok = False
        ev.append("mixed trailer classes: " + ", ".join(sorted(by_class))
                  + " (pass --allow-mixed-trailers with the reason stated in "
                    "the review notes)")
    rep.result("5 credit-symmetry", "PASS" if ok else "FAIL", ev)


def check_rendered_shape(rep, repo):
    def kind(m):
        return (m.group(1), m.group(2)[0].isdigit()) if m else None
    hits, files = [], sorted(pathlib.Path(repo).glob("*.md"))
    for p in files:
        raw = p.read_text(encoding="utf-8", errors="replace")
        prose = re.sub(r"(?ms)^```.*?^```[ \t]*$",
                       lambda m: re.sub(r"[^\n]+", "~", m.group(0)), raw)
        lines = prose.splitlines()
        items = [kind(LIST_ITEM_RE.match(l)) for l in lines]
        for i, line in enumerate(lines):
            if line.strip() or (i and not lines[i - 1].strip()):
                continue
            prev = next((j for j in range(i - 1, -1, -1) if lines[j].strip()), None)
            nxt = next((j for j in range(i + 1, len(lines)) if lines[j].strip()), None)
            if prev is None or nxt is None or not items[prev] or items[prev] != items[nxt]:
                continue
            tight = (prev > 0 and items[prev - 1] == items[prev]) or \
                    (nxt + 1 < len(lines) and items[nxt + 1] == items[nxt])
            if tight:
                hits.append(f"{p.name}:{i + 1}: blank line splits a list in two")
    ev = [f"repo-root .md files checked: {len(files)}"]
    rep.result("6 rendered-shape", "FAIL" if hits else "PASS", ev + hits)


LICENSE_CANONICAL_RE = re.compile(
    r"^[\s>*-]*`?license_canonical:`?\s*`([^`]+)`|^[\s>*-]*license_canonical:\s*(\S+)",
    re.M)


def load_license_canonical(config_path):
    """(path, where it came from) for the config's `license_canonical:` line,
    or (None, None). A relative path is resolved against the config's
    folder, its parent (the workspace folder) and the working directory, in
    that order; the first that exists wins, else the first candidate is
    returned so the check can name what it looked for."""
    text = pathlib.Path(config_path).read_text(encoding="utf-8")
    m = LICENSE_CANONICAL_RE.search(text)
    if not m:
        return None, None
    raw = (m.group(1) or m.group(2)).strip()
    p = pathlib.Path(raw).expanduser()
    if p.is_absolute():
        return p, "config license_canonical"
    base = pathlib.Path(config_path).resolve().parent
    cands = [base / p, base.parent / p, pathlib.Path.cwd() / p]
    return next((c for c in cands if c.is_file()), cands[0]), "config license_canonical"


def check_license_canonical(rep, repo, commit, canonical, source):
    name = "7 license-canonical"
    if canonical is None:
        rep.result(name, "SKIP", ["no canonical licence path configured "
                                  "(config `license_canonical:` or --license-canonical)"])
        return
    canonical = pathlib.Path(canonical)
    ev = [f"canonical: {canonical} ({source})"]
    if not canonical.is_file():
        rep.result(name, "FAIL", ev + ["the canonical file cannot be read — "
                                       "a configured check that cannot run refuses"])
        return
    want = canonical.read_bytes()
    r = subprocess.run(["git", "-C", str(repo), "show", f"{commit}:LICENSE"],
                       capture_output=True)
    if r.returncode != 0:
        rep.result(name, "FAIL", ev + [f"no LICENSE in {commit[:12]}"])
        return
    got = r.stdout
    def digest(b):
        return f"{len(b)} bytes, sha256 {hashlib.sha256(b).hexdigest()[:16]}"
    ev += [f"LICENSE @ {commit[:12]}: {digest(got)}",
           f"canonical file: {digest(want)}"]
    if got == want:
        rep.result(name, "PASS", ev)
        return
    a, b = got.splitlines(), want.splitlines()
    line = next((i + 1 for i, (x, y) in enumerate(zip(a, b)) if x != y),
                min(len(a), len(b)) + 1)
    rep.result(name, "FAIL", ev + [f"first difference at line {line} "
                                   f"({len(a)} lines vs {len(b)} canonical); "
                                   "copy the canonical file over LICENSE"])


FIGURE_COLS = ("repo", "file", "anchor", "source", "value", "round", "fetched")
FIGURE_SEPS = ",.'_   "


def table_cells(line):
    """The cells of a Markdown table row, or None. A `|` inside a backtick
    span or escaped as `\\|` is cell text (a source command may pipe)."""
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|") and len(s) > 1):
        return None
    cells, cur, code, i = [], [], False, 1
    while i < len(s) - 1:
        c = s[i]
        if c == "\\" and s[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if c == "`":
            code = not code
        if c == "|" and not code:
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
        i += 1
    cells.append("".join(cur).strip())
    return cells


def load_figures(path, repo_name):
    """(line number, {column: value}) for every row of the figures record
    whose Repo cell names this repo. A row for this repo with the wrong
    cell count is returned with an `error` key, never dropped: a row the
    gate cannot read must refuse, not pass."""
    rows = []
    for no, line in enumerate(pathlib.Path(path).read_text(
            encoding="utf-8", errors="replace").splitlines(), 1):
        cells = table_cells(line)
        if not cells or set("".join(cells)) <= set("-: "):
            continue
        if cells[0].strip("`").strip().lower() != repo_name.lower():
            continue
        if len(cells) != len(FIGURE_COLS):
            rows.append((no, {"error": f"{len(cells)} cells, want "
                                       f"{len(FIGURE_COLS)}"}))
            continue
        rows.append((no, {k: v.strip("`").strip()
                          for k, v in zip(FIGURE_COLS, cells)}))
    return rows


def check_readme_figures(rep, repo, commit, figures, repo_name, today,
                         named=False):
    name = "8 readme-figures"
    if figures is None or not pathlib.Path(figures).is_file():
        if named:
            rep.result(name, "FAIL", [f"--figures {figures} cannot be read — "
                                      "a configured check that cannot run refuses"])
            return
        rep.result(name, "SKIP", [f"no figures record ({figures or 'none named'})"])
        return
    rows = load_figures(figures, repo_name)
    if not rows:
        rep.result(name, "SKIP", [f"no row for repo {repo_name!r} in {figures}"])
        return
    ev = [f"record: {figures}; rows for {repo_name}: {len(rows)}; push day {today}"]
    hits, texts = [], {}
    for no, row in rows:
        tag = f"{pathlib.Path(figures).name}:{no}"
        if "error" in row:
            hits.append(f"{tag}: unreadable row ({row['error']})")
            continue
        try:
            fetched = datetime.date.fromisoformat(row["fetched"])
            value = int(row["value"].translate({ord(c): None for c in FIGURE_SEPS}))
            step = int(row["round"].translate({ord(c): None for c in FIGURE_SEPS}))
            if step <= 0:
                raise ValueError("Round must be positive")
        except ValueError:
            hits.append(f"{tag}: unreadable Value, Round or Fetched cell "
                        f"({row['value']!r}, {row['round']!r}, {row['fetched']!r})")
            continue
        want = value // step * step
        ev.append(f"  {tag}: {row['file']} `{row['anchor']}` = {want:,} "
                  f"(value {value}, round {step}; fetched {fetched})")
        if fetched < today:
            hits.append(f"{tag}: fetched {fetched}, older than the push day "
                        f"{today} — re-read {row['source']} uncached and "
                        "refresh the figure and the row")
        if row["anchor"].count("{}") != 1:
            hits.append(f"{tag}: the anchor needs exactly one {{}} slot")
            continue
        if row["file"] not in texts:
            r = subprocess.run(["git", "-C", str(repo), "show",
                                f"{commit}:{row['file']}"], capture_output=True)
            # Whitespace runs collapse on both sides, so a figure whose
            # sentence wraps across README lines is still found.
            texts[row["file"]] = (re.sub(r"\s+", " ", r.stdout.decode("utf-8", "replace"))
                                  if r.returncode == 0 else None)
        text = texts[row["file"]]
        if text is None:
            hits.append(f"{tag}: no {row['file']} in {commit[:12]}")
            continue
        pre, post = re.sub(r"\s+", " ", row["anchor"]).split("{}")
        num = r"(\d(?:[\d" + re.escape(FIGURE_SEPS) + r"]*\d)?)"
        found = list(re.finditer(re.escape(pre) + num + re.escape(post), text))
        if not found:
            hits.append(f"{tag}: anchor not found in {row['file']} — the wording "
                        "changed; update the row's Anchor with the README")
        for m in found:
            got = int(re.sub(r"\D", "", m.group(1)))
            if got != want:
                hits.append(f"{tag}: {row['file']} says {m.group(1)!r}, the record "
                            f"gives {want:,}")
    rep.result(name, "FAIL" if hits else "PASS", ev + hits)


SHELL_FENCES = {"", "bash", "sh", "zsh", "shell", "console", "shell-session"}
GLOB_CHARS = set("?*[]")
LONE_WORDS = {"[", "]", "[[", "]]"}       # test-command brackets, not patterns


def unquoted_glob_words(text):
    """(line offset, word) for each word of a shell block that carries a glob
    metacharacter OUTSIDE any quoting. Quoting spans lines, so the block is
    read whole. Single quotes, double quotes, $'...', backslash escapes,
    ${...} and $((...)) protect; `$?` is a parameter, not a pattern.
    Interactive zsh aborts a command on an unmatched glob ("no matches
    found") where bash passes the word through, so the author's shell is no
    evidence."""
    words, cur, raw, i, n = [], [], [], 0, len(text)
    at = [0]

    def flush():
        if raw and any(c in GLOB_CHARS for c in cur) and "".join(raw) not in LONE_WORDS:
            words.append((at[0], "".join(raw)))
        cur.clear()
        raw.clear()

    def take(j):
        if not raw:
            at[0] = text.count("\n", 0, i)
        raw.append(text[i:j])
        return j

    while i < n:
        c = text[i]
        if c in " \t\n;|&()<>":
            flush()
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            i = take(i + 2)
            continue
        if c == "'" or text.startswith("$'", i) or c == '"':
            ansi = c == "$"
            q = "'" if c != '"' else '"'
            j = i + (2 if ansi else 1)
            while j < n and text[j] != q:
                j += 2 if (text[j] == "\\" and (ansi or q == '"')) else 1
            i = take(j + 1)
            continue
        if text.startswith("${", i) or text.startswith("$((", i):
            close, depth, j = ("}", "{") if text[i + 1] == "{" else (")", "("), 0, i + 1
            while j < n:
                if text[j] == close[1]:
                    depth += 1
                elif text[j] == close[0]:
                    depth -= 1
                    if depth == 0 and (close[0] == "}" or text[j - 1] == ")"):
                        break
                j += 1
            i = take(j + 1)
            continue
        if text.startswith("$?", i):
            i = take(i + 2)
            continue
        if c == "#" and not raw:
            while i < n and text[i] != "\n":
                i += 1                    # a comment (itself a block-rule breach)
            continue
        cur.append(c)
        i = take(i + 1)
    flush()
    return words


INLINE_SPAN_RE = re.compile(r"(`+)(?!`)(.+?)(?<!`)\1(?!`)")
LINT_IGNORE_RE = re.compile(r"<!--\s*lint-commands:\s*ignore\s*-->")


def check_command_blocks(rep, paths, inline=False):
    """Lint mode: every fenced shell block (untagged or bash/sh/zsh/shell/
    console) of a REVIEW.md-style handover is read line by line; an argument
    carrying an unquoted `? * [ ]` refuses — single-quote it
    (`--format='%G?'`). With `inline`, the inline code spans of the prose
    outside fenced blocks are read the same way and REPORTED (WARN, never a
    refusal); a span is exempt when the line before it carries
    `<!-- lint-commands: ignore -->`."""
    hits, blocks = [], 0
    span_hits, spans, exempt = [], 0, 0
    for p in paths:
        fence, body, prev = None, [], ""
        for no, line in enumerate(pathlib.Path(p).read_text(
                encoding="utf-8", errors="replace").splitlines(), 1):
            m = re.match(r"^\s*(`{3,}|~{3,})\s*([\w-]*)", line)
            if m and fence is None:
                fence, first = (m.group(1), m.group(2).lower() in SHELL_FENCES), no + 1
                blocks += fence[1]
                prev = ""
                continue
            if fence and line.strip().startswith(fence[0]):
                if fence[1]:
                    for off, w in unquoted_glob_words("\n".join(body)):
                        hits.append(f"{p}:{first + off}: unquoted glob "
                                    f"metacharacter in {w!r}")
                fence, body, prev = None, [], ""
                continue
            if fence:
                body.append(re.sub(r"^\s*\$\s+", "", line))
                continue
            if inline:
                found = INLINE_SPAN_RE.findall(line)
                spans += len(found)
                if found and LINT_IGNORE_RE.search(prev):
                    exempt += len(found)
                else:
                    for _, span in found:
                        for _, w in unquoted_glob_words(span.strip()):
                            span_hits.append(f"{p}:{no}: unquoted glob "
                                             f"metacharacter in inline span {w!r}")
            prev = line
    ev = [f"files read: {len(paths)}; shell blocks checked: {blocks}"]
    rep.result("lint command-blocks", "FAIL" if hits else "PASS", ev + hits)
    if inline:
        ev = [f"inline code spans read: {spans}; hits: {len(span_hits)}; exempt "
              f"(marker on the preceding line): {exempt}; report mode — never "
              "refuses"]
        rep.result("lint inline-spans", "WARN" if span_hits else "PASS",
                   ev + span_hits)


def selftest():
    """Fixture repos for the multi-commit release, the AI-tool trailer rule
    (maintainer vs contributor vs already on origin), vendor-as-subject, the
    pre-bundle no-signature assertion, the signing-key comparison, a
    tripwire term, an unsigned commit and a bare Closes ref planted below the
    tip (the range unit of checks 1, 3 and 4), and a repo with no origin ref
    (scope = every commit reachable from the tip), a new branch with no
    origin/<branch> ref on a main whose public history carries a check-3 hit
    (scope = the commits on no origin ref), the --draft-thanks line, and the
    command-block
    lint (unquoted glob metacharacters in a handed-over shell block),
    the canonical-licence comparison (check 7), directories named with a
    trailing slash beside a prose "and/or" (check 2), and current, stale,
    drifted and unanchored README figures (check 8). Git
    runs with the global and system config ignored, so the environment's own
    signing default cannot leak into the fixture."""
    import contextlib, io, os, tempfile
    os.environ.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    fails = []

    def expect(name, fn, want, needle=None):
        rep = Report()
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            fn(rep)
        got = dict(rep.results)
        ok = all(got.get(k) == v for k, v in want.items()) and \
            (needle is None or needle in buf.getvalue())
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {got}")
        if not ok:
            fails.append(name)
            print("        " + buf.getvalue().replace("\n", "\n        "))

    def fake_ssh_sig(seed):
        def s(b):
            return struct.pack(">I", len(b)) + b
        key = s(b"ssh-ed25519") + s(hashlib.sha256(seed).digest())
        blob = (b"SSHSIG" + struct.pack(">I", 1) + s(key) + s(b"git") + s(b"")
                + s(b"sha512") + s(b"\0" * 64))
        b64 = base64.b64encode(blob).decode()
        lines = ["-----BEGIN SSH SIGNATURE-----"] + \
            [b64[i:i + 70] for i in range(0, len(b64), 70)] + \
            ["-----END SSH SIGNATURE-----"]
        fp = "SHA256:" + base64.b64encode(hashlib.sha256(key).digest()).decode().rstrip("=")
        return lines, fp

    with tempfile.TemporaryDirectory() as d:
        cfg = pathlib.Path(d, "config.md")
        cfg.write_text("| Key | Value |\n|---|---|\n| Commit email | `me@example.org` |\n\n"
                       "```tripwire-terms\nacmeclient\nvendortool\n```\n\n"
                       "```vendor-as-subject\ndemo-repo: vendortool\n```\n",
                       encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            terms = load_terms(cfg)
        values = load_config_values(cfg)
        repo = pathlib.Path(d, "demo-repo")
        repo.mkdir()
        git(repo, "init", "-q", "-b", "main")
        for k, v in (("user.name", "Maintainer"), ("user.email", "me@example.org"),
                     ("commit.gpgsign", "false"), ("tag.gpgsign", "false")):
            git(repo, "config", k, v)          # the per-repo identity snippet

        def commit(msg, author="Maintainer <me@example.org>", path="SKILL.md"):
            f = repo / path
            f.write_text(f.read_text() + "x\n" if f.exists() else "x\n")
            git(repo, "add", path)
            git(repo, "commit", "-q", "--author", author, "-m", msg)
            return git(repo, "rev-parse", "HEAD").strip()

        base = commit("Initial release")
        git(repo, "tag", "-a", "v1.0.0", "-m", "v1.0.0")
        git(repo, "update-ref", "refs/remotes/origin/main", base)
        noreply = "users.noreply.github.com"
        commit("Fix the gate\n\ncloses #1\n\n"
               f"Co-authored-by: Alice <1+alice@{noreply}>")
        commit("Fix the scan\n\ncloses #2\n\n"
               f"Co-authored-by: Bob <2+bob@{noreply}>")
        tip = commit("Bump version to 1.1.0")
        git(repo, "tag", "-a", "v1.1.0", "-m", "v1.1.0")
        body = pathlib.Path(d, "body.md")
        body.write_text("Thanks to @alice and @bob.\n", encoding="utf-8")

        cs, label = release_commits(repo, tip, None, False)
        expect("multi-commit release: range union matches the body",
               lambda r: check_credit_symmetry(r, repo, cs, label, body, False),
               {"5 credit-symmetry": "PASS"})
        c1, l1 = release_commits(repo, tip, None, True)
        expect("multi-commit release: single-commit mode refuses",
               lambda r: check_credit_symmetry(r, repo, c1, l1, body, False),
               {"5 credit-symmetry": "FAIL"})
        c2, l2 = release_commits(repo, tip, "v1.0.0..v1.1.0", False)
        expect("explicit --release-range", lambda r: check_credit_symmetry(
            r, repo, c2, l2, body, False), {"5 credit-symmetry": "PASS"})
        drafted = pathlib.Path(d, "drafted.md")
        drafted.write_text(draft_thanks(repo, c2)[0] + "\n", encoding="utf-8")
        expect("--draft-thanks: the drafted line passes check 5",
               lambda r: check_credit_symmetry(r, repo, c2, l2, drafted, False),
               {"5 credit-symmetry": "PASS"})
        ok = drafted.read_text() == "Thanks to @alice and @bob.\n"
        print(f"[{'PASS' if ok else 'FAIL'}] --draft-thanks: the line names "
              f"every trailer login ({drafted.read_text().strip()!r})")
        if not ok:
            fails.append("--draft-thanks: the line names every trailer login")

        ai_msg = ("Sync the skill\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n"
                  "Claude-Session: https://example.invalid/session_x")
        ai_tip = commit(ai_msg)
        scope, _ = scope_commits(repo, ai_tip, "main")
        expect("maintainer commit with AI trailers refuses", lambda r:
               check_confidentiality(r, ai_msg, terms, [], "demo-repo", repo,
                                     scope, values.get("commit email", "")),
               {"3 confidentiality": "FAIL"})
        expect("AI trailers in a maintainer commit: excluded from credit",
               lambda r: check_credit_symmetry(
                   r, repo, *release_commits(repo, ai_tip, "v1.0.0.." + ai_tip,
                                             False), body, False),
               {"5 credit-symmetry": "PASS"})
        git(repo, "update-ref", "refs/remotes/origin/main", ai_tip)
        expect("the same commit already on origin is not checked", lambda r:
               check_confidentiality(r, "Sync", terms, [], "demo-repo", repo,
                                     scope_commits(repo, ai_tip, "main")[0],
                                     values.get("commit email", "")),
               {"3 confidentiality": "PASS"})
        contrib = commit(ai_msg.replace("Sync the skill", "Contributor fix"),
                         author="Carol <3+carol@users.noreply.github.com>")
        expect("contributor-authored commit keeps its AI trailer", lambda r:
               check_confidentiality(r, "Contributor fix", terms, [], "demo-repo",
                                     repo, scope_commits(repo, contrib, "main")[0],
                                     values.get("commit email", "")),
               {"3 confidentiality": "PASS"})
        git(repo, "update-ref", "refs/remotes/origin/main", contrib)

        vendor = load_vendor_subject(cfg, "demo-repo")
        expect("vendor-as-subject passes in its own repo", lambda r:
               check_confidentiality(r, "Document the vendortool API", terms,
                                     vendor, "demo-repo"),
               {"3 confidentiality": "PASS"})
        expect("vendor-as-subject refuses in another repo", lambda r:
               check_confidentiality(r, "Document the vendortool API", terms,
                                     load_vendor_subject(cfg, "other-repo"),
                                     "other-repo"),
               {"3 confidentiality": "FAIL"})
        expect("a client term still refuses in the vendor's repo", lambda r:
               check_confidentiality(r, "Fix for acmeclient", terms, vendor,
                                     "demo-repo"),
               {"3 confidentiality": "FAIL"})

        unsigned = commit("Plain commit")
        expect("pre-bundle: unsigned commits pass", lambda r: check_signature(
            r, repo, unsigned, "main", False, True,
            scope_commits(repo, unsigned, "main")[0]), {"4 signature": "PASS"})
        sig, fp = fake_ssh_sig(b"maintainer")

        def sign(c, lines=None):
            """Rewrite commit c with a gpgsig header (the maintainer's fake
            signature unless `lines` is another) and move main to it."""
            head, msg = git(repo, "cat-file", "commit", c).split("\n\n", 1)
            obj = head + "\ngpgsig " + "\n ".join(lines or sig) + "\n\n" + msg
            s = subprocess.run(["git", "-C", str(repo), "hash-object", "-t",
                                "commit", "-w", "--stdin"], input=obj,
                               capture_output=True, text=True).stdout.strip()
            git(repo, "update-ref", "refs/heads/main", s)
            return s

        signed = sign(unsigned)
        expect("pre-bundle: a sandbox-signed commit refuses", lambda r:
               check_signature(r, repo, signed, "main", False, True,
                               scope_commits(repo, signed, "main")[0]),
               {"4 signature": "FAIL"})
        expect("push: key not configured is a SKIP line, never a pass",
               lambda r: check_signature(r, repo, signed, "main", True),
               {"4 signing-key": "SKIP"})
        expect("push: a foreign key refuses even when unverifiable is allowed",
               lambda r: check_signature(r, repo, signed, "main", True,
                                         signing_key=fake_ssh_sig(b"other")[1]),
               {"4 signature": "FAIL"})
        expect("push: the maintainer's key, unverifiable here, WARNs when allowed",
               lambda r: check_signature(r, repo, signed, "main", True,
                                         signing_key=fp),
               {"4 signature": "WARN"})
        expect("push: an unsigned tip refuses", lambda r: check_signature(
            r, repo, unsigned, "main", True, signing_key=fp),
            {"4 signature": "FAIL"})

        # The gate's unit is the unpushed range, not the tip: a tripwire term
        # and an unsigned commit planted BELOW a clean, signed tip.
        git(repo, "update-ref", "refs/remotes/origin/main", signed)
        leak = sign(commit("Tidy the wording for acmeclient"))
        middle = commit("Plain middle commit")
        tip2 = sign(commit("Bump version to 1.2.0"))
        rng = scope_commits(repo, tip2, "main")[0]
        expect("range: a tripwire term below the tip refuses, named by sha",
               lambda r: check_confidentiality(
                   r, "Bump version to 1.2.0", terms, [], "demo-repo", repo,
                   rng, values.get("commit email", "")),
               {"3 confidentiality": "FAIL"}, leak[:12] + " tripwire term")
        expect("range: the same tip read alone passes (what tip-only missed)",
               lambda r: check_confidentiality(
                   r, "Bump version to 1.2.0", terms, [], "demo-repo", repo,
                   [tip2], values.get("commit email", "")),
               {"3 confidentiality": "PASS"})
        expect("push: an unsigned commit below a signed tip refuses, by sha",
               lambda r: check_signature(r, repo, tip2, "main", True, False,
                                         rng, fp),
               {"4 signature": "FAIL"}, middle[:12] + " FAIL")
        expect("pre-bundle: a signed commit below the tip refuses, by sha",
               lambda r: check_signature(r, repo, tip2, "main", False, True,
                                         rng), {"4 signature": "FAIL"},
               leak[:12])

        # Check 1 shares the range unit: GitHub closes from any pushed commit.
        bare_c = commit("Fold two reports\n\nCloses #4, #5")
        tip3 = commit("Bump version to 1.3.0\n\ncloses #6")
        rng3 = scope_commits(repo, tip3, "main")[0]
        expect("range: a bare Closes ref below the tip refuses, named by sha",
               lambda r: check_closing_keywords(r, "", repo, rng3),
               {"1 closing-keywords": "FAIL"}, bare_c[:12] + " #5")
        expect("range: the same tip's message alone passes check 1",
               lambda r: check_closing_keywords(
                   r, "Bump version to 1.3.0\n\ncloses #6"),
               {"1 closing-keywords": "PASS"})

        # No origin ref (awaiting first push, a clone made from a bundle):
        # nothing is pushed, so the scope is every commit below the tip.
        fresh = pathlib.Path(d, "fresh-repo")
        fresh.mkdir()
        git(fresh, "init", "-q", "-b", "main")
        for k, v in (("user.name", "Maintainer"), ("user.email", "me@example.org"),
                     ("commit.gpgsign", "false"), ("tag.gpgsign", "false")):
            git(fresh, "config", k, v)
        fresh_shas = []
        for msg in ("Initial release for acmeclient", "Bump version to 1.0.1"):
            pathlib.Path(fresh, "SKILL.md").write_text(msg + "\n")
            git(fresh, "add", "SKILL.md")
            git(fresh, "commit", "-q", "-m", msg)
            fresh_shas.append(git(fresh, "rev-parse", "HEAD").strip())
        expect("no origin ref: a tripwire term below the tip refuses, by sha",
               lambda r: check_confidentiality(
                   r, "Bump version to 1.0.1", terms, [], "fresh-repo", fresh,
                   scope_commits(fresh, fresh_shas[-1], "main")[0],
                   values.get("commit email", "")),
               {"3 confidentiality": "FAIL"}, fresh_shas[0][:12] + " tripwire term")
        expect("no origin ref: the signing hint rebases from --root",
               lambda r: check_signature(
                   r, fresh, fresh_shas[-1], "main", True, False,
                   scope_commits(fresh, fresh_shas[-1], "main")[0], fp),
               {"4 signature": "FAIL"}, "git rebase --force-rebase -S --root")
        # First push of a new branch: main's public history carries a known
        # check-3 hit; the branch's own commits are clean. No
        # origin/<branch> ref, so the scope is the commits on no origin ref.
        git(fresh, "update-ref", "refs/remotes/origin/main", fresh_shas[-1])
        git(fresh, "checkout", "-q", "-b", "release/v2")
        for msg in ("Fold a report", "Bump version to 2.0.0"):
            pathlib.Path(fresh, "SKILL.md").write_text(msg + "\n")
            git(fresh, "add", "SKILL.md")
            git(fresh, "commit", "-q", "-m", msg)
        br_tip = git(fresh, "rev-parse", "HEAD").strip()
        br_scope, br_label = scope_commits(fresh, br_tip, "release/v2")

        def new_branch(r):
            print("commits in scope: " + br_label)
            check_confidentiality(r, "Bump version to 2.0.0", terms, [],
                                  "fresh-repo", fresh, br_scope,
                                  values.get("commit email", ""))
        expect("new branch, no origin/<branch>: a hit already on origin/main "
               "is out of scope", new_branch, {"3 confidentiality": "PASS"},
               "--not --remotes=origin (2 commits")
        hint = rebase_upstream(fresh, "release/v2", br_tip)
        ok = hint == fresh_shas[-1][:12]
        print(f"[{'PASS' if ok else 'FAIL'}] new branch: a rewrite hint "
              f"rebases onto the branch point ({hint})")
        if not ok:
            fails.append("new branch: a rewrite hint rebases onto the branch point")

        # Verbatim contributions: a bare repo stands in for origin and
        # carries refs/pull/N/head; a foreign-authored, foreign-signed
        # commit reachable from one keeps its signature, the maintainer's
        # merge commit above it does not get the carve-out, and the same
        # commit without the ref is refused in both modes.
        bare = pathlib.Path(d, "origin.git")
        git(bare.parent, "init", "-q", "--bare", str(bare))
        git(repo, "remote", "add", "origin", str(bare))
        git(repo, "update-ref", "refs/remotes/origin/main", tip3)
        me = values.get("commit email", "")
        dsig, _ = fake_ssh_sig(b"dave")
        pr_c = sign(commit("Contributor change",
                           author=f"Dave <4+dave@{noreply}>", path="README.md"),
                    dsig)
        git(repo, "push", "-q", "origin", f"{pr_c}:refs/pull/7/head")
        heads, note = pr_heads(repo)
        merge_u = commit("Merge pull request from dave")
        rng4 = scope_commits(repo, merge_u, "main")[0]
        expect("PR head: the contributor commit passes, the unsigned merge "
               "commit above it still refuses", lambda r: check_signature(
                   r, repo, merge_u, "main", True, False, rng4, fp, me, heads,
                   note), {"4 signature": "FAIL"}, merge_u[:12] + " FAIL")
        merge_s = sign(merge_u)
        rng4 = scope_commits(repo, merge_s, "main")[0]
        expect("PR head: foreign-signed contributor commit + maintainer-signed "
               "merge commit pass, with the message", lambda r: check_signature(
                   r, repo, merge_s, "main", True, False, rng4, fp, me, heads,
                   note), {"4 signature": "WARN"},
               pr_c[:12] + " contributor commit, PR #7, signature left as submitted")
        expect("PR head: --pre-bundle keeps the contributor's signature",
               lambda r: check_signature(r, repo, pr_c, "main", False, True,
                                         [pr_c], "", me, heads, note),
               {"4 signature": "PASS"}, "contributor commit, PR #7")
        expect("PR head: a maintainer-authored commit never gets the carve-out",
               lambda r: check_signature(r, repo, merge_s, "main", False, True,
                                         [merge_s], "", me, heads, note),
               {"4 signature": "FAIL"})
        body2 = pathlib.Path(d, "body2.md")
        body2.write_text("Thanks to @dave.\n", encoding="utf-8")
        expect("check 5: a verbatim PR author counts as credited",
               lambda r: check_credit_symmetry(r, repo, rng4, "range", body2,
                                               False, me, heads),
               {"5 credit-symmetry": "PASS"}, "@dave (PR #7)")
        expect("check 5: the release body must mention the PR author",
               lambda r: check_credit_symmetry(r, repo, rng4, "range", body,
                                               False, me, heads),
               {"5 credit-symmetry": "FAIL"},
               "verbatim PR author not mentioned: @dave (PR #7)")
        esig, _ = fake_ssh_sig(b"erin")
        erin = sign(commit("Second contribution", author="Erin <erin@example.net>",
                           path="README.md"), esig)
        git(repo, "push", "-q", "origin", f"{erin}:refs/pull/9/head")
        heads, note = pr_heads(repo)
        body3 = pathlib.Path(d, "body3.md")
        body3.write_text("Thanks to @dave and @erin.\n", encoding="utf-8")
        expect("check 5: a login not resolvable offline falls back to the "
               "email's login part, reported as unverified",
               lambda r: check_credit_symmetry(
                   r, repo, scope_commits(repo, erin, "main")[0], "range",
                   body3, False, me, heads),
               {"5 credit-symmetry": "PASS"}, "@erin (PR #9, login unverified")
        git(repo, "push", "-q", "origin", ":refs/pull/7/head", ":refs/pull/9/head")
        heads, note = pr_heads(repo)
        expect("no PR head: the same foreign-signed commit refuses at push",
               lambda r: check_signature(r, repo, merge_s, "main", True, False,
                                         rng4, fp, me, heads, note),
               {"4 signature": "FAIL"}, pr_c[:12] + " FAIL")
        expect("no PR head: the same commit refuses in --pre-bundle",
               lambda r: check_signature(r, repo, pr_c, "main", False, True,
                                         [pr_c], "", me, heads, note),
               {"4 signature": "FAIL"}, "signed in the sandbox")
        expect("origin not listable: no carve-out, and the check says so",
               lambda r: check_signature(r, repo, pr_c, "main", False, True,
                                         [pr_c], "", me,
                                         *pr_heads(pathlib.Path(d, "fresh-repo"))),
               {"4 signature": "FAIL"}, "no contributor carve-out this run")
        # Check 7: LICENSE against the canonical file, read from the tip.
        canon = pathlib.Path(d, "LICENSE.canonical.txt")
        canon.write_bytes(b"Licence text\nline two\n")
        (repo / "LICENSE").write_bytes(canon.read_bytes())
        git(repo, "add", "LICENSE")
        git(repo, "commit", "-q", "-m", "Add the licence")
        lic_ok = git(repo, "rev-parse", "HEAD").strip()
        (repo / "LICENSE").write_bytes(b"Licence text\nline two \n")
        git(repo, "add", "LICENSE")
        git(repo, "commit", "-q", "-m", "Touch the licence")
        lic_bad = git(repo, "rev-parse", "HEAD").strip()
        expect("licence: byte-identical LICENSE passes", lambda r:
               check_license_canonical(r, repo, lic_ok, canon, "flag"),
               {"7 license-canonical": "PASS"})
        expect("licence: one trailing space refuses, line named", lambda r:
               check_license_canonical(r, repo, lic_bad, canon, "flag"),
               {"7 license-canonical": "FAIL"}, "first difference at line 2")
        expect("licence: no path configured is a SKIP line", lambda r:
               check_license_canonical(r, repo, lic_ok, *load_license_canonical(cfg)),
               {"7 license-canonical": "SKIP"})
        expect("licence: a configured path that is missing refuses", lambda r:
               check_license_canonical(r, repo, lic_ok,
                                       pathlib.Path(d, "nope.txt"), "flag"),
               {"7 license-canonical": "FAIL"}, "cannot be read")
        expect("licence: a tip without LICENSE refuses", lambda r:
               check_license_canonical(r, repo, base, canon, "flag"),
               {"7 license-canonical": "FAIL"}, "no LICENSE in")
        cfg2 = pathlib.Path(d, "ws", "skill-publishing", "config.md")
        cfg2.parent.mkdir(parents=True)
        cfg2.write_text("- `license_canonical:` `skill-publishing/LICENSE.txt`"
                        " — the one licence text\n", encoding="utf-8")
        pathlib.Path(cfg2.parent, "LICENSE.txt").write_bytes(canon.read_bytes())
        expect("licence: the config line resolves against the workspace folder",
               lambda r: check_license_canonical(
                   r, repo, lic_ok, *load_license_canonical(cfg2)),
               {"7 license-canonical": "PASS"}, "config license_canonical")

        def fixture_repo(name, files):
            fx = pathlib.Path(d, name)
            fx.mkdir()
            git(fx, "init", "-q", "-b", "main")
            for k, v in (("user.name", "Maintainer"), ("user.email", "me@example.org"),
                         ("commit.gpgsign", "false")):
                git(fx, "config", k, v)
            for rel, text in files.items():
                (fx / rel).parent.mkdir(parents=True, exist_ok=True)
                (fx / rel).write_text(text, encoding="utf-8")
            git(fx, "add", "-A")
            git(fx, "commit", "-q", "-m", "Initial")
            return fx

        # Check 2: a directory named with a trailing slash is a named path.
        mv = fixture_repo("move-repo", {"references/a.md": "x\n",
                                        "scripts/b.py": "x\n", "SKILL.md": "x\n"})
        git(mv, "rm", "-q", "-r", "references", "scripts")
        mv_msg = "Move the bundle\n\nFiles: references/, scripts/\n"
        git(mv, "commit", "-q", "-m", mv_msg)
        mv_tip = git(mv, "rev-parse", "HEAD").strip()
        expect("diff-vs-claim: `references/, scripts/` names both directories",
               lambda r: check_diff_vs_claim(r, mv, mv_tip, mv_msg, 25, []),
               {"2 diff-vs-claim": "PASS"},
               "paths the message names (+ --allow-path): references, scripts")
        expect("diff-vs-claim: `and/or` in prose names no path",
               lambda r: check_diff_vs_claim(r, mv, mv_tip,
                                             "Tidy the and/or wording\n", 1, []),
               {"2 diff-vs-claim": "FAIL"}, "message names no path")

        # Check 8: README figures against the figures record.
        fr = fixture_repo("fig-repo", {"README.md": "Install it: the registry "
                                       "reports over\n4,000 installs.\n"})
        fr_tip = git(fr, "rev-parse", "HEAD").strip()
        today = datetime.date.today()
        rec = pathlib.Path(d, "readme-figures.md")
        nope = pathlib.Path(d, "no-record.md")

        def figures(value, fetched, anchor="reports over {} installs",
                    repo_cell="fig-repo"):
            rec.write_text(
                "| Repo | File | Anchor | Source | Value | Round | Fetched |\n"
                "|---|---|---|---|---|---|---|\n"
                f"| {repo_cell} | README.md | `{anchor}` | "
                f"`curl -s '<page URL>' | jq .installs` | {value} | 1000 | {fetched} |\n",
                encoding="utf-8")
            return lambda r: check_readme_figures(r, fr, fr_tip, rec, "fig-repo",
                                                  today)
        expect("figures: a current row whose figure matches passes (a wrapped "
               "line, a piped source)", figures(4321, today),
               {"8 readme-figures": "PASS"}, "= 4,000 (value 4321, round 1000")
        expect("figures: a fetch date before the push day refuses",
               figures(4321, today - datetime.timedelta(days=1)),
               {"8 readme-figures": "FAIL"}, "older than the push day")
        expect("figures: a README figure the record does not give refuses",
               figures(5300, today), {"8 readme-figures": "FAIL"},
               "README.md says '4,000', the record gives 5,000")
        expect("figures: an anchor the README no longer carries refuses",
               figures(4321, today, anchor="counted over {} installs"),
               {"8 readme-figures": "FAIL"}, "anchor not found")
        expect("figures: no row for this repo is a SKIP",
               figures(4321, today, repo_cell="other-repo"),
               {"8 readme-figures": "SKIP"}, "no row for repo 'fig-repo'")
        expect("figures: no record beside the config is a SKIP",
               lambda r: check_readme_figures(r, fr, fr_tip, nope, "fig-repo",
                                              today),
               {"8 readme-figures": "SKIP"}, "no figures record")
        expect("figures: a record named with --figures that is missing refuses",
               lambda r: check_readme_figures(r, fr, fr_tip, nope, "fig-repo",
                                              today, named=True),
               {"8 readme-figures": "FAIL"}, "cannot be read")

        # Lint mode: glob metacharacters in a handed-over command block.
        def lint(text):
            f = pathlib.Path(d, "REVIEW.md")
            f.write_text(text, encoding="utf-8")
            return lambda r: check_command_blocks(r, [str(f)])
        expect("lint: an unquoted %G? in a shell block refuses",
               lint("```bash\ngit rebase -S origin/main && git log -1 "
                    "--format=%G? && git push origin main\n```\n"),
               {"lint command-blocks": "FAIL"}, "--format=%G?")
        expect("lint: the single-quoted form passes",
               lint("```bash\ngit log -1 --format='%G?' && git push origin main\n```\n"),
               {"lint command-blocks": "PASS"})
        expect("lint: a glob inside a quoted string passes",
               lint('```\ngit commit -m "Fix *.md globs [x]?" && echo \'a*b\'\n```\n'),
               {"lint command-blocks": "PASS"})
        expect("lint: an unquoted glob in an untagged block refuses",
               lint("```\ngh api repos/o/r/issues/comments?since=2020\n```\n"),
               {"lint command-blocks": "FAIL"}, "comments?since")
        expect("lint: $?, test brackets, ${...} and $'...' are not patterns",
               lint("```bash\n[ -f x ] && echo $? ${v#*/} "
                    "$'[[:space:]]' $((2*3))\n```\n"),
               {"lint command-blocks": "PASS"})
        expect("lint: a single-quoted string spanning lines passes",
               lint("```bash\nawk 'prev ~ /^ *- / {print}\n     $0 ~ /[a-z]?/' "
                    "README.md\n```\n"),
               {"lint command-blocks": "PASS"})
        expect("lint: a hit names its file line, not its block line",
               lint("Intro.\n\n```bash\ncd repo &&\n  ls *.md\n```\n"),
               {"lint command-blocks": "FAIL"}, "REVIEW.md:5:")
        expect("lint: prose and non-shell fences are not read",
               lint("Run `ls *.md` here.\n\n```python\nx = a[0] * 2\n```\n"),
               {"lint command-blocks": "PASS"})

        # Inline report mode: the two known false positives are the
        # fixtures — a prose `ls *.md` is reported, a "never type this"
        # `--format=%G?` example is exempted by the marker.
        def lint_inline(text):
            f = pathlib.Path(d, "REVIEW.md")
            f.write_text(text, encoding="utf-8")
            return lambda r: check_command_blocks(r, [str(f)], inline=True)
        expect("inline: `ls *.md` in prose is reported as WARN, never refused",
               lint_inline("Run `ls *.md` here.\n\n```python\nx = a[0] * 2\n```\n"),
               {"lint command-blocks": "PASS", "lint inline-spans": "WARN"},
               "REVIEW.md:1: unquoted glob metacharacter in inline span '*.md'")
        expect("inline: the marker on the preceding line exempts the span",
               lint_inline("<!-- lint-commands: ignore -->\nnever type "
                           "`--format=%G?` unquoted; `git log -1` is fine.\n"),
               {"lint inline-spans": "PASS"},
               "inline code spans read: 2; hits: 0; exempt (marker on the "
               "preceding line): 2")
        expect("inline: the marker two lines above does not exempt",
               lint_inline("<!-- lint-commands: ignore -->\n\nnever type "
                           "`--format=%G?` unquoted.\n"),
               {"lint inline-spans": "WARN"}, "hits: 1")
        expect("inline: quoted globs, $?, double-backtick spans and fenced "
               "lines are not hits",
               lint_inline("Use `git log --format='%G?'` or ``echo $? "
                           "\"*.md\"``.\n\n```bash\nls *.md\n```\n"),
               {"lint command-blocks": "FAIL", "lint inline-spans": "PASS"},
               "inline code spans read: 2; hits: 0")
        rep = Report()
        with contextlib.redirect_stdout(io.StringIO()):
            check_command_blocks(rep, [str(pathlib.Path(d, "REVIEW.md"))],
                                 inline=True)
        with contextlib.redirect_stdout(io.StringIO()):
            rep2 = Report()
            lint_inline("Run `ls *.md` here.\n")(rep2)
        ok = rep.failed and not rep2.failed
        print(f"[{'PASS' if ok else 'FAIL'}] inline: only the block rule sets the "
              f"refusal (block hit: {rep.failed}; inline hit alone: {rep2.failed})")
        if not ok:
            fails.append("inline: only the block rule sets the refusal")
    print("SELFTEST: " + (f"FAILED ({len(fails)})" if fails else "all cases passed"))
    sys.exit(1 if fails else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", help="config.md with the tripwire-terms block "
                    "(required except with --lint-commands)")
    ap.add_argument("--lint-commands", nargs="+", metavar="FILE",
                    help="lint mode: refuse unquoted glob metacharacters in the "
                         "fenced shell blocks of a REVIEW.md-style handover; "
                         "spelled --lint-commands=inline FILE..., also report "
                         "them in inline code spans (never a refusal)")
    ap.add_argument("--lint-inline", action="store_true",
                    help="what --lint-commands=inline sets")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--commit", default="HEAD", help="commit to gate (default HEAD)")
    ap.add_argument("--target-branch", default="main")
    ap.add_argument("--max-files", type=int, default=25)
    ap.add_argument("--allow-path", action="append", default=[],
                    help="path or dir the diff may touch beyond what the message names")
    ap.add_argument("--release-body", help="release notes file; enables check 5")
    ap.add_argument("--release-range", help="A..B whose trailers feed check 5 "
                    "(default: previous annotated tag..--commit)")
    ap.add_argument("--single-commit", action="store_true",
                    help="check 5 reads --commit alone (a squashed release)")
    ap.add_argument("--repo-name", help="name keying the vendor-as-subject block "
                    "(default: origin URL basename, else the directory name)")
    ap.add_argument("--allow-mixed-trailers", action="store_true")
    ap.add_argument("--allow-unverifiable-signature", action="store_true")
    ap.add_argument("--license-canonical", metavar="FILE",
                    help="canonical licence file LICENSE must equal byte for "
                         "byte (overrides the config's license_canonical:)")
    ap.add_argument("--figures", metavar="FILE",
                    help="README figures record for check 8 (default: "
                         "readme-figures.md beside --config)")
    ap.add_argument("--pre-bundle", action="store_true",
                    help="sandbox run before bundling: check 4 asserts the "
                         "commits are UNSIGNED (the push-side run never passes this)")
    ap.add_argument("--draft-thanks", metavar="A..B",
                    help="print the release notes' Thanks line from the credit "
                         "trailers (and verbatim PR authors) over A..B, then exit")
    if "--selftest" in sys.argv[1:]:
        selftest()
    # `--lint-commands=inline FILE...` is the documented spelling of the
    # inline report; argparse would read "inline" as the one file.
    argv = [x for y in sys.argv[1:] for x in
            (["--lint-inline", "--lint-commands"] if y == "--lint-commands=inline"
             else [y])]
    a = ap.parse_args(argv)
    if a.lint_commands and a.lint_commands[0] == "inline" \
            and not pathlib.Path("inline").exists():
        a.lint_inline, a.lint_commands = True, a.lint_commands[1:]
    if a.lint_commands:
        rep = Report()
        check_command_blocks(rep, a.lint_commands, a.lint_inline)
        print("RESULT: " + ("REFUSED — quote before handover" if rep.failed
                            else "clear to hand over"))
        sys.exit(1 if rep.failed else 0)
    if a.draft_thanks:
        repo = pathlib.Path(a.repo)
        commits = git(repo, "rev-list", a.draft_thanks).split()
        me = load_config_values(a.config).get("commit email", "") \
            if a.config else ""
        heads, note = pr_heads(repo)
        line, by_class, authors = draft_thanks(repo, commits, me, heads)
        print(f"draft-thanks: range {a.draft_thanks}, {len(commits)} commits; "
              f"credit trailers: {sum(len(v) for v in by_class.values())}; "
              f"verbatim PR authors: {len(authors)}"
              + (f"; {note}" if note else ""), file=sys.stderr)
        print(line or "(no credit trailers in range: no Thanks line)")
        sys.exit(0)
    if not a.config:
        ap.error("--config is required (except with --lint-commands "
                 "or --draft-thanks)")

    repo = pathlib.Path(a.repo)
    sha = git(repo, "rev-parse", a.commit).strip()
    message = git(repo, "log", "-1", "--format=%B", sha)
    print(f"pre-push-check: {repo.resolve()} @ {sha[:12]} -> {a.target_branch}")
    print("subject: " + (message.strip().splitlines() or [""])[0])
    terms = load_terms(a.config)
    cfg = load_config_values(a.config)
    repo_name = a.repo_name or derive_repo_name(repo)
    scope, scope_label = scope_commits(repo, sha, a.target_branch)
    print("commits in scope: " + scope_label)
    rep = Report()
    check_closing_keywords(rep, message, repo, scope)
    check_diff_vs_claim(rep, repo, sha, message, a.max_files, a.allow_path)
    check_confidentiality(rep, message, terms,
                          load_vendor_subject(a.config, repo_name), repo_name,
                          repo, scope, cfg.get("commit email", ""))
    heads, heads_note = pr_heads(repo)
    check_signature(rep, repo, sha, a.target_branch, a.allow_unverifiable_signature,
                    a.pre_bundle, scope, cfg.get("signing key", ""),
                    cfg.get("commit email", ""), heads, heads_note)
    if a.release_body:
        commits, label = release_commits(repo, sha, a.release_range,
                                         a.single_commit)
        check_credit_symmetry(rep, repo, commits, label, a.release_body,
                              a.allow_mixed_trailers, cfg.get("commit email", ""),
                              heads)
    else:
        rep.result("5 credit-symmetry", "SKIP",
                   ["no --release-body; required at release time"])
    check_rendered_shape(rep, repo)
    if a.license_canonical:
        canonical, source = pathlib.Path(a.license_canonical), "--license-canonical"
    else:
        canonical, source = load_license_canonical(a.config)
    check_license_canonical(rep, repo, sha, canonical, source)
    figures = pathlib.Path(a.figures) if a.figures else \
        pathlib.Path(a.config).resolve().parent / "readme-figures.md"
    check_readme_figures(rep, repo, sha, figures, repo_name,
                         datetime.date.today(), named=bool(a.figures))
    print("RESULT: " + ("REFUSED — do not push" if rep.failed else "clear to push"))
    sys.exit(1 if rep.failed else 0)


if __name__ == "__main__":
    main()
