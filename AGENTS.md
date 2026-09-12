# Personal rules

Global defaults for every repo. A repo's own `AGENTS.md` adds
project-specific facts on top of these.

- Never use an em dash. Use a hyphen.

## On-demand rule docs

Shared rule docs live in `agents/.agents/rules/` under this file's
directory (also `~/.agents/rules/` where the repo is stowed). Load
them when the work matches:

- `code-style.md` - writing or editing code.
- `planning.md` - planning non-trivial work.
- `git-commits.md` - composing or reviewing commit messages or series.
- `git-workflow.md` - branching, staging, pushing, PR series hygiene.
- `testing.md` - writing tests, or changing a validator, parser, or
  regex (guard-code attack matrix).
