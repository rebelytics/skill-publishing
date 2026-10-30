# skill-publishing

Open-source skill that **publishes agent skills as open-source repositories and keeps the published repos byte-identical to the installed copies**: one repo per skill, a freshness gate between installed and staged versions, a confidentiality scan over every file, commits built in a sandbox and handed over as git bundles, and a push gate run before every push. Load it into any MCP-capable AI agent (Claude, Cursor, Codex, n8n, etc.).

## When it triggers

Publishing or open-sourcing a skill, syncing a skill repo, creating a repo, README or LICENSE for a skill, reviewing a diff or bundle before a push, deciding whether a skill can be open-sourced, promotion shortlists, upstream drift on a published repo, issue and PR checks on skill repos, a release branch under test, folding community contributions into a release, or a repo awaiting its first push.

## What this repo contains

- `SKILL.md` — the configuration contract, the hard rules, the workspace state, the cycle, the public-artefact conventions and the pointer list for the reference files.
- `references/` — the cycle step bodies (`cycle-gates-and-sync.md`, `cycle-commit-and-close.md`), promotion and first publication, release branches and contributions, README rules, the confidentiality scan and the execution environments; `ceilings.txt` holds the line ceilings the skill validator reads.
- `scripts/` — `confidentiality_scan.py`, `pre-push-check.py`, `cut-release-branch.py`, `pr-coverage.py`.
- `LICENSE` — CC BY 4.0.

## Install

Install the whole skill directory — `SKILL.md`, `references/` and `scripts/` must travel together — into your MCP-capable agent's skills directory, following the client-specific path, and restart the client. Every maintainer-specific value (identity, account, tripwire terms, exclusions, cadence) lives in a private configuration file the skill asks for on its first run.

## Related

[`task-observer`](https://github.com/rebelytics/one-skill-to-rule-them-all) is the published companion: it runs the skill reviews whose staged copies this skill publishes, and its validator and authoring reference are cited here.

## Contributing

Open an issue or a PR at [github.com/rebelytics/skill-publishing](https://github.com/rebelytics/skill-publishing).

## Credits

- Original author: [Eoghan Henn](https://www.rebelytics.com) / [LinkedIn](https://www.linkedin.com/in/eoghanhenn)

## License

CC BY 4.0 — the licence text is in [LICENSE](./LICENSE): the full legal code, unmodified, as Creative Commons publishes it; the [human-readable summary](https://creativecommons.org/licenses/by/4.0/) says what it allows. Use it, fork it, adapt it, monetise it. Keep the attribution.

Copyright (c) 2026 Eoghan Henn / rebelytics.com
