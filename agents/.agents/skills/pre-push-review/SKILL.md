---
name: pre-push-review
description: Tidy the unpushed series before any push, PR open/update, pr-review-loop convergence, or user request.
triggers:
  - user
  - model
---

# Pre-Push Review

## 1. Load the commit series

If the repo has a commit-msg hook (`git rev-parse --git-path
hooks`/commit-msg), verify it runs.
If the working tree is dirty, stop and ask the user to commit or stash.
Derive or recover `$base` as in the `Variables` section of the `fixup-squash`
skill, then inspect the unpushed series with `git log --oneline "$base"..HEAD`
and `git diff "$base"..HEAD`.
For a short-lived branch with one clean commit, you may skip the full review but
still run tests and a quick style pass.

**Done when:** the hook check is done, the tree is clean, `$base` is set, and
the unpushed series is listed against it.

## 2. Load the review bar

Load the review bar before checking commits: the
[git-commits.md](../../rules/git-commits.md) commit conventions plus this skill's
tidy judgement. Conventions accept overrides that improve the story; the safety
invariants in [git-workflow.md](../../rules/git-workflow.md#before-committing) and
[testing.md](../../rules/testing.md#guard-code) bind regardless.

**Done when:** before checking the first commit, you have stated the review bar
and the three safety invariants (hook-enforced rules, guard attack matrix, no
secrets).

## 3. Common issues

For each commit, check:

- **Subject semantics**: a commit-msg hook, if present, enforces the mechanical
  rules, including the most common vague verbs. Apply the rest of the
  [git-commits.md subject-style rules](../../rules/git-commits.md#subject-and-body)
  and reword to name the concrete artifact or change.
- **Scope membership**: if a commit's subject has a scope, check it against the
  scopes in history before the series - run the
  [git-commits.md scope-listing command](../../rules/git-commits.md#scope)
  against `"$base"`. An unknown scope is a finding: propose rewording to an
  existing scope or confirm the new scope with the user. If the list is empty,
  the scope is the first in history.
- **`docs:` commits**: apply the
  [git-commits.md rule](../../rules/git-commits.md#conventional-commits):
  documentation and comments only.
- **`fixup!` / `squash!` commits**: fold them into their target commit with
  `fixup-squash` before finalizing the series.
- **Late fixups**: a late `fix`, `refactor`, or `test` that only corrects an
  earlier `feat`/`fix` is a squash candidate.
- **Churn and dead ends**: back-and-forth or exploratory commits that add no new
  story are squash or drop candidates.
- **Guard or validator changes**: keep the valid / invalid / bypass-input tests
  in the same commit as the guard. See
  [testing.md guard code](../../rules/testing.md#guard-code).
- **Secrets and credentials**: the commit contains no real secrets or
  credentials. Real values stay in `.env` (git-ignored) or config vars. See
  [git-workflow.md Before committing](../../rules/git-workflow.md#before-committing).

**Done when:** every commit in the unpushed series has been checked against each
item, and every issue found is carried into the tidy plan.

## 4. The commit value test

Before keeping a late commit separate, ask:

1. If squashed into the parent, will the story lose information a future reader needs?
2. Can the same information live as a code comment or in the parent commit message?

Keep the commit separate only if it captures a design decision, tradeoff,
constraint, or gotcha not obvious in the code. Otherwise squash it and add a
comment if needed.

**Done when:** every late commit is classified keep-separate or squash, and
each kept commit names the decision, tradeoff, constraint, or gotcha it
preserves.

## 5. Propose a tidy plan

Present a short plan: what to reword, squash, drop, or split. Note any rule
overrides and why they make a better story.

**Done when:** the plan names every commit to reword, squash, drop, or split
and why, including overrides.

## 6. Execute or ask

For a **local-only branch** (one that exists only on your machine), you may
execute message-only rewords and create `fixup!` marker commits immediately. Use
the `fixup-squash` skill for the mechanics.

For a **published branch** (one that has been pushed or has an open PR), you
must get explicit approval before any rebase, reword, squash, drop, split, or
reset. Explain exactly what will change, show the before/after
`git log --oneline`, and get approval. Then apply with `fixup-squash`.

If no issues are found, say so and continue to tests.

**Done when:** for a local-only branch, the series is clean; for a published
branch, the user has approved the rewrite and it has been applied; or no rewrite
was needed and the series is already clean.

## 7. Run tests

Discover the test command from the repo's `AGENTS.md`; if absent, infer from
manifests (`package.json` scripts, `pyproject.toml`, etc.); if still unclear,
ask the user. Run it or the most relevant subset. For changes that only touch
documentation or skill files, you may skip the full suite if no relevant tests
exist, but say so.

**Done when:** the relevant tests pass, or the skip is stated with its reason.

## 8. Present the result

Show the cleaned `git log --oneline "$base"..HEAD`, a one-paragraph story, and
the test result.

**Done when:** the user sees the final `git log --oneline "$base"..HEAD`, the
story, and the test result.
