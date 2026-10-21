---
name: pr-review-loop
description: Fix or rebut outstanding Devin Review flags on a PR, one invariant per round.
triggers:
  - user
  - model
permissions:
  allow:
    - Read(**)
    - Write(**)
    - Exec(git)
    - Exec(gh)
    - Exec(sleep)
    - mcp__devin__devin_review_manage
---

# PR Review Loop

A *round* is one full pass: collect the outstanding flags, name the invariant they share, fix or rebut it, run the relevant tests when fixing, commit and push when fixing, and trigger the next review. Batching by invariant keeps the commit history clean and prevents a chain of review-fix commits. Run each round in one continuous turn, blocking on the review result, until the review is clean or a stop condition fires.

Every `mcp__devin__devin_review_manage` call below passes the confirmed `pr_url`. `action: trigger` starts a real review run, so call it only after the PR is confirmed. If the tool is unavailable, each call goes to the user instead: ask them to trigger the review when one is needed and to paste the open flags once it completes.

## Prepare the loop state

Before the first round, create a todo list with a single `Loop state` item. Keep it as the only place for `round`, `pr_url`, `invariant`, `round_type` (`fix` or `rebuttal`), `plan` (fix plan or rebuttal text), and `stop reason`. Update it each round.

Bind `pr_url` to the PR for the current branch - do not use an arbitrary or example PR URL:

1. Run `gh pr view --json url,headRefName` from the worktree.
2. If `gh` fails, no PR exists, or `headRefName` differs from `git branch --show-current`, ask the user for the correct PR URL and stop.
3. Display the derived `pr_url` and ask for explicit confirmation. If the user does not confirm, stop.

**Done when:** the `Loop state` item holds `round=1` and the user-confirmed `pr_url`.

## Stop conditions

The loop stops when the user sends one of these messages at any point:

- The user says one or all flags are resolved, overriding the review output.
- The user asks you to stop (e.g., daily quota is full).

Point-in-time conditions are checked inside the loop steps where they become knowable.

## Wait for the review

Call `get_status`. If no review exists, call `trigger`. While the status is `pending` or `running`, `sleep 5` and call `get_status` again. If the status ends in anything other than `completed` (e.g. `failed`, `error`), set `stop reason: review failed` and go to `## Final tidy`.

**Done when:** the review `status` is `completed`, or you are in `## Final tidy`.

## The loop

1. **Outstanding flags collected.**
   - Run `## Wait for the review`, then call `get_findings` (or use the flags the user pasted).
   - Keep findings whose status is `open`. Drop `resolved` or `dismissed` entries.
   - If none remain, set `stop reason: review clean` and go to `## Final tidy`.

   **Done when:** the list of open flags is known, or you are in `## Final tidy`.

2. **Invariant named and a single fix or rebuttal decided.**
   - Group the open flags by the invariant they point at. If they cannot be grouped into a single invariant, are contradictory, or need a product decision, set `stop reason: flags unclear/contradictory` and go to `## Final tidy`.
   - If the new invariant matches the previous round's `invariant`, set `stop reason: repeated invariant` and go to `## Final tidy`. Otherwise record it as `invariant`.
   - Decide the `round_type` and record the `plan`:
     - **Fix round**: the invariant is real. Design one fix for it. If a flag reports one bypass of a guard, fix the whole class per the [testing.md guard code rule](../../rules/testing.md#guard-code), not just the reported instance.
     - **Rebuttal round**: the flagged invariant is wrong. Keep the current code and draft a rebuttal that includes the flag text, severity, location, round, and the reason it is wrong. Surface it for the user to post, then skip to step 5.

   **Done when:** `invariant`, `round_type`, and `plan` are set in `Loop state`.

3. **Fix applied and tests passing.**
   - Apply the fix.
   - For guard or validator changes, write the attack matrix from the [testing.md guard code rule](../../rules/testing.md#guard-code) as tests first.
   - Run the relevant test suite. Discover the command from the repo's `AGENTS.md`, else from manifests (`package.json` scripts, `pyproject.toml`, etc.), else ask the user.
   - If the suite fails, fix the failure and rerun it. If it still fails, show the failures and ask the user whether to approve a test skip.

   **Done when:** the fix is applied and the suite passes, or the user has approved a test skip.

4. **Round committed and pushed once.**
   - Commit as plain logical commits per [git-workflow.md](../../rules/git-workflow.md), so the PR's published history stays intact. `## Final tidy` decides whether to rebuild.
   - Push once with `git push`. Per-round pushes skip `pre-push-review`. `## Final tidy` runs it over the whole loop.

   **Done when:** the round is committed and pushed exactly once.

5. **Next review triggered and completed.** Call `trigger` (or ask the user to trigger it when the tool is unavailable), then run `## Wait for the review`.

   **Done when:** the review `status` is `completed`, or you are in `## Final tidy`.

6. **Loop ended or continued.**
   - If the user sent one of the messages in `## Stop conditions`, set the matching stop reason and go to `## Final tidy`.
   - If `round` is 5, set `stop reason: fifth round reached` and go to `## Final tidy`.
   - Otherwise, increment `round` and return to step 1.

   **Done when:** `Loop state` is updated and you are back at step 1 or in `## Final tidy`.

## Final tidy

Run before the user views the branch, regardless of how the loop ended.

Invoke the `pre-push-review` skill and show `git log --oneline origin/main..HEAD` so the user reviews the commits added during the loop. If the branch is not based on `origin/main`, substitute the correct base.

If the branch is a chain of review-fix commits, propose a rebuild and get explicit user approval before force-pushing. Present the final commit story so the user knows what to review.

**Done when:** `pre-push-review` has run and the commit log from the correct base to `HEAD` is shown.
