# Git workflow

Keep every commit atomic and every unpushed series coherent. Commit message rules are in [git-commits.md](git-commits.md).

## Branches and pull requests

- Branch from the PR's target branch, usually `main`.
- Name branches with a concrete noun or `verb-noun` form that describes the change (e.g., `session-cache-fix`, `add-export-flow`). Avoid generic names like `fix` or `feature`.
- Keep one logical change per branch.
- Open a PR when the branch is ready for review. Give the PR a title and body that summarize the outcome and the test plan.

Done when:
- The branch name describes the change.
- The PR title and body summarize the outcome and the test plan.

## Commit messages

We follow Conventional Commits. See [git-commits.md](git-commits.md) for the full rules and examples.

## Before committing

- Keep the index limited to the intended, clean changes; remove any debug or temporary content you added (stray prints/logs, scratch files); leave everything else in place.
- Commit the related, intentional changes; leave incidental formatting or whitespace churn unstaged.
- Put real secrets and credentials in `.env` (git-ignored) or the deploy platform's config vars; put only placeholders and comments in `.env.template`.

Done when:
- `git diff --cached` contains only the intended, clean changes.
- The commit message follows Conventional Commits.
- The repo's commit-msg hook, if present, would pass.

## Before pushing

- Review the unpushed series with `git log --oneline origin/main..HEAD` (or the branch's actual base). Each commit must be a single, logical step; the series as a whole must tell a coherent story. Invoke the `pre-push-review` skill before any push.
- Run the relevant tests before pushing; find the command in the repo's `AGENTS.md` or manifests.
- On a branch with an open PR, batch review feedback into logical fixes instead of pushing a chain of one-line `fix:` commits. If the history becomes noisy, propose a rebuild to the user before pushing again. To drive a PR to a clean Devin Review state, use the `pr-review-loop` skill.
- Keep an open PR's published history intact. If the user explicitly asks to rebase or force-push, warn before proceeding and re-split bundled commits as part of the rewrite.

Done when:
- `git log --oneline origin/main..HEAD` is a coherent, atomic series.
- Relevant tests pass.
- `pre-push-review` has completed.
