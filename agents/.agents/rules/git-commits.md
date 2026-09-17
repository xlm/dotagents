# Git commits

## Conventional Commits

Use [Conventional Commits](https://www.conventionalcommits.org/) (Angular convention).

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `revert`, `release`.
Pick the narrowest allowed type. If a change looks like a `chore`, reclassify it into one of the allowed types.

A `docs:` commit changes only documentation (README, `AGENTS.md`, `.agents/skills/`, or similar human-facing docs) and code comments. Code comments that explain a new `feat`/`fix` belong in the `feat`/`fix` commit. Standalone comments on already-merged code belong in a `docs:` commit. A `feat`/`fix` commit may include small, directly tied docs or comment updates if the commit stays focused.

Release / version-bump-only changes: use a custom `release:` type with the version as the description (e.g., `release: 1.2.3`). Reserved solely for version bumps. A `release:` commit contains the version bump only, with no `!` or `BREAKING CHANGE:` footers.

## Classification

Classify the staged diff before composing a message:

- **Docs or comments only**: the diff changes only human-facing docs, or a source file's only changes are comments/docstrings. Type is `docs`.
- **Style only**: formatting, lint fixes, semicolons, or whitespace with no logic, type, test, or config change. Type is `style`.
- **Release version bump**: a version bump with no other logic. Type is `release:`.
- **Revert**: `revert: <subject of reverted commit>` with a body line `This reverts commit <hash>`, unquoted and without a `Revert` prefix.
- **Merge commit**: do not propose one - rebase first. If a merge is unavoidable, create the merge then commit with `--no-verify`.
- **Breaking change**: breaks public API or behavior and is not `release:`/`revert:`. Mark with `!` and a `BREAKING CHANGE:` footer (format below).
- **Everything else**: logic, types, tests, config, CI files, or a mix of code and small docs. Choose the narrowest allowed type that matches.

Blockers: if the diff contains conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) or temporary/debug output (e.g. `print(`, `console.log`, `debugger;`, commented-out code), stop and clean up before composing.

If the diff contains two or more logical changes, split it into separate commits, each atomic and logically single-purpose. Small docs or comment updates directly tied to a `feat`/`fix` stay with that commit. Large or user-facing docs split out.

## Scope

Use one scope or none. A scope is a single noun naming the area the change affects (e.g., `feat(auth): ...`). For cross-area changes, split the commit or omit the scope.

Prefer an existing scope. List the scopes already in history with:

```sh
git log --pretty=format:%s | sed -En 's/^(feat|fix|docs|style|refactor|perf|test|build|ci|revert|release)\(([a-z0-9-]+)\)!?:.*$/\2/p' | sort -u
```

A scope absent from that list is new - confirm it before using it. If the list is empty, the scope would be the first in history.

## Subject and body

- 50/72 rule: keep the subject line at or below 50 characters. Wrap body lines at 72.
- Commit pure renames, moves, and repackaging separately from behavioral change, so a move reads as a reviewable no-op. Include only the mechanical edits the move requires.
- Structure a solution as an ordered progression from most isolated/least complex to most broad/complex. Lead with cleanups, one-line fixes, and mechanical edits; then model/type changes; then broader feature or app-wiring changes, ordered by how much of the request pipeline they touch.
- Treat a manifest bump and its lockfile update as a single commit (e.g., `pyproject.toml` + `uv.lock`, or `package.json` + `pnpm-lock.yaml`).
- Bundle a dependency bump with the code that first uses it. The consuming code is the bump's justification and the combined commit builds on its own. Pull the bump into its own preceding commit only when it is shared by multiple later commits or is a large standalone upgrade. Then say what it enables in the message.
- When revising or rebasing a branch, re-split commits that bundle multiple concerns. A rebase corrects commit boundaries before it replays them.

  > This rule applies within a rebase or revision that is already in progress.

- Breaking changes: append `!` after type/scope (e.g., `feat(api)!: ...`) and add a `BREAKING CHANGE:` footer describing what broke and the migration path. The footer is mandatory. Include it even when the subject has `!`.

- Subject style: lowercase, no trailing period, any readable form (imperative, declarative, or noun phrase). Name the outcome. When it helps locate the change, include the concrete artifact or path (`src/auth`, `dist/bundle`). The type already classifies the change - a verb that re-says it is wasted (`feat: add metrics export` → `feat: metrics export`; `fix: fix crash on logout` → `fix: prevent crash on logout`). Use the concrete action as the verb. `support`, `enable`, `allow`, and `complete` are symptoms of a vague subject.

Full message example:

```
fix(search): drop cached results on index update

Stale results were shown after a reindex because the
result was memoized lacking a version key. Key the cache on the
index version so results recompute when it changes.
```

Omit body example:

```
docs: agent commits use concrete subject terms
```

## Composing the message

- Compose multi-line commit messages with `git commit -F` or one heredoc, because each `-m` becomes a separate paragraph and produces mid-sentence blank lines.
- The Devin attribution footer (`Generated with [Devin]`, `Co-Authored-By: Devin`) is appended by the CLI and is intentional. It marks agent-authored commits. Leave it intact.

Done when every staged change is classified; each commit has an allowed type, at most one scope (existing or confirmed), a subject at or below 50 characters that names the outcome, and a single logical change; breaking changes carry `!` and the `BREAKING CHANGE:` footer.
