# Personal rules

Global defaults for every repo. A repo's own `AGENTS.md` adds
project-specific facts on top of these.

- Never use an em dash. Use a hyphen.
- In prose, prefer a full stop or comma over a semicolon.

## On-demand rule docs

Shared rule docs live in `agents/.agents/rules/` under this file's
directory (also `~/.agents/rules/` where the repo is stowed). Load
them when the work matches:

- Writing or editing code: `code-style.md`.
- Planning non-trivial work: `planning.md`.
- Composing or reviewing commit messages or series: `git-commits.md`.
- Branching, staging, pushing, PRs: `git-workflow.md`.
- Creating or working in a worktree: `git-worktree.md`.
- Writing tests, or changing a validator, parser, or regex
  (guard-code attack matrix): `testing.md`.
